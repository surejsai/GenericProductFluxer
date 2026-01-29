"""
Hybrid entity extraction orchestrator.

Combines deterministic rules extraction with LLM-powered gap filling.
Strategy: Rules first, LLM only when confidence is low or critical types missing.
"""
from __future__ import annotations

from collections import defaultdict
from typing import List, Dict, Tuple, Optional

from ..models import (
    EntityExtractionResult,
    HybridEntityExtractionResult,
    EntityItem,
    SupportingEntity,
    PlacementRecommendation,
    AuditInfo
)
from ..services.entity_rules import EntityRulesEngine
from ..services.entity_llm import EntityLLMExtractor, LLMExtractionResult
from ..services.entity_merge import EntityMerger
from ..config import Config
from ..logger import get_logger

logger = get_logger(__name__)


class EntityExtractor:
    """
    Orchestrate hybrid rules + LLM entity extraction.

    Strategy:
    1. Always run rules extraction first (fast, deterministic)
    2. Evaluate confidence and check for missing critical types
    3. If gaps exist, invoke LLM to fill them
    4. Merge results with rules preference
    5. Build placement recommendations
    """

    # Confidence threshold below which LLM is triggered
    CONFIDENCE_THRESHOLD = 0.7

    # Entity types that should trigger LLM if missing
    CRITICAL_TYPES = ['material', 'dimension']

    # Category keywords for TF-IDF term grouping
    CATEGORY_KEYWORDS = {
        'core_attributes': {
            'size', 'width', 'height', 'depth', 'length', 'diameter',
            'material', 'colour', 'color', 'finish', 'weight', 'capacity',
            'volume', 'dimension', 'thickness', 'gauge', 'grade', 'density',
            'pattern', 'style', 'texture', 'surface'
        },
        'functional_terms': {
            'durability', 'durable', 'strength', 'load', 'rating',
            'resistance', 'heat', 'water', 'fire', 'corrosion', 'rust',
            'temperature', 'moisture', 'uv', 'fade', 'fading', 'longevity',
            'lifespan', 'performance', 'efficient', 'energy', 'power',
            'capacity', 'speed', 'flow', 'pressure', 'noise'
        },
        'usage_context': {
            'indoor', 'outdoor', 'interior', 'exterior', 'residential',
            'commercial', 'industrial', 'domestic', 'home', 'office', 'garden',
            'patio', 'pool', 'bathroom', 'kitchen', 'bedroom', 'living',
            'room', 'space', 'area', 'climate', 'coastal', 'exposure',
            'environment', 'condition', 'season', 'weather', 'tropical'
        },
        'compliance_standards': {
            'standard', 'certification', 'certified', 'au', 'nz', 'as/nzs',
            'iso', 'safety', 'warrant', 'warranty', 'guarantee',
            'care', 'instruction', 'maintenance', 'clean', 'cleaning',
            'disposal', 'recycle', 'recycling', 'label', 'rating', 'ce',
            'fda', 'rohs', 'reach'
        }
    }

    # Placement rules by entity type
    PLACEMENT_RULES = {
        'material': {
            'sections': ['specs_table', 'features', 'care_instructions'],
            'reasoning': 'Material information belongs in specifications and care guidance.'
        },
        'dimension': {
            'sections': ['specs_table', 'hero_copy'],
            'reasoning': 'Dimensions are key specifications that help with fit assessment.'
        },
        'weight': {
            'sections': ['specs_table', 'shipping_info'],
            'reasoning': 'Weight affects shipping and handling considerations.'
        },
        'capacity': {
            'sections': ['specs_table', 'features'],
            'reasoning': 'Capacity is a key functional specification.'
        },
        'finish': {
            'sections': ['specs_table', 'care_instructions'],
            'reasoning': 'Finish affects appearance and maintenance requirements.'
        },
        'standard': {
            'sections': ['specs_table', 'certifications', 'faq'],
            'reasoning': 'Standards/certifications should be clearly listed.'
        },
        'certification': {
            'sections': ['specs_table', 'certifications', 'sustainability'],
            'reasoning': 'Certifications provide credibility and compliance info.'
        },
        'environment': {
            'sections': ['designed_for', 'use_cases', 'features'],
            'reasoning': 'Usage environment guides customer suitability assessment.'
        },
        'care': {
            'sections': ['care_instructions', 'maintenance', 'faq'],
            'reasoning': 'Care information helps maintain product longevity.'
        },
        'warranty': {
            'sections': ['warranty_info', 'faq', 'specs_table'],
            'reasoning': 'Warranty details provide purchase confidence.'
        },
        'rating': {
            'sections': ['specs_table', 'features'],
            'reasoning': 'Power/efficiency ratings are key specifications.'
        }
    }

    def __init__(self):
        """Initialize the hybrid entity extractor."""
        self.rules_engine = EntityRulesEngine()
        self.llm_extractor = EntityLLMExtractor()
        self.merger = EntityMerger()

        # Get threshold from config if available
        self.confidence_threshold = getattr(
            Config, 'ENTITY_CONFIDENCE_THRESHOLD', self.CONFIDENCE_THRESHOLD
        )

        logger.info(f"EntityExtractor initialized (threshold={self.confidence_threshold})")

    def extract_entities(
        self,
        product_id: str,
        product_name: str,
        tfidf_terms: List[Dict],
        product_description: Optional[str] = None,
        force_llm: bool = False,
        search_query: Optional[str] = None
    ) -> HybridEntityExtractionResult:
        """
        Extract entities using hybrid rules + LLM approach.

        Args:
            product_id: Unique product identifier
            product_name: Product name/title
            tfidf_terms: List of TF-IDF term dicts with 'phrase' key
            product_description: Optional product description text
            force_llm: Force LLM extraction regardless of confidence
            search_query: Original search query for better LLM context

        Returns:
            HybridEntityExtractionResult with full audit trail
        """
        audit = AuditInfo()

        # Step 1: Group TF-IDF terms into buckets
        grouped_terms, noise_terms = self._group_terms(tfidf_terms)
        logger.info(f"Grouped {sum(len(v) for v in grouped_terms.values())} terms, {len(noise_terms)} noise")

        # Step 2: Run rules extraction (pass search_query for context-aware filtering)
        rules_result = self.rules_engine.extract(
            product_name=product_name,
            tfidf_terms=tfidf_terms,
            description=product_description,
            search_query=search_query
        )
        audit.notes.extend(rules_result.notes)

        # Step 3: Determine if LLM should be invoked
        llm_result: Optional[LLMExtractionResult] = None

        should_invoke, invoke_reason = self.llm_extractor.should_invoke(
            rules_confidence=rules_result.confidence,
            missing_types=rules_result.missing_types,
            threshold=self.confidence_threshold,
            critical_types=self.CRITICAL_TYPES
        )

        if force_llm:
            should_invoke = True
            invoke_reason = "Forced by request"

        if should_invoke:
            audit.llm_invoked = True
            audit.llm_reason = invoke_reason
            logger.info(f"Invoking LLM: {invoke_reason}")

            # Step 4: Run LLM extraction
            # Pass search_query for better context about the product type
            llm_result = self.llm_extractor.extract(
                product_name=product_name,
                description=product_description,
                tfidf_terms=tfidf_terms,
                missing_types=rules_result.missing_types,
                existing_entities=rules_result.rule_entities,
                search_query=search_query
            )

            if llm_result.success:
                audit.notes.extend(llm_result.notes)
            else:
                audit.notes.append(f"LLM extraction failed: {llm_result.error}")
        else:
            audit.notes.append(f"LLM skipped: {invoke_reason}")

        # Step 5: Merge results
        llm_entities = llm_result.llm_entities if llm_result and llm_result.success else []
        llm_confidence = llm_result.confidence if llm_result and llm_result.success else 0.0

        merge_result = self.merger.merge(
            rule_entities=rules_result.rule_entities,
            llm_entities=llm_entities,
            rules_confidence=rules_result.confidence,
            llm_confidence=llm_confidence
        )

        audit.notes.extend(merge_result.notes)
        audit.conflicts = rules_result.conflicts + merge_result.conflicts
        audit.missing_types = rules_result.missing_types

        # Step 6: Determine primary entity path
        primary_entity_path = self._determine_primary_entity_path(
            rules_result.primary_entity_path,
            llm_result.primary_entity_path if llm_result else None
        )

        # Step 7: Build placement map
        placement_map = self._create_placement_map(
            merge_result.merged_entities,
            grouped_terms,
            llm_result.placement_suggestions if llm_result else None
        )

        # Clean product name (remove brand names for generic output)
        clean_product_name = self.merger.clean_product_name(product_name)

        # Build final result
        result = HybridEntityExtractionResult(
            product_id=product_id,
            product_name=clean_product_name,
            primary_entity_path=primary_entity_path,
            grouped_terms=grouped_terms,
            rule_entities=rules_result.rule_entities,
            llm_entities=llm_entities,
            supporting_entities=merge_result.merged_entities,
            placement_map=placement_map,
            noise_terms=noise_terms,
            confidence=merge_result.confidence,
            audit=audit
        )

        logger.info(
            f"Extraction complete: {len(result.supporting_entities)} entities, "
            f"confidence={result.confidence:.2f}, llm_invoked={audit.llm_invoked}"
        )

        return result

    def extract_entities_simple(
        self,
        product_id: str,
        product_name: str,
        tfidf_terms: List[Dict],
        product_description: Optional[str] = None
    ) -> EntityExtractionResult:
        """
        Backward-compatible simple extraction (rules only, original format).

        Args:
            product_id: Unique product identifier
            product_name: Product name/title
            tfidf_terms: List of TF-IDF term dicts
            product_description: Optional product description

        Returns:
            EntityExtractionResult in original format
        """
        # Group terms
        grouped_terms, noise_terms = self._group_terms(tfidf_terms)

        # Run rules extraction
        rules_result = self.rules_engine.extract(
            product_name=product_name,
            tfidf_terms=tfidf_terms,
            description=product_description
        )

        # Convert EntityItems to SupportingEntities
        supporting_entities = [
            SupportingEntity(
                name=e.name,
                entity_type=e.entity_type,
                why_it_matters=e.why_it_matters or ""
            )
            for e in rules_result.rule_entities
        ]

        # Build placement map
        placement_map = self._create_placement_map_simple(supporting_entities, grouped_terms)

        # Clean product name and entity path (remove brand names)
        clean_product_name = self.merger.clean_product_name(product_name)
        primary_path = rules_result.primary_entity_path or f"Product > {clean_product_name.title()}"
        primary_path = self.merger.clean_entity_path(primary_path)

        return EntityExtractionResult(
            product_id=product_id,
            product_name=clean_product_name,
            primary_entity_path=primary_path,
            supporting_entities=supporting_entities,
            placement_map=placement_map,
            noise_terms=noise_terms,
            grouped_terms=grouped_terms
        )

    def _group_terms(
        self,
        tfidf_terms: List[Dict]
    ) -> Tuple[Dict[str, List[str]], List[str]]:
        """Group TF-IDF terms into categories."""
        grouped = defaultdict(list)
        noise = []

        categories = {
            'core_attributes': 'Core Attributes',
            'functional_terms': 'Functional Terms',
            'usage_context': 'Usage Context',
            'compliance_standards': 'Compliance / Standards'
        }

        for term_data in tfidf_terms:
            phrase = term_data.get('phrase', '').lower().strip()
            if not phrase:
                continue

            found_category = None
            for category_key, keywords in self.CATEGORY_KEYWORDS.items():
                for keyword in keywords:
                    if keyword.lower() in phrase:
                        found_category = categories[category_key]
                        break
                if found_category:
                    break

            if found_category:
                grouped[found_category].append(phrase)
            else:
                noise.append(phrase)

        # Remove duplicates
        grouped_unique = {
            cat: list(dict.fromkeys(terms))
            for cat, terms in grouped.items()
        }

        return grouped_unique, noise

    def _determine_primary_entity_path(
        self,
        rules_path: Optional[str],
        llm_path: Optional[str]
    ) -> str:
        """
        Determine final primary entity path.

        Strategy:
        - If rules returns a confident category (not "Product >"), use it
        - If rules returns "Product > Unknown" (low confidence), prefer LLM
        - If rules returns "Product > <something>" but LLM has a better path, prefer LLM
        - Fall back to rules path if nothing else works
        """
        # Check if rules path indicates low confidence
        rules_uncertain = (
            not rules_path or
            rules_path.startswith("Product >")
        )

        # Check if LLM provided a confident category
        llm_has_category = (
            llm_path and
            not llm_path.startswith("Product >") and
            "Unknown" not in llm_path
        )

        if not rules_uncertain:
            # Rules has a confident category match
            path = rules_path
        elif llm_has_category:
            # Rules uncertain, but LLM has a confident category
            path = llm_path
            logger.info(f"Using LLM category path: {llm_path} (rules was uncertain)")
        else:
            # Both are uncertain, use rules path or default
            path = rules_path or "Product > Unknown"

        # Clean brand names from the path
        path = self.merger.clean_entity_path(path)
        return path

    def _create_placement_map(
        self,
        entities: List[EntityItem],
        grouped_terms: Dict[str, List[str]],
        llm_suggestions: Optional[Dict[str, List[str]]] = None
    ) -> List[PlacementRecommendation]:
        """Create placement recommendations for entities."""
        placements = []
        seen_entities = set()

        # Add placements for each entity
        for entity in entities:
            if entity.name in seen_entities:
                continue
            seen_entities.add(entity.name)

            rules = self.PLACEMENT_RULES.get(entity.entity_type, {})
            sections = rules.get('sections', ['specs_table'])
            reasoning = rules.get('reasoning', 'Appropriate PDP section based on entity type.')

            # Check LLM suggestions
            if llm_suggestions:
                for section, names in llm_suggestions.items():
                    if entity.name in names and section not in sections:
                        sections.append(section)

            placements.append(PlacementRecommendation(
                entity_name=entity.name,
                entity_type=entity.entity_type,
                recommended_sections=sections,
                reasoning=reasoning
            ))

        # Add category-level recommendations
        if 'Core Attributes' in grouped_terms:
            placements.append(PlacementRecommendation(
                entity_name='Specifications',
                entity_type='core_attributes',
                recommended_sections=['specs_table'],
                reasoning='Core attribute terms should populate the specifications table.'
            ))

        if 'Functional Terms' in grouped_terms:
            placements.append(PlacementRecommendation(
                entity_name='Features & Benefits',
                entity_type='functional_terms',
                recommended_sections=['features', 'hero_copy'],
                reasoning='Functional advantages highlight key benefits.'
            ))

        if 'Usage Context' in grouped_terms:
            placements.append(PlacementRecommendation(
                entity_name='Designed For',
                entity_type='usage_context',
                recommended_sections=['designed_for', 'use_cases'],
                reasoning='Usage context helps customers assess suitability.'
            ))

        return placements

    def _create_placement_map_simple(
        self,
        entities: List[SupportingEntity],
        grouped_terms: Dict[str, List[str]]
    ) -> List[PlacementRecommendation]:
        """Create placement map for simple/legacy format."""
        placements = []

        simple_rules = {
            'material': {
                'sections': ['specs_table', 'features', 'care_instructions'],
                'reasoning': 'Material information belongs in specifications and care guidance.'
            },
            'standard': {
                'sections': ['specs_table', 'certifications', 'faq'],
                'reasoning': 'Certifications should be clearly listed.'
            },
            'environment': {
                'sections': ['designed_for', 'use_cases', 'features'],
                'reasoning': 'Usage environment guides suitability assessment.'
            },
            'care': {
                'sections': ['care_instructions', 'maintenance', 'faq'],
                'reasoning': 'Care information helps maintain product longevity.'
            }
        }

        for entity in entities:
            rules = simple_rules.get(entity.entity_type, {})
            placements.append(PlacementRecommendation(
                entity_name=entity.name,
                entity_type=entity.entity_type,
                recommended_sections=rules.get('sections', []),
                reasoning=rules.get('reasoning', 'Appropriate PDP section.')
            ))

        # Category recommendations
        if 'Core Attributes' in grouped_terms:
            placements.append(PlacementRecommendation(
                entity_name='Specifications',
                entity_type='core_attributes',
                recommended_sections=['specs_table'],
                reasoning='Core attributes populate specifications.'
            ))

        if 'Functional Terms' in grouped_terms:
            placements.append(PlacementRecommendation(
                entity_name='Features & Benefits',
                entity_type='functional_terms',
                recommended_sections=['features', 'hero_copy'],
                reasoning='Functional terms highlight benefits.'
            ))

        return placements
