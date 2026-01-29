"""
LLM-powered entity extraction for gap filling.

Uses OpenAI to:
- Infer primary entity path when rules cannot determine
- Fill missing entity types
- Normalize entity names
- Suggest PDP placements and FAQs

Only invoked when rules extraction has gaps or low confidence.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from ..models import EntityItem
from ..config import Config
from ..logger import get_logger

logger = get_logger(__name__)

# Check OpenAI availability
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI package not installed. LLM extraction will be disabled.")


# =============================================================================
# JSON Schema for LLM output validation
# =============================================================================

LLM_OUTPUT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://example.com/schemas/product_entities_llm_output.json",
    "title": "ProductEntitiesLLMOutput",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "primary_entity_path",
        "llm_entities",
        "placement_map",
        "faqs",
        "confidence",
        "notes"
    ],
    "properties": {
        "primary_entity_path": {
            "type": "string",
            "minLength": 3,
            "description": "Single canonical taxonomy path like 'Furniture > Table > Coffee Table'. Use 'Unknown' if truly not inferable from inputs."
        },
        "llm_entities": {
            "type": "array",
            "description": "Entities proposed by the LLM to fill gaps/normalize. Must not contradict rule_entities unless explicitly marked in notes.",
            "items": {
                "$ref": "#/$defs/entity"
            }
        },
        "placement_map": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "spec_table",
                "designed_for",
                "not_suitable_for",
                "care_maintenance",
                "faqs",
                "json_ld"
            ],
            "properties": {
                "spec_table": {"type": "array", "items": {"type": "string"}},
                "designed_for": {"type": "array", "items": {"type": "string"}},
                "not_suitable_for": {"type": "array", "items": {"type": "string"}},
                "care_maintenance": {"type": "array", "items": {"type": "string"}},
                "faqs": {"type": "array", "items": {"type": "string"}},
                "json_ld": {"type": "array", "items": {"type": "string"}}
            }
        },
        "faqs": {
            "type": "array",
            "description": "FAQ suggestions that clarify entities/relationships. Keep them specific and non-marketing.",
            "maxItems": 12,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["question", "answer", "evidence"],
                "properties": {
                    "question": {"type": "string", "minLength": 5},
                    "answer": {"type": "string", "minLength": 5},
                    "evidence": {
                        "type": "string",
                        "minLength": 3,
                        "description": "Short phrase from provided inputs justifying the FAQ. If evidence is weak, do not include the FAQ."
                    }
                }
            }
        },
        "confidence": {
            "type": "object",
            "additionalProperties": False,
            "required": ["primary_entity", "supporting_entities"],
            "properties": {
                "primary_entity": {"type": "number", "minimum": 0, "maximum": 1},
                "supporting_entities": {"type": "number", "minimum": 0, "maximum": 1}
            }
        },
        "notes": {
            "type": "object",
            "additionalProperties": False,
            "required": ["missing_types", "conflicts", "assumptions"],
            "properties": {
                "missing_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Types still missing after LLM pass (if any)."
                },
                "conflicts": {
                    "type": "array",
                    "description": "Describe any conflicts between rule_entities and inferred entities, or contradictions within inputs.",
                    "items": {"type": "string"}
                },
                "assumptions": {
                    "type": "array",
                    "description": "Only include assumptions that are clearly supported. If unsupported, do not assume; leave unknown.",
                    "items": {"type": "string"}
                }
            }
        }
    },
    "$defs": {
        "entity": {
            "type": "object",
            "additionalProperties": False,
            "required": ["name", "type", "value", "unit", "evidence", "why_it_matters", "source"],
            "properties": {
                "name": {"type": "string", "minLength": 2},
                "type": {
                    "type": "string",
                    "enum": [
                        "material",
                        "standard",
                        "environment",
                        "care",
                        "size",
                        "capacity",
                        "finish",
                        "compatibility",
                        "safety"
                    ]
                },
                "value": {
                    "type": ["string", "null"],
                    "description": "Optional numeric/text value. Use null when not applicable."
                },
                "unit": {
                    "type": ["string", "null"],
                    "description": "Unit for value if applicable, e.g., cm, mm, kg, L, W. Otherwise null."
                },
                "evidence": {
                    "type": "string",
                    "minLength": 3,
                    "description": "Short quote/phrase from provided inputs (product specs/title/TFIDF) showing this entity exists. If you cannot cite evidence, do not output the entity."
                },
                "why_it_matters": {
                    "type": "string",
                    "minLength": 5,
                    "description": "One sentence explaining why this entity helps disambiguate or helps the buyer."
                },
                "source": {
                    "type": "string",
                    "enum": ["llm"]
                }
            }
        }
    }
}


# =============================================================================
# LLM Prompts
# =============================================================================

SYSTEM_PROMPT = """You extract semantic product entities for SEO in a rules+LLM hybrid pipeline.

Hard rules:
- DO NOT invent facts. Only use information present in the inputs.
- Every entity you output MUST include an evidence phrase copied from the inputs.
- If evidence is not present, do not output the entity.
- You are NOT writing marketing copy. Be factual and concise.
- Prefer normalizing and clarifying over adding more items.
- If the primary product entity cannot be inferred, output "Unknown".

Output requirements:
- Output MUST be valid JSON only.
- Output MUST conform exactly to the provided JSON Schema.
- No extra keys, no markdown, no commentary."""


USER_PROMPT_TEMPLATE = """TASK
We already ran deterministic rules to extract entities. Your job is to:
1) Infer the single best primary_entity_path (taxonomy path like "Furniture > Table > Coffee Table") ONLY from the inputs.
2) Fill only the missing entity types and normalize names.
3) Propose a placement_map showing where entities should live on a PDP.
4) Suggest FAQs that clarify entity relationships, only if evidence exists.

CONSTRAINTS
- Do NOT duplicate entities already present in rule_entities unless you are providing a normalized name that is clearer (still must include evidence).
- Do NOT contradict rule_entities. If you suspect conflict, explain it in notes.conflicts and avoid adding contradictory entities.
- You MUST include evidence for every llm_entities item and every FAQ.
- If you cannot find evidence, leave it out.
- Keep llm_entities short and high-signal (typically 0–12 items).

INPUTS
User Search Query (original search intent - use this to understand the product category):
- search_query: "{search_query}"

Product:
- product_name: "{product_name}"
- product_title: "{product_title}"
- product_description: "{product_description}"
- product_specs_text: "{product_specs_text}"

TF-IDF grouped terms:
{grouped_terms_json}

Rule extracted entities (already trusted):
{rule_entities_json}

Missing types requested (only fill these if evidence exists):
{missing_types_json}

Known ambiguities/conflicts from rules (do NOT override; only comment in notes.conflicts):
{rule_conflicts_json}

OUTPUT JSON SCHEMA
You MUST output JSON that matches this schema:
{schema_json}

NOW PRODUCE THE JSON OUTPUT."""


FIX_JSON_PROMPT = """Your previous output did not match the required JSON Schema.

Fix your output so that:
- It is VALID JSON
- It conforms EXACTLY to the schema (no extra keys, all required keys present)
- All llm_entities and faqs include evidence from the provided inputs
Return JSON only."""


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class FAQSuggestion:
    """FAQ suggestion with evidence."""
    question: str
    answer: str
    evidence: str

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "answer": self.answer,
            "evidence": self.evidence
        }


@dataclass
class LLMExtractionResult:
    """Result from LLM-based entity extraction."""
    llm_entities: List[EntityItem] = field(default_factory=list)
    primary_entity_path: Optional[str] = None
    placement_suggestions: Dict[str, List[str]] = field(default_factory=dict)
    faq_suggestions: List[FAQSuggestion] = field(default_factory=list)
    confidence: float = 0.0
    confidence_primary: float = 0.0
    confidence_supporting: float = 0.0
    success: bool = True
    error: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    llm_missing_types: List[str] = field(default_factory=list)
    llm_conflicts: List[str] = field(default_factory=list)
    llm_assumptions: List[str] = field(default_factory=list)


# =============================================================================
# LLM Extractor Class
# =============================================================================

class EntityLLMExtractor:
    """
    LLM-based entity extraction using OpenAI.

    Only invoked when rules extraction has gaps or low confidence.
    Uses JSON mode for structured output with schema validation.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        max_retries: int = 2
    ):
        """
        Initialize LLM extractor.

        Args:
            model: OpenAI model to use (default from config)
            temperature: Creativity level (low for consistency)
            max_tokens: Maximum response tokens
            max_retries: Number of retry attempts on failure
        """
        self.model = model or getattr(Config, 'ENTITY_LLM_MODEL', 'gpt-4o-mini')
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries

        self._client: Optional[Any] = None
        self._init_client()

    def _init_client(self) -> None:
        """Initialize OpenAI client."""
        if not OPENAI_AVAILABLE:
            return

        api_key = Config.OPENAI_API_KEY
        if api_key:
            self._client = OpenAI(api_key=api_key)
            logger.info(f"LLM extractor initialized with model: {self.model}")
        else:
            logger.warning("OPENAI_API_KEY not set. LLM extraction will fail.")

    def is_available(self) -> bool:
        """Check if LLM extraction is available."""
        return OPENAI_AVAILABLE and self._client is not None

    def should_invoke(
        self,
        rules_confidence: float,
        missing_types: List[str],
        threshold: float = 0.7,
        critical_types: Optional[List[str]] = None
    ) -> tuple[bool, str]:
        """
        Determine if LLM should be invoked based on rules result.

        Args:
            rules_confidence: Confidence score from rules extraction
            missing_types: Entity types not found by rules
            threshold: Confidence threshold below which LLM is triggered
            critical_types: Types that must be present

        Returns:
            Tuple of (should_invoke, reason)
        """
        if not self.is_available():
            return False, "LLM not available (no API key or package)"

        if not getattr(Config, 'ENTITY_LLM_ENABLED', True):
            return False, "LLM extraction disabled in config"

        critical = critical_types or ['material', 'dimension']

        # Check if critical types are missing
        missing_critical = [t for t in missing_types if t in critical]
        if missing_critical:
            return True, f"Missing critical types: {missing_critical}"

        # Check confidence threshold
        if rules_confidence < threshold:
            return True, f"Low rules confidence: {rules_confidence:.2f} < {threshold}"

        return False, "Rules extraction sufficient"

    def extract(
        self,
        product_name: str,
        description: Optional[str],
        tfidf_terms: List[Dict],
        missing_types: List[str],
        existing_entities: List[EntityItem],
        rule_conflicts: Optional[List[str]] = None,
        product_title: Optional[str] = None,
        product_specs_text: Optional[str] = None,
        grouped_terms: Optional[Dict[str, List[str]]] = None,
        search_query: Optional[str] = None
    ) -> LLMExtractionResult:
        """
        Extract entities using LLM to fill gaps.

        Args:
            product_name: Product name/title
            description: Product description text
            tfidf_terms: TF-IDF terms from SEO analysis
            missing_types: Entity types to fill
            existing_entities: Entities already extracted by rules
            rule_conflicts: Known conflicts from rules extraction
            product_title: Optional separate product title
            product_specs_text: Optional specs as plain text
            grouped_terms: Grouped TF-IDF terms by category
            search_query: Original search query for product context

        Returns:
            LLMExtractionResult with extracted entities
        """
        result = LLMExtractionResult()

        if not self.is_available():
            result.success = False
            result.error = "LLM not available"
            return result

        if not missing_types:
            result.notes.append("No missing types to fill")
            return result

        try:
            # Build prompt with all context
            prompt = self._build_prompt(
                product_name=product_name,
                product_title=product_title or product_name,
                description=description,
                specs_text=product_specs_text,
                tfidf_terms=tfidf_terms,
                grouped_terms=grouped_terms,
                missing_types=missing_types,
                existing_entities=existing_entities,
                rule_conflicts=rule_conflicts or [],
                search_query=search_query
            )

            # Call LLM with retry
            response_data = self._call_with_retry(prompt)

            if response_data is None:
                result.success = False
                result.error = "Failed to get valid response from LLM"
                return result

            # Parse and validate response
            result = self._parse_response(response_data)
            result.notes.append(f"LLM extracted {len(result.llm_entities)} entities")

            logger.info(
                f"LLM extraction complete: {len(result.llm_entities)} entities, "
                f"confidence={result.confidence:.2f}"
            )

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}", exc_info=True)
            result.success = False
            result.error = str(e)

        return result

    def _build_prompt(
        self,
        product_name: str,
        product_title: str,
        description: Optional[str],
        specs_text: Optional[str],
        tfidf_terms: List[Dict],
        grouped_terms: Optional[Dict[str, List[str]]],
        missing_types: List[str],
        existing_entities: List[EntityItem],
        rule_conflicts: List[str],
        search_query: Optional[str] = None
    ) -> str:
        """Build the user prompt for LLM with full context."""

        # Format grouped terms as JSON
        if grouped_terms:
            grouped_terms_json = json.dumps(grouped_terms, indent=2)
        else:
            # Build grouped terms from tfidf_terms
            terms_dict = {}
            for term in tfidf_terms[:30]:
                phrase = term.get('phrase', '')
                score = term.get('tfidf_score', 0)
                if phrase:
                    terms_dict[phrase] = round(score, 3)
            grouped_terms_json = json.dumps({"tfidf_terms": terms_dict}, indent=2)

        # Format rule entities as JSON
        rule_entities_list = []
        for entity in existing_entities:
            rule_entities_list.append({
                "name": entity.name,
                "type": entity.entity_type,
                "evidence": entity.evidence,
                "source": entity.source
            })
        rule_entities_json = json.dumps(rule_entities_list, indent=2)

        # Format missing types
        missing_types_json = json.dumps(missing_types)

        # Format conflicts
        rule_conflicts_json = json.dumps(rule_conflicts) if rule_conflicts else "[]"

        # Get schema as JSON string
        schema_json = json.dumps(LLM_OUTPUT_SCHEMA, indent=2)

        return USER_PROMPT_TEMPLATE.format(
            search_query=(search_query or "(Not provided)"),
            product_name=product_name,
            product_title=product_title,
            product_description=(description[:3000] if description else "(No description available)"),
            product_specs_text=(specs_text[:2000] if specs_text else "(No specs text available)"),
            grouped_terms_json=grouped_terms_json,
            rule_entities_json=rule_entities_json,
            missing_types_json=missing_types_json,
            rule_conflicts_json=rule_conflicts_json,
            schema_json=schema_json
        )

    def _call_with_retry(self, user_prompt: str) -> Optional[Dict]:
        """Call OpenAI API with JSON mode and retry on failure."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        last_error = None
        last_content = ""

        for attempt in range(self.max_retries):
            try:
                logger.info(f"LLM API call attempt {attempt + 1}/{self.max_retries}")

                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )

                content = response.choices[0].message.content
                last_content = content or ""

                if not content:
                    raise ValueError("Empty response from LLM")

                # Parse JSON
                data = json.loads(content)

                # Validate basic structure
                if not isinstance(data, dict):
                    raise ValueError("Response is not a JSON object")

                # Check required top-level keys
                required_keys = ["primary_entity_path", "llm_entities", "placement_map", "faqs", "confidence", "notes"]
                missing_keys = [k for k in required_keys if k not in data]
                if missing_keys:
                    raise ValueError(f"Missing required keys: {missing_keys}")

                logger.info("LLM API call successful")
                return data

            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse failed (attempt {attempt + 1}): {e}")
                last_error = e

                # Add repair instruction for retry
                if attempt < self.max_retries - 1:
                    messages.append({
                        "role": "assistant",
                        "content": last_content
                    })
                    messages.append({
                        "role": "user",
                        "content": FIX_JSON_PROMPT
                    })

            except ValueError as e:
                logger.warning(f"Schema validation failed (attempt {attempt + 1}): {e}")
                last_error = e

                # Add repair instruction for retry
                if attempt < self.max_retries - 1:
                    messages.append({
                        "role": "assistant",
                        "content": last_content
                    })
                    messages.append({
                        "role": "user",
                        "content": FIX_JSON_PROMPT
                    })

            except Exception as e:
                logger.warning(f"LLM API call failed (attempt {attempt + 1}): {e}")
                last_error = e

        logger.error(f"All LLM retry attempts failed: {last_error}")
        return None

    def _parse_response(self, data: Dict) -> LLMExtractionResult:
        """Parse LLM response into result object."""
        result = LLMExtractionResult()

        # Extract primary entity path
        result.primary_entity_path = data.get('primary_entity_path')

        # Extract entities
        entities_data = data.get('llm_entities', [])
        for entity_data in entities_data:
            if not isinstance(entity_data, dict):
                continue

            name = entity_data.get('name')
            entity_type = entity_data.get('type')
            evidence = entity_data.get('evidence', '')

            if not name or not entity_type or not evidence:
                # Skip entities without required evidence
                continue

            result.llm_entities.append(EntityItem(
                name=name,
                entity_type=entity_type.lower(),
                evidence=evidence,
                source='llm',
                value=entity_data.get('value'),
                unit=entity_data.get('unit'),
                why_it_matters=entity_data.get('why_it_matters')
            ))

        # Extract placement suggestions (map new keys to old format for compatibility)
        placements = data.get('placement_map', {})
        if isinstance(placements, dict):
            # Map to the expected format
            result.placement_suggestions = {
                'specs_table': placements.get('spec_table', []),
                'features': placements.get('designed_for', []),
                'designed_for': placements.get('designed_for', []),
                'not_suitable_for': placements.get('not_suitable_for', []),
                'care_instructions': placements.get('care_maintenance', []),
                'faqs': placements.get('faqs', []),
                'json_ld': placements.get('json_ld', [])
            }

        # Extract FAQ suggestions with evidence
        faqs = data.get('faqs', [])
        if isinstance(faqs, list):
            for faq in faqs:
                if isinstance(faq, dict):
                    question = faq.get('question', '')
                    answer = faq.get('answer', '')
                    evidence = faq.get('evidence', '')
                    if question and answer and evidence:
                        result.faq_suggestions.append(FAQSuggestion(
                            question=question,
                            answer=answer,
                            evidence=evidence
                        ))

        # Extract confidence (new format with primary_entity and supporting_entities)
        confidence_data = data.get('confidence', {})
        if isinstance(confidence_data, dict):
            result.confidence_primary = float(confidence_data.get('primary_entity', 0.5))
            result.confidence_supporting = float(confidence_data.get('supporting_entities', 0.5))
            # Use average for overall confidence
            result.confidence = (result.confidence_primary + result.confidence_supporting) / 2
        elif isinstance(confidence_data, (int, float)):
            # Fallback for old format
            result.confidence = max(0.0, min(1.0, float(confidence_data)))
            result.confidence_primary = result.confidence
            result.confidence_supporting = result.confidence

        # Extract notes
        notes_data = data.get('notes', {})
        if isinstance(notes_data, dict):
            result.llm_missing_types = notes_data.get('missing_types', [])
            result.llm_conflicts = notes_data.get('conflicts', [])
            result.llm_assumptions = notes_data.get('assumptions', [])

            # Add to general notes
            if result.llm_conflicts:
                result.notes.append(f"LLM conflicts: {result.llm_conflicts}")
            if result.llm_assumptions:
                result.notes.append(f"LLM assumptions: {result.llm_assumptions}")
            if result.llm_missing_types:
                result.notes.append(f"Still missing after LLM: {result.llm_missing_types}")

        result.success = True
        return result
