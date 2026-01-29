"""
Deterministic rules engine for entity extraction.

Extracts structured entities from product data and TF-IDF terms using:
- Regex patterns for dimensions, standards, ratings
- Dictionary lookups for materials, finishes, environments
- Pattern matching for care/warranty information

Rules extraction runs first; LLM only fills gaps.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple

from ..models import EntityItem, Conflict
from ..logger import get_logger

logger = get_logger(__name__)


@dataclass
class RulesExtractionResult:
    """Result from rules-based entity extraction."""
    rule_entities: List[EntityItem] = field(default_factory=list)
    primary_entity_path: Optional[str] = None
    missing_types: List[str] = field(default_factory=list)
    conflicts: List[Conflict] = field(default_factory=list)
    confidence: float = 0.0
    notes: List[str] = field(default_factory=list)


class EntityRulesEngine:
    """
    Deterministic extraction of entities using rules and dictionaries.

    Extracts:
    - Dimensions (mm, cm, m, inch, kg, L, etc.)
    - Materials (from dictionary)
    - Finishes (from dictionary)
    - Standards & certifications (regex + dictionary)
    - Environments (from dictionary)
    - Care/warranty information (pattern matching)
    """

    # Entity types we attempt to extract
    ALL_ENTITY_TYPES = {
        'dimension', 'material', 'finish', 'standard',
        'certification', 'environment', 'care', 'warranty',
        'capacity', 'weight', 'rating'
    }

    # Critical types that should trigger LLM if missing
    CRITICAL_TYPES = {'material', 'dimension'}

    # Dimension patterns
    DIMENSION_PATTERNS = [
        # Width x Depth x Height patterns
        r'(\d+(?:\.\d+)?)\s*(mm|cm|m)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*(mm|cm|m)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*(mm|cm|m)',
        # Single dimension with label
        r'(\d+(?:\.\d+)?)\s*(mm|cm|m|inch|inches|")\s*(?:W|H|D|L|width|height|depth|length|diameter|dia)?',
        # Labeled dimension
        r'(?:width|height|depth|length|diameter|dia)[:\s]*(\d+(?:\.\d+)?)\s*(mm|cm|m|inch|inches|")',
    ]

    # Weight patterns
    WEIGHT_PATTERNS = [
        r'(\d+(?:\.\d+)?)\s*(kg|g|lb|lbs|pounds?)',
        r'(?:weight|weighs?)[:\s]*(\d+(?:\.\d+)?)\s*(kg|g|lb|lbs|pounds?)',
    ]

    # Capacity patterns
    CAPACITY_PATTERNS = [
        r'(\d+(?:\.\d+)?)\s*(L|l|litre|liter|litres|liters|ml|mL|gallon|gal)',
        r'(?:capacity|volume)[:\s]*(\d+(?:\.\d+)?)\s*(L|l|litre|liter|ml)',
    ]

    # Power/energy patterns
    POWER_PATTERNS = [
        r'(\d+(?:\.\d+)?)\s*(W|kW|watts?|kilowatts?)',
        r'(\d+(?:\.\d+)?)\s*(V|volts?)',
        r'(\d+(?:\.\d+)?)\s*(A|amps?|amperes?)',
        r'(\d+(?:\.\d+)?)\s*(MJ/?h?)',  # Gas rating
    ]

    # Standard patterns (regex)
    STANDARD_PATTERNS = [
        r'(AS/NZS\s*\d+(?:\.\d+)?)',
        r'(AS\s*\d+(?:\.\d+)?)',
        r'(NZS\s*\d+(?:\.\d+)?)',
        r'(ISO\s*\d+(?:[-:]\d+)?)',
        r'(IEC\s*\d+)',
        r'(EN\s*\d+)',
        r'(UL\s*\d+)',
        r'(IP\d{2})',
        r'(IPX\d)',
    ]

    # Care/warranty patterns
    CARE_PATTERNS = [
        r'(\d+)\s*(?:year|yr)s?\s*(?:warranty|guarantee)',
        r'(?:warranty|guarantee)[:\s]*(\d+)\s*(?:year|yr)s?',
        r'(lifetime)\s*(?:warranty|guarantee)',
        r'(wipe\s*clean)',
        r'(machine\s*wash)',
        r'(hand\s*wash)',
        r'(dry\s*clean)',
        r'(spot\s*clean)',
    ]

    # Primary entity keywords for path inference
    PRIMARY_ENTITY_KEYWORDS = {
        'Apparel': ['apparel', 'clothing', 'clothes', 'wear', 'shirt', 'short', 'shorts', 'pants', 'dress', 'jacket', 'coat', 'sweater', 'hoodie', 'top', 'bottom', 'skirt', 'legging', 'leggings', 'bike short', 'bike shorts', 'activewear', 'sportswear', 'athleisure', 'underwear', 'bra', 'sock', 'socks'],
        'Footwear': ['footwear', 'shoe', 'shoes', 'boot', 'boots', 'sneaker', 'sneakers', 'sandal', 'sandals', 'slipper', 'slippers', 'heel', 'heels', 'loafer', 'loafers', 'trainer', 'trainers'],
        'Accessories': ['accessory', 'accessories', 'bag', 'bags', 'handbag', 'purse', 'wallet', 'belt', 'hat', 'cap', 'scarf', 'glove', 'gloves', 'watch', 'jewelry', 'jewellery', 'sunglasses'],
        'Furniture': ['furniture', 'table', 'chair', 'sofa', 'bed', 'cabinet', 'desk', 'shelving', 'bench', 'stool', 'ottoman'],
        'Appliance': ['appliance', 'cooktop', 'stove', 'oven', 'cooker', 'rangehood', 'hood', 'dishwasher', 'refrigerator', 'microwave', 'freezer'],
        'Cookware': ['cookware', 'pan', 'pot', 'skillet', 'wok', 'stock pot', 'saucepan', 'frypan', 'bakeware'],
        'Flooring': ['flooring', 'floor', 'tile', 'laminate', 'vinyl', 'carpet', 'rug', 'timber floor'],
        'Textile': ['textile', 'fabric', 'cloth', 'curtain', 'bedding', 'cushion', 'throw', 'blanket', 'pillow'],
        'Hardware': ['hardware', 'handle', 'lock', 'hinge', 'fastener', 'bolt', 'knob', 'pull', 'tap', 'faucet'],
        'Lighting': ['light', 'lighting', 'lamp', 'bulb', 'fixture', 'pendant', 'chandelier', 'sconce', 'downlight'],
        'Outdoor': ['outdoor', 'patio', 'garden', 'landscape', 'bbq', 'barbecue', 'umbrella', 'gazebo'],
        'Storage': ['storage', 'shelf', 'rack', 'organizer', 'basket', 'container', 'box', 'bin'],
        'Decor': ['decor', 'decoration', 'art', 'mirror', 'vase', 'frame', 'ornament', 'sculpture'],
        'Electronics': ['electronic', 'electronics', 'computer', 'laptop', 'phone', 'tablet', 'tv', 'television', 'speaker', 'headphone', 'headphones', 'camera'],
        'Sports': ['sports', 'sport', 'fitness', 'gym', 'exercise', 'workout', 'yoga', 'cycling', 'running', 'swimming'],
    }

    # Materials that are NOT applicable for certain categories
    # Used to filter out irrelevant materials from TF-IDF noise
    EXCLUDED_MATERIALS_BY_CATEGORY = {
        'Apparel': ['stainless steel', 'steel', 'iron', 'aluminium', 'aluminum', 'brass', 'copper', 'bronze', 'granite', 'marble', 'concrete', 'glass', 'ceramic', 'porcelain', 'timber', 'oak', 'pine', 'teak', 'ash', 'walnut'],
        'Footwear': ['stainless steel', 'steel', 'iron', 'aluminium', 'aluminum', 'brass', 'copper', 'bronze', 'granite', 'marble', 'concrete', 'glass', 'ceramic', 'porcelain', 'timber', 'oak', 'pine', 'teak'],
        'Accessories': ['stainless steel', 'iron', 'aluminium', 'granite', 'marble', 'concrete', 'timber', 'oak', 'pine', 'teak'],
        'Sports': ['stainless steel', 'steel', 'iron', 'granite', 'marble', 'concrete', 'glass', 'porcelain', 'timber', 'oak', 'pine', 'teak', 'ash'],
    }

    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize rules engine with dictionaries.

        Args:
            data_dir: Path to data/ folder with JSON dictionaries.
                      Defaults to project root/data/
        """
        if data_dir is None:
            # Find data directory relative to this file
            data_dir = Path(__file__).parent.parent.parent.parent / "data"

        self.data_dir = data_dir
        self._materials: Dict = {}
        self._finishes: Dict = {}
        self._standards: Dict = {}
        self._environments: Dict = {}

        self._load_dictionaries()

    def _load_dictionaries(self) -> None:
        """Load JSON dictionaries from data folder."""
        try:
            materials_path = self.data_dir / "materials.json"
            if materials_path.exists():
                with open(materials_path, 'r', encoding='utf-8') as f:
                    self._materials = json.load(f)
                logger.info(f"Loaded materials dictionary: {len(self._materials)} categories")

            finishes_path = self.data_dir / "finishes.json"
            if finishes_path.exists():
                with open(finishes_path, 'r', encoding='utf-8') as f:
                    self._finishes = json.load(f)
                logger.info(f"Loaded finishes dictionary")

            standards_path = self.data_dir / "standards.json"
            if standards_path.exists():
                with open(standards_path, 'r', encoding='utf-8') as f:
                    self._standards = json.load(f)
                logger.info(f"Loaded standards dictionary")

            environments_path = self.data_dir / "environments.json"
            if environments_path.exists():
                with open(environments_path, 'r', encoding='utf-8') as f:
                    self._environments = json.load(f)
                logger.info(f"Loaded environments dictionary")

        except Exception as e:
            logger.warning(f"Error loading dictionaries: {e}")

    def extract(
        self,
        product_name: str,
        tfidf_terms: List[Dict],
        description: Optional[str] = None,
        search_query: Optional[str] = None
    ) -> RulesExtractionResult:
        """
        Extract entities using deterministic rules.

        Args:
            product_name: Product name/title
            tfidf_terms: List of TF-IDF term dicts with 'phrase' key
            description: Optional product description text
            search_query: Original search query for context awareness

        Returns:
            RulesExtractionResult with extracted entities and metadata
        """
        result = RulesExtractionResult()
        found_types: Set[str] = set()

        # Combine all text for searching
        all_text = self._build_search_text(product_name, tfidf_terms, description)
        term_phrases = [t.get('phrase', '').lower() for t in tfidf_terms if t.get('phrase')]

        # Determine product category early using search query for context filtering
        # Search query takes precedence over TF-IDF terms for category detection
        detected_category = self._detect_product_category(search_query or product_name)

        # Extract dimensions
        dimensions = self._extract_dimensions(all_text)
        result.rule_entities.extend(dimensions)
        if dimensions:
            found_types.add('dimension')

        # Extract weights
        weights = self._extract_weights(all_text)
        result.rule_entities.extend(weights)
        if weights:
            found_types.add('weight')

        # Extract capacities
        capacities = self._extract_capacities(all_text)
        result.rule_entities.extend(capacities)
        if capacities:
            found_types.add('capacity')

        # Extract power ratings
        power = self._extract_power(all_text)
        result.rule_entities.extend(power)
        if power:
            found_types.add('rating')

        # Extract materials (filtered by detected category to remove irrelevant ones)
        materials = self._extract_materials(all_text, term_phrases, detected_category)
        result.rule_entities.extend(materials)
        if materials:
            found_types.add('material')

        # Extract finishes
        finishes = self._extract_finishes(all_text, term_phrases)
        result.rule_entities.extend(finishes)
        if finishes:
            found_types.add('finish')

        # Extract standards & certifications
        standards = self._extract_standards(all_text, term_phrases)
        result.rule_entities.extend(standards)
        if standards:
            found_types.update({'standard', 'certification'})

        # Extract environments
        environments = self._extract_environments(all_text, term_phrases)
        result.rule_entities.extend(environments)
        if environments:
            found_types.add('environment')

        # Extract care/warranty
        care = self._extract_care(all_text, term_phrases)
        result.rule_entities.extend(care)
        if care:
            found_types.update({'care', 'warranty'})

        # Identify primary entity path (use search query for priority matching)
        result.primary_entity_path = self._identify_primary_entity(
            product_name, all_text, result.rule_entities, search_query
        )

        # Determine missing types
        result.missing_types = list(self.ALL_ENTITY_TYPES - found_types)

        # Detect internal conflicts
        result.conflicts = self._detect_conflicts(result.rule_entities)

        # Calculate confidence
        result.confidence = self._calculate_confidence(
            result.rule_entities,
            result.missing_types,
            result.conflicts
        )

        # Add notes
        result.notes.append(f"Extracted {len(result.rule_entities)} entities via rules")
        if result.conflicts:
            result.notes.append(f"Detected {len(result.conflicts)} potential conflicts")

        logger.info(
            f"Rules extraction complete: {len(result.rule_entities)} entities, "
            f"confidence={result.confidence:.2f}, missing={result.missing_types}"
        )

        return result

    def _build_search_text(
        self,
        product_name: str,
        tfidf_terms: List[Dict],
        description: Optional[str]
    ) -> str:
        """Build combined text for searching."""
        parts = [product_name.lower()]

        for term in tfidf_terms:
            phrase = term.get('phrase', '')
            if phrase:
                parts.append(phrase.lower())

        if description:
            parts.append(description.lower()[:2000])  # Limit description length

        return ' '.join(parts)

    def _extract_dimensions(self, text: str) -> List[EntityItem]:
        """Extract dimension entities using regex patterns."""
        entities = []
        seen = set()

        for pattern in self.DIMENSION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                groups = match.groups()
                if len(groups) >= 2:
                    value = groups[0]
                    unit = groups[1].lower()

                    # Normalize unit
                    if unit in ('"', 'inch', 'inches'):
                        unit = 'inch'

                    key = f"{value}{unit}"
                    if key not in seen:
                        seen.add(key)
                        entities.append(EntityItem(
                            name=f"{value}{unit}",
                            entity_type='dimension',
                            evidence=match.group(0),
                            source='rules',
                            value=value,
                            unit=unit,
                            why_it_matters="Product dimensions affect fit and suitability for intended space."
                        ))

        return entities[:5]  # Limit to top 5 dimensions

    def _extract_weights(self, text: str) -> List[EntityItem]:
        """Extract weight entities."""
        entities = []
        seen = set()

        for pattern in self.WEIGHT_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                groups = match.groups()
                if len(groups) >= 2:
                    value = groups[0]
                    unit = groups[1].lower()

                    # Normalize unit
                    if unit in ('lb', 'lbs', 'pound', 'pounds'):
                        unit = 'lb'
                    elif unit == 'g':
                        unit = 'g'
                    else:
                        unit = 'kg'

                    key = f"{value}{unit}"
                    if key not in seen:
                        seen.add(key)
                        entities.append(EntityItem(
                            name=f"{value}{unit}",
                            entity_type='weight',
                            evidence=match.group(0),
                            source='rules',
                            value=value,
                            unit=unit,
                            why_it_matters="Weight affects portability and structural requirements."
                        ))

        return entities[:2]

    def _extract_capacities(self, text: str) -> List[EntityItem]:
        """Extract capacity/volume entities."""
        entities = []
        seen = set()

        for pattern in self.CAPACITY_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                groups = match.groups()
                if len(groups) >= 2:
                    value = groups[0]
                    unit = groups[1].lower()

                    # Normalize unit
                    if unit in ('l', 'litre', 'liter', 'litres', 'liters'):
                        unit = 'L'
                    elif unit in ('ml', 'millilitre', 'milliliter'):
                        unit = 'mL'

                    key = f"{value}{unit}"
                    if key not in seen:
                        seen.add(key)
                        entities.append(EntityItem(
                            name=f"{value}{unit}",
                            entity_type='capacity',
                            evidence=match.group(0),
                            source='rules',
                            value=value,
                            unit=unit,
                            why_it_matters="Capacity determines how much the product can hold."
                        ))

        return entities[:2]

    def _extract_power(self, text: str) -> List[EntityItem]:
        """Extract power/energy rating entities."""
        entities = []
        seen = set()

        for pattern in self.POWER_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                groups = match.groups()
                if len(groups) >= 2:
                    value = groups[0]
                    unit = groups[1]

                    # Normalize unit
                    unit_lower = unit.lower()
                    if 'watt' in unit_lower or unit == 'W':
                        unit = 'W'
                    elif 'kw' in unit_lower or unit == 'kW':
                        unit = 'kW'
                    elif 'volt' in unit_lower or unit == 'V':
                        unit = 'V'
                    elif 'amp' in unit_lower or unit == 'A':
                        unit = 'A'
                    elif 'mj' in unit_lower.lower():
                        unit = 'MJ/h'

                    key = f"{value}{unit}"
                    if key not in seen:
                        seen.add(key)
                        entities.append(EntityItem(
                            name=f"{value}{unit}",
                            entity_type='rating',
                            evidence=match.group(0),
                            source='rules',
                            value=value,
                            unit=unit,
                            why_it_matters="Power rating indicates energy consumption and performance."
                        ))

        return entities[:3]

    def _extract_materials(
        self,
        text: str,
        term_phrases: List[str],
        detected_category: Optional[str] = None
    ) -> List[EntityItem]:
        """Extract material entities from dictionary lookup."""
        entities = []
        seen = set()

        # Get list of materials to exclude for this category
        excluded_materials = set()
        if detected_category and detected_category in self.EXCLUDED_MATERIALS_BY_CATEGORY:
            excluded_materials = {m.lower() for m in self.EXCLUDED_MATERIALS_BY_CATEGORY[detected_category]}

        # Search through all material categories
        for category, materials in self._materials.items():
            if not isinstance(materials, dict):
                continue

            for material_name, material_info in materials.items():
                if not isinstance(material_info, dict):
                    continue

                # Skip materials that don't make sense for the detected product category
                if material_name.lower() in excluded_materials:
                    continue

                # Check material name and aliases
                names_to_check = [material_name.lower()]
                aliases = material_info.get('aliases', [])
                if isinstance(aliases, list):
                    names_to_check.extend([a.lower() for a in aliases])

                # Also skip if any alias is in excluded list
                if any(alias in excluded_materials for alias in names_to_check):
                    continue

                for name in names_to_check:
                    if name in text and name not in seen:
                        # Find evidence
                        evidence = self._find_evidence(name, text)

                        seen.add(name)
                        seen.add(material_name.lower())  # Also mark canonical name

                        entities.append(EntityItem(
                            name=material_name.title(),
                            entity_type='material',
                            evidence=evidence,
                            source='rules',
                            why_it_matters=f"Material composition affects durability, maintenance, and appearance."
                        ))
                        break  # Found this material, move to next

        return entities[:5]  # Limit to 5 materials

    def _extract_finishes(
        self,
        text: str,
        term_phrases: List[str]
    ) -> List[EntityItem]:
        """Extract finish/coating entities from dictionary lookup."""
        entities = []
        seen = set()

        for category, finishes in self._finishes.items():
            if not isinstance(finishes, (dict, list)):
                continue

            # Handle both dict and list formats
            if isinstance(finishes, list):
                for finish_name in finishes:
                    if finish_name.lower() in text and finish_name.lower() not in seen:
                        evidence = self._find_evidence(finish_name.lower(), text)
                        seen.add(finish_name.lower())
                        entities.append(EntityItem(
                            name=finish_name.title(),
                            entity_type='finish',
                            evidence=evidence,
                            source='rules',
                            why_it_matters="Finish affects appearance, durability, and maintenance."
                        ))
            else:
                for finish_name, finish_info in finishes.items():
                    if not isinstance(finish_info, dict):
                        continue

                    names_to_check = [finish_name.lower()]
                    aliases = finish_info.get('aliases', [])
                    if isinstance(aliases, list):
                        names_to_check.extend([a.lower() for a in aliases])

                    for name in names_to_check:
                        if name in text and name not in seen:
                            evidence = self._find_evidence(name, text)
                            seen.add(name)
                            seen.add(finish_name.lower())

                            entities.append(EntityItem(
                                name=finish_name.title(),
                                entity_type='finish',
                                evidence=evidence,
                                source='rules',
                                why_it_matters="Finish affects appearance, durability, and maintenance."
                            ))
                            break

        return entities[:3]

    def _extract_standards(
        self,
        text: str,
        term_phrases: List[str]
    ) -> List[EntityItem]:
        """Extract standards and certifications using regex + dictionary."""
        entities = []
        seen = set()

        # First, check regex patterns
        for pattern in self.STANDARD_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                standard = match.group(1).upper()
                if standard not in seen:
                    seen.add(standard)

                    # Determine entity type
                    entity_type = 'standard'
                    if standard.startswith('IP'):
                        entity_type = 'rating'
                    elif any(cert in standard for cert in ['CE', 'UL']):
                        entity_type = 'certification'

                    # Look up description
                    description = self._lookup_standard_description(standard)

                    entities.append(EntityItem(
                        name=standard,
                        entity_type=entity_type,
                        evidence=match.group(0),
                        source='rules',
                        why_it_matters=description or "Compliance ensures product meets safety and quality standards."
                    ))

        # Check environmental certifications
        env_certs = self._standards.get('environmental', {}).get('certifications', {})
        if isinstance(env_certs, dict):
            for cert_name, cert_info in env_certs.items():
                if cert_name.lower() in text.lower() and cert_name not in seen:
                    seen.add(cert_name)
                    desc = cert_info.get('description', '') if isinstance(cert_info, dict) else ''
                    entities.append(EntityItem(
                        name=cert_name,
                        entity_type='certification',
                        evidence=self._find_evidence(cert_name.lower(), text),
                        source='rules',
                        why_it_matters=desc or "Environmental certification indicates sustainability commitment."
                    ))

        return entities[:5]

    def _lookup_standard_description(self, standard: str) -> Optional[str]:
        """Look up standard description from dictionary."""
        standard_upper = standard.upper()

        for region, data in self._standards.items():
            if not isinstance(data, dict):
                continue

            known = data.get('known', {})
            if isinstance(known, dict):
                for std_name, std_info in known.items():
                    if std_name.upper() == standard_upper:
                        if isinstance(std_info, dict):
                            return std_info.get('description')
                        return str(std_info)

        return None

    def _extract_environments(
        self,
        text: str,
        term_phrases: List[str]
    ) -> List[EntityItem]:
        """Extract environment/usage context entities."""
        entities = []
        seen = set()

        for category, environments in self._environments.items():
            if not isinstance(environments, dict):
                continue

            for env_name, env_info in environments.items():
                if not isinstance(env_info, dict):
                    continue

                names_to_check = [env_name.lower()]
                aliases = env_info.get('aliases', [])
                if isinstance(aliases, list):
                    names_to_check.extend([a.lower() for a in aliases])

                for name in names_to_check:
                    if name in text and name not in seen:
                        evidence = self._find_evidence(name, text)
                        seen.add(name)
                        seen.add(env_name.lower())

                        description = env_info.get('description', '')

                        entities.append(EntityItem(
                            name=env_name.title(),
                            entity_type='environment',
                            evidence=evidence,
                            source='rules',
                            why_it_matters=description or f"Product is designed for {env_name} conditions."
                        ))
                        break

        return entities[:4]

    def _extract_care(
        self,
        text: str,
        term_phrases: List[str]
    ) -> List[EntityItem]:
        """Extract care and warranty information."""
        entities = []
        seen = set()

        for pattern in self.CARE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                matched_text = match.group(0).lower().strip()

                if matched_text not in seen:
                    seen.add(matched_text)

                    # Determine entity type
                    if 'warranty' in matched_text or 'guarantee' in matched_text:
                        entity_type = 'warranty'
                        name = match.group(0).title()
                        why = "Warranty coverage provides peace of mind and protection."
                    else:
                        entity_type = 'care'
                        name = match.group(0).title()
                        why = "Care instructions help maintain product quality and lifespan."

                    entities.append(EntityItem(
                        name=name,
                        entity_type=entity_type,
                        evidence=match.group(0),
                        source='rules',
                        why_it_matters=why
                    ))

        return entities[:3]

    def _detect_product_category(self, text: str) -> Optional[str]:
        """
        Detect the product category from text (search query or product name).
        Used for filtering irrelevant materials and entities.
        """
        if not text:
            return None

        text_lower = text.lower()

        # Score each category based on keyword matches
        scores = {}
        for category, keywords in self.PRIMARY_ENTITY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in text_lower)
            if score > 0:
                scores[category] = score

        if not scores:
            return None

        # Return the highest scoring category
        return max(scores, key=scores.get)

    def _identify_primary_entity(
        self,
        product_name: str,
        all_text: str,
        entities: List[EntityItem],
        search_query: Optional[str] = None
    ) -> str:
        """Identify primary product entity path."""
        # IMPORTANT: Prioritize search query over TF-IDF contaminated text
        # The search query tells us what the user was actually looking for
        if search_query:
            query_category = self._detect_product_category(search_query)
            if query_category:
                # Use search query to determine category
                subtype = self._infer_subtype(query_category, search_query.lower(), entities)
                if subtype:
                    return f"{query_category} > {subtype}"
                # Try to use part of the search query as subtype
                # e.g., "bike short with side pocket" -> "Apparel > Bike Short"
                clean_query = search_query.title()
                return f"{query_category} > {clean_query}"

        # Fallback to analyzing all text (may be contaminated with unrelated terms)
        search_text = all_text.lower()

        # Score each primary entity type
        scores = {}
        for entity_type, keywords in self.PRIMARY_ENTITY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in search_text)
            if score > 0:
                scores[entity_type] = score

        if not scores:
            return f"Product > {product_name.title()}"

        # Get top scoring entity
        top_entity = max(scores, key=scores.get)

        # Try to infer subtype
        subtype = self._infer_subtype(top_entity, search_text, entities)

        if subtype:
            return f"{top_entity} > {subtype}"
        return top_entity

    def _infer_subtype(
        self,
        entity_type: str,
        text: str,
        entities: List[EntityItem]
    ) -> Optional[str]:
        """Infer a more specific subtype for the primary entity."""
        subtype_hints = {
            'Apparel': {
                'bike short': 'Bike Short',
                'bike shorts': 'Bike Shorts',
                'legging': 'Leggings',
                'leggings': 'Leggings',
                'yoga pant': 'Yoga Pants',
                'yoga pants': 'Yoga Pants',
                'running short': 'Running Shorts',
                'dress': 'Dress',
                'shirt': 'Shirt',
                't-shirt': 'T-Shirt',
                'jacket': 'Jacket',
                'hoodie': 'Hoodie',
                'sweater': 'Sweater',
                'jeans': 'Jeans',
                'shorts': 'Shorts',
                'pants': 'Pants',
                'skirt': 'Skirt',
                'blouse': 'Blouse',
                'top': 'Top',
                'bra': 'Sports Bra',
                'sports bra': 'Sports Bra',
            },
            'Footwear': {
                'running shoe': 'Running Shoes',
                'sneaker': 'Sneakers',
                'boot': 'Boots',
                'sandal': 'Sandals',
                'heel': 'Heels',
                'loafer': 'Loafers',
                'trainer': 'Trainers',
            },
            'Sports': {
                'yoga': 'Yoga',
                'cycling': 'Cycling',
                'running': 'Running',
                'fitness': 'Fitness',
                'gym': 'Gym',
                'swimming': 'Swimming',
            },
            'Appliance': {
                'induction': 'Induction Cooktop',
                'gas': 'Gas Cooktop',
                'electric': 'Electric Cooktop',
                'rangehood': 'Rangehood',
                'oven': 'Oven',
                'microwave': 'Microwave',
            },
            'Furniture': {
                'coffee table': 'Coffee Table',
                'dining': 'Dining',
                'console': 'Console',
                'side table': 'Side Table',
                'desk': 'Desk',
                'chair': 'Chair',
                'sofa': 'Sofa',
                'bed': 'Bed',
            },
            'Cookware': {
                'non-stick': 'Non-Stick',
                'stainless': 'Stainless Steel',
                'cast iron': 'Cast Iron',
                'ceramic': 'Ceramic',
            },
            'Lighting': {
                'pendant': 'Pendant',
                'floor lamp': 'Floor Lamp',
                'table lamp': 'Table Lamp',
                'downlight': 'Downlight',
                'chandelier': 'Chandelier',
            },
        }

        hints = subtype_hints.get(entity_type, {})
        for keyword, subtype in hints.items():
            if keyword in text:
                return subtype

        return None

    def _find_evidence(self, term: str, text: str, context_chars: int = 50) -> str:
        """Find evidence snippet containing the term."""
        idx = text.lower().find(term.lower())
        if idx == -1:
            return term

        start = max(0, idx - context_chars)
        end = min(len(text), idx + len(term) + context_chars)

        evidence = text[start:end].strip()
        if start > 0:
            evidence = "..." + evidence
        if end < len(text):
            evidence = evidence + "..."

        return evidence

    def _detect_conflicts(self, entities: List[EntityItem]) -> List[Conflict]:
        """Detect internal conflicts within rules extraction."""
        conflicts = []

        # Group entities by type
        by_type: Dict[str, List[EntityItem]] = {}
        for entity in entities:
            if entity.entity_type not in by_type:
                by_type[entity.entity_type] = []
            by_type[entity.entity_type].append(entity)

        # Check for conflicting materials (e.g., both "indoor" and "outdoor only")
        if 'environment' in by_type:
            envs = [e.name.lower() for e in by_type['environment']]
            if 'indoor' in envs and 'outdoor' in envs and 'indoor/outdoor' not in envs:
                conflicts.append(Conflict(
                    entity_type='environment',
                    rule_value='indoor',
                    llm_value='outdoor',
                    resolution='manual_review',
                    reason="Both indoor and outdoor mentioned; may be indoor/outdoor"
                ))

        return conflicts

    def _calculate_confidence(
        self,
        entities: List[EntityItem],
        missing_types: List[str],
        conflicts: List[Conflict]
    ) -> float:
        """
        Calculate extraction confidence score.

        Factors:
        - Number of entities found
        - Whether critical types are covered
        - Presence of conflicts
        """
        if not entities:
            return 0.1

        # Start with base score based on entities found
        score = min(0.5 + (len(entities) * 0.05), 0.8)

        # Penalize for missing critical types
        critical_missing = [t for t in missing_types if t in self.CRITICAL_TYPES]
        score -= len(critical_missing) * 0.15

        # Penalize for conflicts
        score -= len(conflicts) * 0.1

        # Ensure score is in valid range
        return max(0.1, min(1.0, score))
