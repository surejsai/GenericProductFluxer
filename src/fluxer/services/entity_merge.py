"""
Entity merge logic for combining rules and LLM extraction results.

Handles:
- Deduplication by (type, normalized_name)
- Rules preference over LLM
- Conflict detection
- Final confidence calculation
- Brand name filtering
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Optional

from ..models import EntityItem, Conflict
from ..logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Brand Name Filtering
# =============================================================================

class BrandFilter:
    """
    Filter brand names from entity extraction results.

    Ensures output is generic product information without brand-specific content.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize brand filter with data directory."""
        if data_dir is None:
            # Default to data/ folder relative to project root
            data_dir = Path(__file__).parent.parent.parent.parent / "data"

        self.data_dir = data_dir
        self._brands: Set[str] = set()
        self._patterns: List[str] = []
        self._load_brands()

    def _load_brands(self) -> None:
        """Load brand names from JSON file."""
        brands_file = self.data_dir / "brands.json"

        if not brands_file.exists():
            logger.warning(f"Brands file not found: {brands_file}")
            return

        try:
            with open(brands_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Collect all brands from all categories
            for category, brands in data.items():
                if category == "common_patterns":
                    self._patterns = [p.lower() for p in brands]
                elif isinstance(brands, list):
                    for brand in brands:
                        self._brands.add(brand.lower().strip())

            logger.info(f"Loaded {len(self._brands)} brand names for filtering")

        except Exception as e:
            logger.error(f"Failed to load brands: {e}")

    def contains_brand(self, text: str) -> bool:
        """Check if text contains a brand name."""
        if not text:
            return False

        text_lower = text.lower()

        # Check exact brand matches (with word boundaries)
        for brand in self._brands:
            # Match brand as whole word
            pattern = r'\b' + re.escape(brand) + r'\b'
            if re.search(pattern, text_lower):
                return True

        return False

    def is_brand_only(self, text: str) -> bool:
        """Check if text is just a brand name (nothing useful left after removal)."""
        cleaned = self.remove_brands(text)
        # If after removing brands, only whitespace or very short text remains
        return len(cleaned.strip()) < 3

    def remove_brands(self, text: str) -> str:
        """
        Remove brand names from text.

        Args:
            text: Text that may contain brand names

        Returns:
            Text with brand names removed
        """
        if not text:
            return text

        result = text

        # Sort brands by length (longest first) to avoid partial matches
        sorted_brands = sorted(self._brands, key=len, reverse=True)

        for brand in sorted_brands:
            # Match brand as whole word (case-insensitive)
            pattern = re.compile(r'\b' + re.escape(brand) + r'\b', re.IGNORECASE)
            result = pattern.sub('', result)

        # Remove common patterns (pty ltd, etc.)
        for pattern in self._patterns:
            pat = re.compile(r'\b' + re.escape(pattern) + r'\b', re.IGNORECASE)
            result = pat.sub('', result)

        # Clean up extra whitespace and punctuation
        result = re.sub(r'\s+', ' ', result)
        result = re.sub(r'^[\s\-,]+|[\s\-,]+$', '', result)
        result = re.sub(r'\s*[,\-]\s*[,\-]\s*', ' ', result)

        return result.strip()

    def clean_entity_path(self, path: str) -> str:
        """
        Clean brand names from entity path.

        Args:
            path: Entity path like "Appliance > Brand > Oven"

        Returns:
            Cleaned path without brand names
        """
        if not path:
            return path

        # Split by common separators
        parts = re.split(r'\s*[>›»]\s*', path)

        # Clean each part and filter out brand-only parts
        cleaned_parts = []
        for part in parts:
            cleaned = self.remove_brands(part)
            if cleaned and len(cleaned) >= 2:
                cleaned_parts.append(cleaned)

        # Rejoin
        return ' > '.join(cleaned_parts) if cleaned_parts else path

    def clean_product_name(self, name: str) -> str:
        """
        Clean brand names from product name while preserving useful info.

        Args:
            name: Product name like "Hisense 20L Microwave Oven"

        Returns:
            Cleaned name like "20L Microwave Oven"
        """
        return self.remove_brands(name)


@dataclass
class MergeResult:
    """Result from merging rules and LLM entities."""
    merged_entities: List[EntityItem] = field(default_factory=list)
    conflicts: List[Conflict] = field(default_factory=list)
    confidence: float = 0.0
    notes: List[str] = field(default_factory=list)


class EntityMerger:
    """
    Merge and deduplicate entities from rules and LLM extraction.

    Strategy:
    - Deduplicate by (type, normalized_name)
    - Prefer rules-extracted entities over LLM
    - Detect and record conflicts
    - Calculate final confidence score
    - Filter out brand names for generic output
    """

    def __init__(self, filter_brands: bool = True):
        """
        Initialize the entity merger.

        Args:
            filter_brands: Whether to filter brand names from output
        """
        self.filter_brands = filter_brands
        self._brand_filter: Optional[BrandFilter] = None

        if filter_brands:
            self._brand_filter = BrandFilter()

    # Name normalization mappings
    NAME_NORMALIZATIONS = {
        # Material variations
        'aluminum': 'aluminium',
        'ss': 'stainless steel',
        '304 stainless': 'stainless steel',
        '316 stainless': 'stainless steel',
        'alu': 'aluminium',
        # Finish variations
        'powder-coated': 'powder coated',
        'powdercoated': 'powder coated',
        'anodized': 'anodised',
        'galvanized': 'galvanised',
        'matt': 'matte',
        # Environment variations
        'indoors': 'indoor',
        'outdoors': 'outdoor',
        'exterior': 'outdoor',
        'interior': 'indoor',
    }

    def merge(
        self,
        rule_entities: List[EntityItem],
        llm_entities: List[EntityItem],
        rules_confidence: float = 0.5,
        llm_confidence: float = 0.5
    ) -> MergeResult:
        """
        Merge entities from rules and LLM extraction.

        Args:
            rule_entities: Entities from rules extraction
            llm_entities: Entities from LLM extraction
            rules_confidence: Confidence score from rules
            llm_confidence: Confidence score from LLM

        Returns:
            MergeResult with deduplicated entities and conflicts
        """
        result = MergeResult()

        # Detect conflicts between rules and LLM
        result.conflicts = self._detect_conflicts(rule_entities, llm_entities)

        # Build merged list with rules preference
        seen_keys: Set[str] = set()
        merged: List[EntityItem] = []

        # First, add all rules entities
        for entity in rule_entities:
            key = self._make_key(entity)
            if key not in seen_keys:
                seen_keys.add(key)
                merged.append(entity)

        # Then, add LLM entities that don't conflict
        for entity in llm_entities:
            key = self._make_key(entity)
            if key not in seen_keys:
                # Check if this type has a conflict
                type_has_conflict = any(
                    c.entity_type == entity.entity_type
                    for c in result.conflicts
                )

                if not type_has_conflict:
                    seen_keys.add(key)
                    merged.append(entity)
                else:
                    result.notes.append(
                        f"Skipped LLM entity '{entity.name}' due to conflict in type '{entity.entity_type}'"
                    )

        # Apply brand filtering if enabled
        if self.filter_brands and self._brand_filter:
            merged = self._filter_brand_entities(merged, result)

        result.merged_entities = merged

        # Calculate final confidence
        result.confidence = self._calculate_final_confidence(
            rules_confidence,
            llm_confidence,
            len(rule_entities),
            len(llm_entities),
            len(result.conflicts)
        )

        result.notes.append(
            f"Merged {len(rule_entities)} rules + {len(llm_entities)} LLM → "
            f"{len(merged)} entities ({len(result.conflicts)} conflicts)"
        )

        logger.info(
            f"Merge complete: {len(merged)} entities, "
            f"{len(result.conflicts)} conflicts, confidence={result.confidence:.2f}"
        )

        return result

    def _make_key(self, entity: EntityItem) -> str:
        """Create deduplication key from entity."""
        normalized_name = self._normalize_name(entity.name)
        return f"{entity.entity_type}:{normalized_name}"

    def _normalize_name(self, name: str) -> str:
        """
        Normalize entity name for comparison.

        - Lowercase
        - Remove special characters
        - Apply known mappings
        """
        # Lowercase
        normalized = name.lower().strip()

        # Remove special characters but keep spaces
        normalized = re.sub(r'[^\w\s-]', '', normalized)

        # Apply known normalizations
        for variant, canonical in self.NAME_NORMALIZATIONS.items():
            if normalized == variant or normalized.startswith(variant + ' '):
                normalized = normalized.replace(variant, canonical, 1)
                break

        # Remove extra whitespace
        normalized = ' '.join(normalized.split())

        return normalized

    def _detect_conflicts(
        self,
        rule_entities: List[EntityItem],
        llm_entities: List[EntityItem]
    ) -> List[Conflict]:
        """
        Detect conflicts between rules and LLM extraction.

        A conflict occurs when:
        - Same entity type has different values
        - Both sources provide material/finish but they differ
        """
        conflicts = []

        # Group by type
        rules_by_type = self._group_by_type(rule_entities)
        llm_by_type = self._group_by_type(llm_entities)

        # Check for conflicts in each type
        for entity_type in set(rules_by_type.keys()) & set(llm_by_type.keys()):
            rule_names = {self._normalize_name(e.name) for e in rules_by_type[entity_type]}
            llm_names = {self._normalize_name(e.name) for e in llm_by_type[entity_type]}

            # For material and finish, different values is a conflict
            if entity_type in ('material', 'finish'):
                if rule_names and llm_names and not rule_names & llm_names:
                    # They have different values
                    rule_example = list(rules_by_type[entity_type])[0].name
                    llm_example = list(llm_by_type[entity_type])[0].name

                    conflicts.append(Conflict(
                        entity_type=entity_type,
                        rule_value=rule_example,
                        llm_value=llm_example,
                        resolution='prefer_rules',
                        reason=f"Rules extracted '{rule_example}' but LLM suggested '{llm_example}'. Preferring rules."
                    ))

            # For environment, contradictions like indoor vs outdoor
            elif entity_type == 'environment':
                rule_indoor = any('indoor' in n for n in rule_names)
                rule_outdoor = any('outdoor' in n for n in rule_names)
                llm_indoor = any('indoor' in n for n in llm_names)
                llm_outdoor = any('outdoor' in n for n in llm_names)

                if (rule_indoor and llm_outdoor and not rule_outdoor) or \
                   (rule_outdoor and llm_indoor and not rule_indoor):
                    conflicts.append(Conflict(
                        entity_type='environment',
                        rule_value='indoor' if rule_indoor else 'outdoor',
                        llm_value='indoor' if llm_indoor else 'outdoor',
                        resolution='prefer_rules',
                        reason="Conflicting environment settings. Preferring rules extraction."
                    ))

        return conflicts

    def _group_by_type(self, entities: List[EntityItem]) -> Dict[str, List[EntityItem]]:
        """Group entities by their type."""
        by_type: Dict[str, List[EntityItem]] = {}
        for entity in entities:
            if entity.entity_type not in by_type:
                by_type[entity.entity_type] = []
            by_type[entity.entity_type].append(entity)
        return by_type

    def _calculate_final_confidence(
        self,
        rules_confidence: float,
        llm_confidence: float,
        rules_count: int,
        llm_count: int,
        conflict_count: int
    ) -> float:
        """
        Calculate final confidence score after merge.

        Factors:
        - Weighted average of rules and LLM confidence
        - Rules weighted higher (more trustworthy)
        - Penalty for conflicts
        - Bonus if both sources agree
        """
        if rules_count == 0 and llm_count == 0:
            return 0.1

        # Base: weighted average with rules weighted 2:1
        if llm_count > 0:
            total_weight = rules_count * 2 + llm_count
            weighted = (rules_confidence * rules_count * 2 + llm_confidence * llm_count) / total_weight
        else:
            weighted = rules_confidence

        # Penalty for conflicts
        weighted -= conflict_count * 0.1

        # Small bonus if we have both rules and LLM agreeing
        if rules_count > 0 and llm_count > 0 and conflict_count == 0:
            weighted += 0.05

        return max(0.1, min(1.0, weighted))

    def deduplicate(self, entities: List[EntityItem]) -> List[EntityItem]:
        """
        Deduplicate a list of entities.

        Keeps first occurrence of each (type, normalized_name) pair.
        """
        seen: Set[str] = set()
        result = []

        for entity in entities:
            key = self._make_key(entity)
            if key not in seen:
                seen.add(key)
                result.append(entity)

        return result

    def _filter_brand_entities(
        self,
        entities: List[EntityItem],
        result: MergeResult
    ) -> List[EntityItem]:
        """
        Filter brand names from entity names and remove brand-only entities.

        Args:
            entities: List of entities to filter
            result: MergeResult to add notes to

        Returns:
            Filtered list of entities
        """
        if not self._brand_filter:
            return entities

        filtered = []
        for entity in entities:
            # Check if entity name is brand-only
            if self._brand_filter.is_brand_only(entity.name):
                result.notes.append(
                    f"Filtered out brand-only entity: '{entity.name}'"
                )
                continue

            # Clean brand names from entity name
            cleaned_name = self._brand_filter.remove_brands(entity.name)

            if cleaned_name != entity.name:
                # Create new entity with cleaned name
                entity = EntityItem(
                    name=cleaned_name,
                    entity_type=entity.entity_type,
                    evidence=entity.evidence,
                    source=entity.source,
                    value=entity.value,
                    unit=entity.unit,
                    why_it_matters=entity.why_it_matters
                )

            filtered.append(entity)

        if len(filtered) < len(entities):
            result.notes.append(
                f"Brand filtering removed {len(entities) - len(filtered)} entities"
            )

        return filtered

    def clean_entity_path(self, path: str) -> str:
        """
        Clean brand names from entity path.

        Args:
            path: Entity path like "Appliance > Brand > Oven"

        Returns:
            Cleaned path without brand names
        """
        if self._brand_filter:
            return self._brand_filter.clean_entity_path(path)
        return path

    def clean_product_name(self, name: str) -> str:
        """
        Clean brand names from product name.

        Args:
            name: Product name like "Hisense 20L Microwave"

        Returns:
            Cleaned name like "20L Microwave"
        """
        if self._brand_filter:
            return self._brand_filter.clean_product_name(name)
        return name
