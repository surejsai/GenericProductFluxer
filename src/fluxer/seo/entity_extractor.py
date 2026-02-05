"""
Hybrid entity extraction orchestrator.

Combines deterministic rules extraction with LLM-powered gap filling.
Strategy: Rules first, LLM only when confidence is low or critical types missing.

TF-IDF term grouping is now fully LLM-powered for dynamic, context-aware categorization.
"""
from __future__ import annotations

import json
from typing import List, Dict, Tuple, Optional, Any

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

# Check OpenAI availability for dynamic term grouping
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.info("OpenAI not available for dynamic term grouping")

# Global OpenAI client (lazy initialization)
_openai_client: Optional[Any] = None


def _get_openai_client() -> Optional[Any]:
    """Get or initialize the OpenAI client."""
    global _openai_client
    if _openai_client is None and OPENAI_AVAILABLE:
        api_key = Config.OPENAI_API_KEY
        if api_key:
            _openai_client = OpenAI(api_key=api_key)
            logger.debug("OpenAI client initialized for term grouping")
    return _openai_client


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

        # Step 1: Clean + group TF-IDF terms in a single LLM call
        grouped_terms, noise_terms = self._clean_and_group_terms(tfidf_terms, search_query=search_query)
        logger.info(f"Grouped {sum(len(v) for v in grouped_terms.values())} terms, {len(noise_terms)} noise")

        # Step 3: Run rules extraction (pass search_query for context-aware filtering)
        rules_result = self.rules_engine.extract(
            product_name=product_name,
            tfidf_terms=tfidf_terms,
            description=product_description,
            search_query=search_query
        )
        audit.notes.extend(rules_result.notes)

        # Step 4: Determine if LLM should be invoked
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

            # Step 5: Run LLM extraction
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

        # Step 6: Merge results
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
        product_description: Optional[str] = None,
        search_query: Optional[str] = None
    ) -> EntityExtractionResult:
        """
        Backward-compatible simple extraction (rules only, original format).

        Args:
            product_id: Unique product identifier
            product_name: Product name/title
            tfidf_terms: List of TF-IDF term dicts
            product_description: Optional product description
            search_query: Optional search query for context-aware grouping

        Returns:
            EntityExtractionResult in original format
        """
        # Step 1: Clean + group TF-IDF terms in a single LLM call
        grouped_terms, noise_terms = self._clean_and_group_terms(tfidf_terms, search_query=search_query)

        # Step 3: Run rules extraction
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

    def _clean_and_group_terms(
        self,
        tfidf_terms: List[Dict],
        search_query: Optional[str] = None
    ) -> Tuple[Dict[str, List[str]], List[str]]:
        """
        Clean and group TF-IDF terms in a SINGLE LLM call.

        Combines noise filtering and category grouping into one API call to:
        - Remove shipping/delivery, pricing, store names, marketing noise
        - Categorize remaining terms into Core Attributes, Functional, Care, Compliance

        Args:
            tfidf_terms: List of TF-IDF term dicts with 'phrase' key
            search_query: Optional search query for context

        Returns:
            Tuple of (grouped_terms dict, noise_terms list)
        """
        # Extract phrases from term data
        phrases = []
        for term_data in tfidf_terms:
            phrase = term_data.get('phrase', '').strip()
            if phrase:
                phrases.append(phrase)

        if not phrases:
            return {}, []

        # Try LLM-powered clean + group in one call
        client = _get_openai_client()
        if client and OPENAI_AVAILABLE:
            try:
                return self._clean_and_group_with_llm(client, phrases, search_query)
            except Exception as e:
                logger.warning(f"LLM clean+group failed, using fallback: {e}")

        # Fallback: all terms go to Core Attributes, no noise detected
        logger.info("Using fallback term grouping (LLM unavailable)")
        return {"Core Attributes": phrases}, []

    def _clean_and_group_with_llm(
        self,
        client: Any,
        phrases: List[str],
        search_query: Optional[str] = None
    ) -> Tuple[Dict[str, List[str]], List[str]]:
        """
        Single LLM call to filter noise AND categorize TF-IDF terms.

        Replaces the previous two-call approach (_clean_terms_with_llm + _group_terms_with_llm).
        """
        # Limit phrases for API efficiency
        phrases_to_process = phrases[:150]

        context = f'Product search: "{search_query}"' if search_query else "General product"

        prompt = f"""You are a product data analyst. Filter and categorize these TF-IDF terms extracted from product listings.

{context}

Terms to process:
{json.dumps(phrases_to_process)}

STEP 1 - FILTER: Remove all terms that are NOT product attributes:
- Shipping/delivery (free delivery, standard shipping, express, dispatch, orders)
- Store/website names (any brand or retailer names)
- Pricing (price, sale, discount, offer, cheap, affordable)
- Generic marketing (best, top, new, popular, trending, must-have)
- Return/exchange policies (returned, exchanged, refund)
- Location/availability (australia, online, in stock, available)
- Sizing systems alone (au, us, uk) unless with actual size
- Random noise or incomplete phrases
Be aggressive - when in doubt, remove it.

STEP 2 - CATEGORIZE: Put each remaining term into ONE of these groups:
1. "Core Attributes" - Physical properties: size, dimensions, materials, colors, patterns, design features, fabric types, fits, styles
2. "Functional Terms" - Performance & benefits: durability, resistance, breathability, stretch, comfort, technical features
3. "Care Instructions" - Maintenance: washing, cleaning, ironing, drying instructions
4. "Compliance / Standards" - Certifications, safety standards, warranties (NOT shipping/delivery)

All filtered-out terms go in "Noise".

IMPORTANT RULES:
- Color names and patterns (e.g., "marle", "leo water", "stripe") go in "Core Attributes"
- Shipping/delivery terms go in "Noise" (e.g., "free delivery", "standard delivery")
- Care-related terms go in "Care Instructions" (e.g., "machine wash", "cold wash")
- Only actual certifications/standards go in "Compliance / Standards" (e.g., "ISO", "OEKO-TEX")

Return ONLY valid JSON in this exact format:
{{"Core Attributes": ["term1", "term2"], "Functional Terms": ["term3"], "Care Instructions": ["term4"], "Compliance / Standards": ["term5"], "Noise": ["term6", "term7"]}}

Include ALL terms from the input. Empty categories should be empty arrays []."""

        try:
            response = client.chat.completions.create(
                model=getattr(Config, 'ENTITY_LLM_MODEL', 'gpt-4o-mini'),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2000
            )

            content = response.choices[0].message.content.strip()

            # Handle markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            result = json.loads(content)

            # Extract noise terms
            noise = result.pop("Noise", [])

            # Remove empty categories
            grouped = {k: v for k, v in result.items() if v}

            total_grouped = sum(len(v) for v in grouped.values())
            logger.info(f"LLM clean+group: {len(phrases_to_process)} terms → {total_grouped} grouped, {len(noise)} noise (1 API call)")

            return grouped, noise

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM clean+group response: {e}")
            raise
        except Exception as e:
            logger.warning(f"LLM clean+group API call failed: {e}")
            raise

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
