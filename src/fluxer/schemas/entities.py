"""
Pydantic schemas for entity extraction API validation.

Provides strict input validation at API boundaries while maintaining
compatibility with internal dataclass-based models.
"""
from __future__ import annotations

from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field, field_validator


class TFIDFTerm(BaseModel):
    """A single TF-IDF term from SEO analysis."""
    phrase: str = Field(..., min_length=1, description="The extracted phrase/term")
    tfidf_score: float = Field(default=0.0, ge=0.0, description="TF-IDF score")
    doc_freq: int = Field(default=1, ge=1, description="Document frequency")
    importance_score: float = Field(default=0.0, ge=0.0, description="Combined importance score")
    source: str = Field(default="tfidf", description="Source of the term")

    class Config:
        extra = "allow"  # Allow additional fields from frontend


class EntityItemSchema(BaseModel):
    """Individual entity with provenance tracking."""
    name: str = Field(..., min_length=1, description="Entity name")
    entity_type: str = Field(
        ...,
        description="Entity type: material, standard, environment, care, dimension, finish, certification"
    )
    evidence: str = Field(..., description="Text snippet supporting this entity")
    source: Literal["rules", "llm"] = Field(..., description="Extraction source")
    value: Optional[str] = Field(default=None, description="Numeric value if applicable")
    unit: Optional[str] = Field(default=None, description="Unit of measurement")
    why_it_matters: Optional[str] = Field(default=None, description="Explanation of entity significance")

    @field_validator('entity_type')
    @classmethod
    def validate_entity_type(cls, v: str) -> str:
        valid_types = {
            'material', 'standard', 'environment', 'care',
            'dimension', 'finish', 'certification', 'capacity',
            'weight', 'rating', 'warranty', 'compatibility'
        }
        if v.lower() not in valid_types:
            # Allow unknown types but normalize
            pass
        return v.lower()


class ConflictSchema(BaseModel):
    """Conflict between rules and LLM extraction."""
    entity_type: str = Field(..., description="Type of entity with conflict")
    rule_value: str = Field(..., description="Value from rules extraction")
    llm_value: str = Field(..., description="Value from LLM extraction")
    resolution: Literal["prefer_rules", "prefer_llm", "manual_review"] = Field(
        default="prefer_rules",
        description="How the conflict was resolved"
    )
    reason: str = Field(..., description="Reason for resolution")


class AuditInfoSchema(BaseModel):
    """Audit trail for entity extraction."""
    missing_types: List[str] = Field(default_factory=list, description="Entity types not found")
    conflicts: List[ConflictSchema] = Field(default_factory=list, description="Detected conflicts")
    notes: List[str] = Field(default_factory=list, description="Processing notes")
    llm_invoked: bool = Field(default=False, description="Whether LLM was used")
    llm_reason: Optional[str] = Field(default=None, description="Reason for LLM invocation")


class PlacementRecommendationSchema(BaseModel):
    """Recommendation for entity placement on product page."""
    entity_name: str = Field(..., description="Name of the entity")
    entity_type: str = Field(..., description="Type of the entity")
    recommended_sections: List[str] = Field(
        default_factory=list,
        description="Recommended PDP sections: specs_table, features, designed_for, care_instructions, faq, json_ld"
    )
    reasoning: str = Field(..., description="Reason for placement recommendation")


class EntityExtractionRequest(BaseModel):
    """Request schema for entity extraction API."""
    product_id: str = Field(..., min_length=1, description="Unique product identifier")
    product_name: str = Field(..., min_length=1, description="Product name/title")
    tfidf_terms: List[TFIDFTerm] = Field(
        default_factory=list,
        description="TF-IDF terms from SEO analysis"
    )
    description: Optional[str] = Field(default=None, description="Product description text")
    force_llm: bool = Field(default=False, description="Force LLM extraction regardless of confidence")

    @field_validator('tfidf_terms', mode='before')
    @classmethod
    def parse_tfidf_terms(cls, v):
        """Handle both dict and TFIDFTerm inputs."""
        if not v:
            return []
        result = []
        for item in v:
            if isinstance(item, dict):
                # Handle various field name formats from frontend
                result.append(TFIDFTerm(
                    phrase=item.get('phrase', item.get('term', '')),
                    tfidf_score=float(item.get('tfidf_score', item.get('score', 0.0))),
                    doc_freq=int(item.get('doc_freq', item.get('docFreq', 1))),
                    importance_score=float(item.get('importance_score', item.get('importanceScore', 0.0))),
                    source=item.get('source', 'tfidf')
                ))
            elif isinstance(item, TFIDFTerm):
                result.append(item)
        return result


class EntityExtractionResponse(BaseModel):
    """Complete response from entity extraction."""
    product_id: str = Field(..., description="Product identifier")
    product_name: str = Field(..., description="Product name")
    primary_entity_path: str = Field(..., description="Hierarchical entity path (e.g., Furniture > Table)")
    grouped_terms: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="TF-IDF terms grouped by category"
    )
    rule_entities: List[EntityItemSchema] = Field(
        default_factory=list,
        description="Entities extracted by rules engine"
    )
    llm_entities: List[EntityItemSchema] = Field(
        default_factory=list,
        description="Entities extracted by LLM"
    )
    supporting_entities: List[EntityItemSchema] = Field(
        default_factory=list,
        description="Final merged entities"
    )
    placement_map: List[PlacementRecommendationSchema] = Field(
        default_factory=list,
        description="Placement recommendations for PDP"
    )
    noise_terms: List[str] = Field(
        default_factory=list,
        description="Terms not categorized"
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Extraction confidence score"
    )
    audit: AuditInfoSchema = Field(
        default_factory=AuditInfoSchema,
        description="Audit trail"
    )

    class Config:
        extra = "allow"
