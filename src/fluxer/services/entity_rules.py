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
from functools import lru_cache
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple, Any

from ..models import EntityItem, Conflict
from ..config import Config
from ..logger import get_logger

logger = get_logger(__name__)

# Check OpenAI availability for dynamic subtype inference
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.info("OpenAI not available for dynamic subtype inference. Using fallback.")


# =============================================================================
# Global OpenAI client (lazy initialization)
# =============================================================================
_openai_client: Optional[Any] = None


def _get_openai_client() -> Optional[Any]:
    """Get or initialize the OpenAI client."""
    global _openai_client
    if _openai_client is None and OPENAI_AVAILABLE:
        api_key = Config.OPENAI_API_KEY
        if api_key:
            _openai_client = OpenAI(api_key=api_key)
            logger.info("OpenAI client initialized for dynamic subtype inference")
    return _openai_client


# =============================================================================
# Cached subtype inference using OpenAI
# =============================================================================
@lru_cache(maxsize=256)
def _infer_subtype_from_llm(category: str, text: str) -> Optional[str]:
    """
    Use OpenAI to dynamically infer the product subtype.

    Cached to avoid repeated API calls for the same (category, text) pair.

    Args:
        category: The detected product category (e.g., "Food", "Apparel")
        text: The search query or product description text

    Returns:
        Inferred subtype string or None if inference fails
    """
    client = _get_openai_client()
    if client is None:
        return None

    # Use a short, efficient prompt
    prompt = f"""Given the product category "{category}" and search text "{text}", identify the most specific product subtype.

Return ONLY the subtype name (1-3 words, title case). Examples:
- For Food + "pocky chocolate sticks" → "Snack Stick"
- For Drinkware + "ceramic coffee mug" → "Coffee Mug"
- For Apparel + "women's bike shorts" → "Bike Shorts"
- For Appliance + "gas cooktop 5 burner" → "Gas Cooktop"

If you cannot determine a specific subtype, respond with just "General".

Subtype for {category} + "{text}":"""

    try:
        response = client.chat.completions.create(
            model=getattr(Config, 'ENTITY_LLM_MODEL', 'gpt-4o-mini'),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=20
        )

        subtype = response.choices[0].message.content.strip()

        # Clean up the response
        subtype = subtype.strip('"\'.')

        # Reject overly generic or invalid responses
        if not subtype or subtype.lower() in ('general', 'unknown', 'n/a', 'none'):
            return None

        # Ensure title case
        subtype = subtype.title()

        logger.debug(f"Dynamic subtype inference: {category} + '{text[:30]}...' → {subtype}")
        return subtype

    except Exception as e:
        logger.warning(f"Dynamic subtype inference failed: {e}")
        return None


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
        'Food': ['food', 'snack', 'snacks', 'candy', 'candies', 'chocolate', 'biscuit', 'biscuits', 'cookie', 'cookies', 'confectionery', 'confection', 'treat', 'treats', 'sweet', 'sweets', 'lolly', 'lollies', 'pocky', 'chips', 'crisps', 'crackers', 'cracker', 'wafer', 'wafers', 'gummy', 'gummies', 'caramel', 'toffee', 'fudge', 'mints', 'mint', 'licorice', 'liquorice', 'marshmallow', 'nougat', 'praline', 'truffle', 'bonbon', 'jellybean', 'lollipop', 'hard candy', 'chewy', 'crunchy', 'crispy', 'edible', 'flavour', 'flavor', 'strawberry', 'matcha', 'vanilla', 'cocoa', 'hazelnut'],
        'Drinkware': ['cup', 'cups', 'mug', 'mugs', 'glass', 'glasses', 'tumbler', 'tumblers', 'drinkware', 'goblet', 'goblets', 'wine glass', 'champagne flute', 'beer glass', 'coffee cup', 'tea cup', 'espresso cup', 'travel mug', 'sippy cup', 'shot glass', 'highball', 'lowball', 'pint glass', 'stemware', 'glassware'],
        'Apparel': ['apparel', 'clothing', 'clothes', 'wear', 'shirt', 'short', 'shorts', 'pants', 'dress', 'jacket', 'coat', 'sweater', 'hoodie', 'tank top', 'blouse top', 'crop top', 'bottom', 'skirt', 'legging', 'leggings', 'bike short', 'bike shorts', 'activewear', 'sportswear', 'athleisure', 'underwear', 'bra', 'sock', 'socks', 'swimwear', 'swimsuit', 'swim short', 'swim shorts', 'swim trunk', 'swim trunks', 'board short', 'board shorts', 'bikini', 'rashie', 'rash guard', 'wetsuit', 'trunks', 'briefs', 'boxer', 'boxers'],
        'Footwear': ['footwear', 'shoe', 'shoes', 'boot', 'boots', 'sneaker', 'sneakers', 'sandal', 'sandals', 'slipper', 'slippers', 'heel', 'heels', 'loafer', 'loafers', 'trainer', 'trainers'],
        'Accessories': ['accessory', 'accessories', 'bag', 'bags', 'handbag', 'purse', 'wallet', 'belt', 'hat', 'cap', 'scarf', 'glove', 'gloves', 'watch', 'jewelry', 'jewellery', 'sunglasses'],
        'Furniture': ['furniture', 'table', 'chair', 'sofa', 'bed', 'cabinet', 'desk', 'shelving', 'bench', 'stool', 'ottoman'],
        'Appliance': ['appliance', 'cooktop', 'stove', 'oven', 'cooker', 'rangehood', 'hood', 'dishwasher', 'refrigerator', 'freezer', 'microwave oven', 'microwave appliance'],
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

    # Keywords that should be IGNORED when they appear in compound phrases
    # e.g., "microwave safe" should not trigger Appliance category
    # e.g., "cool iron" should not trigger Iron material (it's a care instruction)
    COMPOUND_PHRASE_EXCLUSIONS = {
        'microwave': ['microwave safe', 'microwave friendly', 'microwave proof', 'microwave-safe'],
    }

    # Material names that should be excluded when they appear in care/laundry instruction contexts
    # "iron" as an action (ironing clothes) vs "iron" as a material (the metal)
    CARE_INSTRUCTION_MATERIAL_EXCLUSIONS = {
        'iron': [
            'cool iron', 'warm iron', 'hot iron', 'steam iron', 'no iron', 'do not iron',
            'iron reverse', 'reverse iron', 'iron inside', 'iron on reverse',
            'iron low', 'iron medium', 'iron high', 'iron setting',
            'softener iron', 'softener cool iron', 'iron reverse dry',
            'line dry iron', 'tumble dry iron', 'dry clean iron',
        ],
        'ash': [
            'wash', 'machine wash', 'hand wash', 'cold wash', 'warm wash',  # "wash" contains "ash"
        ],
    }

    # Materials that NEVER make sense for textile/apparel products
    # These are always excluded regardless of specific category when text contains textile keywords
    TEXTILE_IMPOSSIBLE_MATERIALS = {
        'stainless steel', 'steel', 'iron', 'aluminium', 'aluminum', 'brass', 'copper',
        'bronze', 'granite', 'marble', 'concrete', 'glass', 'ceramic', 'porcelain',
        'timber', 'oak', 'pine', 'teak', 'ash', 'walnut', 'maple', 'birch', 'mahogany',
        'chrome', 'nickel', 'zinc', 'tin', 'lead', 'pewter', 'cast iron',
    }

    # Short material names that require STRICT word boundary matching
    # to avoid false positives like "ash" in "wash" or "tin" in "satin"
    STRICT_WORD_BOUNDARY_MATERIALS = {
        'ash',  # falsely matches "wash", "crash", "flash", "splash"
        'tin',  # falsely matches "satin", "latin", "martin"
        'oak',  # falsely matches "soak", "cloak"
        'gel',  # falsely matches "angel"
        'ice',  # falsely matches "price", "service", "nice"
    }

    # Keywords that indicate the product is a textile/apparel item
    TEXTILE_INDICATOR_KEYWORDS = {
        'shirt', 'shorts', 'pants', 'dress', 'jacket', 'coat', 'sweater', 'hoodie',
        'skirt', 'legging', 'top', 'bottom', 'swim', 'swimwear', 'swimsuit', 'bikini',
        'trunks', 'underwear', 'bra', 'sock', 'apparel', 'clothing', 'wear', 'garment',
        'fabric', 'cotton', 'polyester', 'nylon', 'spandex', 'lycra', 'elastic',
        'waistband', 'drawstring', 'pocket', 'seam', 'hem', 'sleeve', 'collar',
    }

    # Materials that are NOT applicable for certain categories
    # Used to filter out irrelevant materials from TF-IDF noise
    EXCLUDED_MATERIALS_BY_CATEGORY = {
        'Food': ['stainless steel', 'steel', 'iron', 'aluminium', 'aluminum', 'brass', 'copper', 'bronze', 'granite', 'marble', 'concrete', 'glass', 'ceramic', 'porcelain', 'timber', 'oak', 'pine', 'teak', 'ash', 'walnut', 'leather', 'polyester', 'nylon', 'cotton', 'wool', 'silk', 'linen', 'velvet', 'suede', 'denim', 'lycra', 'spandex', 'acrylic', 'vinyl', 'rubber'],
        'Drinkware': ['steel', 'iron', 'aluminium', 'aluminum', 'brass', 'copper', 'bronze', 'granite', 'marble', 'concrete', 'timber', 'oak', 'pine', 'teak', 'ash', 'walnut', 'leather', 'polyester', 'nylon', 'cotton', 'wool', 'silk', 'linen', 'velvet', 'suede', 'denim', 'lycra', 'spandex', 'vinyl', 'rubber'],
        'Apparel': ['stainless steel', 'steel', 'iron', 'aluminium', 'aluminum', 'brass', 'copper', 'bronze', 'granite', 'marble', 'concrete', 'glass', 'ceramic', 'porcelain', 'timber', 'oak', 'pine', 'teak', 'ash', 'walnut', 'maple', 'birch', 'mahogany', 'chrome', 'nickel', 'zinc'],
        'Footwear': ['stainless steel', 'steel', 'iron', 'aluminium', 'aluminum', 'brass', 'copper', 'bronze', 'granite', 'marble', 'concrete', 'glass', 'ceramic', 'porcelain', 'timber', 'oak', 'pine', 'teak', 'ash'],
        'Accessories': ['stainless steel', 'iron', 'aluminium', 'granite', 'marble', 'concrete', 'timber', 'oak', 'pine', 'teak', 'ash'],
        'Sports': ['stainless steel', 'steel', 'iron', 'granite', 'marble', 'concrete', 'glass', 'porcelain', 'timber', 'oak', 'pine', 'teak', 'ash', 'walnut', 'maple'],
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

    def _is_material_in_care_context(self, material_name: str, text: str) -> bool:
        """
        Check if a material name appears only in care instruction contexts.

        E.g., "iron" in "cool iron" or "iron reverse" is a care instruction,
        not the metal material.

        Args:
            material_name: The material name to check (e.g., "iron")
            text: The full text to search in

        Returns:
            True if the material appears ONLY in care instruction contexts
        """
        material_lower = material_name.lower()
        text_lower = text.lower()

        # Check if this material has care instruction exclusions
        exclusion_patterns = self.CARE_INSTRUCTION_MATERIAL_EXCLUSIONS.get(material_lower, [])
        if not exclusion_patterns:
            return False

        # Find all occurrences of the material in the text
        # Check if EVERY occurrence is part of a care instruction phrase
        import re
        material_pattern = r'\b' + re.escape(material_lower) + r'\b'
        matches = list(re.finditer(material_pattern, text_lower))

        if not matches:
            return False

        # For each occurrence, check if it's part of a care instruction phrase
        all_in_care_context = True
        for match in matches:
            match_start = match.start()
            match_end = match.end()

            # Get surrounding context (50 chars before and after)
            context_start = max(0, match_start - 50)
            context_end = min(len(text_lower), match_end + 50)
            context = text_lower[context_start:context_end]

            # Check if this occurrence is part of any care instruction pattern
            in_care_context = False
            for pattern in exclusion_patterns:
                if pattern.lower() in context:
                    in_care_context = True
                    break

            if not in_care_context:
                all_in_care_context = False
                break

        return all_in_care_context

    def _is_textile_product(self, text: str) -> bool:
        """
        Check if the text indicates a textile/apparel product.

        Uses TEXTILE_INDICATOR_KEYWORDS to detect textile products even if
        the category detection might miss them.
        """
        text_lower = text.lower()
        words = set(text_lower.split())

        # Check for textile indicator keywords
        for keyword in self.TEXTILE_INDICATOR_KEYWORDS:
            # Whole word match
            if keyword in words:
                return True
            # Substring match for compound words (e.g., "swimshorts")
            if keyword in text_lower:
                return True

        return False

    def _is_whole_word_match(self, word: str, text: str) -> bool:
        """
        Check if a word appears as a complete word in text (not as substring of another word).

        E.g., "ash" should NOT match "wash" but SHOULD match "ash wood" or "ash veneer".
        """
        import re
        pattern = r'\b' + re.escape(word) + r'\b'
        return bool(re.search(pattern, text, re.IGNORECASE))

    def _extract_materials(
        self,
        text: str,
        term_phrases: List[str],
        detected_category: Optional[str] = None
    ) -> List[EntityItem]:
        """Extract material entities from dictionary lookup with aggressive textile filtering."""
        entities = []
        seen = set()

        # Check if this is a textile product (aggressive detection)
        is_textile = self._is_textile_product(text)

        # Get list of materials to exclude for this category
        excluded_materials = set()
        if detected_category and detected_category in self.EXCLUDED_MATERIALS_BY_CATEGORY:
            excluded_materials = {m.lower() for m in self.EXCLUDED_MATERIALS_BY_CATEGORY[detected_category]}

        # AGGRESSIVE FILTERING: If text indicates a textile product, exclude ALL impossible materials
        # This is a safety net even if category detection fails
        if is_textile:
            excluded_materials.update(self.TEXTILE_IMPOSSIBLE_MATERIALS)
            logger.debug(f"Textile product detected - excluding {len(self.TEXTILE_IMPOSSIBLE_MATERIALS)} impossible materials")

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
                    # Check if this material requires strict word boundary matching
                    if name in self.STRICT_WORD_BOUNDARY_MATERIALS:
                        # Use word boundary matching to avoid false positives like "ash" in "wash"
                        if not self._is_whole_word_match(name, text):
                            continue
                    else:
                        # Standard substring match for other materials
                        if name not in text:
                            continue

                    if name in seen:
                        continue

                    # Check if this material only appears in care instruction context
                    if self._is_material_in_care_context(name, text):
                        logger.debug(f"Skipping '{name}' - appears only in care instruction context")
                        continue

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

    # Keywords that are highly specific (more weight in scoring)
    HIGH_SPECIFICITY_KEYWORDS = {
        # Food/snack specific
        'pocky', 'chocolate', 'candy', 'snack', 'biscuit', 'cookie', 'confectionery',
        'gummy', 'wafer', 'chips', 'crackers', 'marshmallow', 'lolly', 'lollies',
        # Drinkware specific
        'cup', 'cups', 'mug', 'mugs', 'tumbler', 'goblet', 'drinkware', 'glassware',
        # Apparel specific (including swimwear)
        'shirt', 'dress', 'jacket', 'pants', 'jeans', 'hoodie', 'sweater',
        'swimwear', 'swimsuit', 'bikini', 'trunks', 'boardshorts', 'rashie',
        # Footwear specific
        'shoe', 'boot', 'sneaker', 'sandal',
        # Appliance specific
        'cooktop', 'refrigerator', 'dishwasher', 'oven',
        # Electronics specific
        'laptop', 'phone', 'tablet', 'television', 'camera',
    }

    # Minimum score required for a confident category match
    MIN_CATEGORY_SCORE = 2.0  # Requires either 1 high-specificity match or 2+ generic matches

    def _is_excluded_by_compound(self, keyword: str, text: str) -> bool:
        """
        Check if a keyword should be excluded because it appears in a compound phrase.

        E.g., "microwave" should not match if it appears as "microwave safe".
        """
        exclusions = self.COMPOUND_PHRASE_EXCLUSIONS.get(keyword.lower(), [])
        for phrase in exclusions:
            if phrase.lower() in text.lower():
                return True
        return False

    def _detect_product_category(self, text: str) -> Optional[str]:
        """
        Detect the product category from text (search query or product name).
        Uses weighted scoring with minimum threshold to avoid false positives.

        High-specificity keywords get 3x weight.
        Requires minimum score to return a category.
        Checks for compound phrase exclusions (e.g., "microwave safe" doesn't trigger Appliance).
        """
        if not text:
            return None

        text_lower = text.lower()
        words = set(text_lower.split())  # For whole-word matching

        # Score each category with weighted scoring
        scores = {}
        for category, keywords in self.PRIMARY_ENTITY_KEYWORDS.items():
            score = 0.0
            for kw in keywords:
                kw_lower = kw.lower()

                # Skip if this keyword is part of a compound phrase exclusion
                if self._is_excluded_by_compound(kw_lower, text_lower):
                    continue

                # Check for whole word match first (more reliable)
                if kw_lower in words:
                    weight = 3.0 if kw_lower in self.HIGH_SPECIFICITY_KEYWORDS else 1.0
                    score += weight
                # Fall back to substring match for multi-word keywords
                elif ' ' in kw_lower and kw_lower in text_lower:
                    weight = 3.0 if kw_lower in self.HIGH_SPECIFICITY_KEYWORDS else 1.0
                    score += weight
                # Single word substring match (less weight, more false positives)
                elif ' ' not in kw_lower and kw_lower in text_lower and len(kw_lower) >= 4:
                    weight = 0.5 if kw_lower in self.HIGH_SPECIFICITY_KEYWORDS else 0.3
                    score += weight

            if score >= self.MIN_CATEGORY_SCORE:
                scores[category] = score

        if not scores:
            return None

        # Return the highest scoring category that meets threshold
        return max(scores, key=scores.get)

    def _identify_primary_entity(
        self,
        product_name: str,
        all_text: str,
        entities: List[EntityItem],
        search_query: Optional[str] = None
    ) -> str:
        """
        Identify primary product entity path.

        Returns "Product > Unknown" when confidence is low, signaling that
        LLM should be preferred in entity_extractor.py.
        """
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
        # Use the same weighted scoring as _detect_product_category
        search_text = all_text.lower()
        words = set(search_text.split())

        # Score each primary entity type with weighted scoring
        scores = {}
        for entity_type, keywords in self.PRIMARY_ENTITY_KEYWORDS.items():
            score = 0.0
            for kw in keywords:
                kw_lower = kw.lower()

                # Skip if this keyword is part of a compound phrase exclusion
                if self._is_excluded_by_compound(kw_lower, search_text):
                    continue

                # Whole word match (more reliable)
                if kw_lower in words:
                    weight = 3.0 if kw_lower in self.HIGH_SPECIFICITY_KEYWORDS else 1.0
                    score += weight
                # Multi-word keyword substring match
                elif ' ' in kw_lower and kw_lower in search_text:
                    weight = 3.0 if kw_lower in self.HIGH_SPECIFICITY_KEYWORDS else 1.0
                    score += weight
                # Single word substring match (lower weight)
                elif ' ' not in kw_lower and kw_lower in search_text and len(kw_lower) >= 4:
                    weight = 0.5 if kw_lower in self.HIGH_SPECIFICITY_KEYWORDS else 0.3
                    score += weight

            if score >= self.MIN_CATEGORY_SCORE:
                scores[entity_type] = score

        # If no category meets threshold, return uncertain path
        # This signals to entity_extractor.py to prefer LLM's categorization
        if not scores:
            return f"Product > Unknown"

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
        """
        Dynamically infer a more specific subtype for the primary entity using OpenAI.

        Uses LRU-cached OpenAI calls to avoid repeated API requests for the same inputs.
        Falls back gracefully if OpenAI is unavailable.

        Args:
            entity_type: The detected category (e.g., "Food", "Apparel")
            text: Search query or product text to analyze
            entities: Extracted entities (currently unused, reserved for future enhancement)

        Returns:
            Inferred subtype string or None if inference fails/unavailable
        """
        if not text or not entity_type:
            return None

        # Truncate text to first 100 chars for efficiency (search queries are usually short)
        text_truncated = text[:100].strip()

        # Use the cached LLM function for dynamic inference
        return _infer_subtype_from_llm(entity_type, text_truncated)

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
