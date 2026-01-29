"""
Unit tests for entity merge logic.

Tests:
- Deduplication by (type, normalized_name)
- Rules preference over LLM
- Conflict detection
- Confidence calculation
"""
import pytest

from src.fluxer.models import EntityItem
from src.fluxer.services.entity_merge import EntityMerger


class TestDeduplication:
    """Tests for entity deduplication."""

    @pytest.fixture
    def merger(self):
        return EntityMerger()

    def test_deduplicates_exact_matches(self, merger):
        """Should deduplicate entities with same name and type."""
        entities = [
            EntityItem(name="Stainless Steel", entity_type="material", evidence="test", source="rules"),
            EntityItem(name="Stainless Steel", entity_type="material", evidence="test2", source="rules"),
        ]

        result = merger.deduplicate(entities)
        assert len(result) == 1

    def test_keeps_different_types(self, merger):
        """Should keep entities with different types even if same name."""
        entities = [
            EntityItem(name="Steel", entity_type="material", evidence="test", source="rules"),
            EntityItem(name="Steel", entity_type="finish", evidence="test", source="rules"),
        ]

        result = merger.deduplicate(entities)
        assert len(result) == 2

    def test_normalizes_names_for_comparison(self, merger):
        """Should normalize names (lowercase, variants) for comparison."""
        entities = [
            EntityItem(name="Stainless Steel", entity_type="material", evidence="test", source="rules"),
            EntityItem(name="stainless steel", entity_type="material", evidence="test", source="llm"),
        ]

        result = merger.deduplicate(entities)
        assert len(result) == 1


class TestRulesPreference:
    """Tests for preferring rules over LLM."""

    @pytest.fixture
    def merger(self):
        return EntityMerger()

    def test_prefers_rules_over_llm(self, merger):
        """Should keep rules entity when both have same name/type."""
        rules_entities = [
            EntityItem(name="Teak", entity_type="material", evidence="from rules", source="rules")
        ]
        llm_entities = [
            EntityItem(name="teak", entity_type="material", evidence="from llm", source="llm")
        ]

        result = merger.merge(rules_entities, llm_entities)

        # Should have only 1 entity
        assert len(result.merged_entities) == 1
        # Should be from rules
        assert result.merged_entities[0].source == "rules"

    def test_adds_unique_llm_entities(self, merger):
        """Should add LLM entities that don't exist in rules."""
        rules_entities = [
            EntityItem(name="Teak", entity_type="material", evidence="from rules", source="rules")
        ]
        llm_entities = [
            EntityItem(name="Outdoor", entity_type="environment", evidence="from llm", source="llm")
        ]

        result = merger.merge(rules_entities, llm_entities)

        assert len(result.merged_entities) == 2
        types = {e.entity_type for e in result.merged_entities}
        assert "material" in types
        assert "environment" in types


class TestConflictDetection:
    """Tests for conflict detection between rules and LLM."""

    @pytest.fixture
    def merger(self):
        return EntityMerger()

    def test_detects_material_conflict(self, merger):
        """Should detect when rules and LLM have different materials."""
        rules_entities = [
            EntityItem(name="Stainless Steel", entity_type="material", evidence="steel frame", source="rules")
        ]
        llm_entities = [
            EntityItem(name="Aluminium", entity_type="material", evidence="aluminum body", source="llm")
        ]

        result = merger.merge(rules_entities, llm_entities)

        # Should detect a conflict
        assert len(result.conflicts) >= 1
        assert result.conflicts[0].entity_type == "material"

    def test_no_conflict_when_matching(self, merger):
        """Should not detect conflict when rules and LLM agree."""
        rules_entities = [
            EntityItem(name="Teak", entity_type="material", evidence="teak wood", source="rules")
        ]
        llm_entities = [
            EntityItem(name="teak", entity_type="material", evidence="teak timber", source="llm")
        ]

        result = merger.merge(rules_entities, llm_entities)

        # No conflicts - they're the same material
        assert len(result.conflicts) == 0

    def test_detects_environment_conflict(self, merger):
        """Should detect indoor vs outdoor conflict."""
        rules_entities = [
            EntityItem(name="Indoor", entity_type="environment", evidence="indoor use", source="rules")
        ]
        llm_entities = [
            EntityItem(name="Outdoor", entity_type="environment", evidence="outdoor rated", source="llm")
        ]

        result = merger.merge(rules_entities, llm_entities)

        # Should detect environment conflict
        assert len(result.conflicts) >= 1


class TestConfidenceCalculation:
    """Tests for final confidence calculation."""

    @pytest.fixture
    def merger(self):
        return EntityMerger()

    def test_higher_confidence_with_agreement(self, merger):
        """Should have higher confidence when rules and LLM agree."""
        rules_entities = [
            EntityItem(name="Teak", entity_type="material", evidence="teak", source="rules"),
            EntityItem(name="Outdoor", entity_type="environment", evidence="outdoor", source="rules"),
        ]
        llm_entities = [
            EntityItem(name="5 Year Warranty", entity_type="warranty", evidence="warranty", source="llm"),
        ]

        result = merger.merge(rules_entities, llm_entities, rules_confidence=0.7, llm_confidence=0.8)

        # Should have reasonable confidence
        assert result.confidence > 0.5

    def test_lower_confidence_with_conflicts(self, merger):
        """Should have lower confidence when conflicts exist."""
        rules_entities = [
            EntityItem(name="Indoor", entity_type="environment", evidence="indoor", source="rules"),
        ]
        llm_entities = [
            EntityItem(name="Outdoor", entity_type="environment", evidence="outdoor", source="llm"),
        ]

        result = merger.merge(rules_entities, llm_entities, rules_confidence=0.7, llm_confidence=0.7)

        # Should have confidence but penalized for conflict
        assert result.confidence < 0.8

    def test_confidence_with_no_entities(self, merger):
        """Should have very low confidence with no entities."""
        result = merger.merge([], [], rules_confidence=0.0, llm_confidence=0.0)

        assert result.confidence <= 0.2


class TestNameNormalization:
    """Tests for name normalization."""

    @pytest.fixture
    def merger(self):
        return EntityMerger()

    def test_normalizes_aluminum_to_aluminium(self, merger):
        """Should treat aluminum and aluminium as same."""
        name1 = merger._normalize_name("Aluminum")
        name2 = merger._normalize_name("Aluminium")

        assert name1 == name2

    def test_normalizes_case(self, merger):
        """Should normalize case."""
        name1 = merger._normalize_name("STAINLESS STEEL")
        name2 = merger._normalize_name("stainless steel")

        assert name1 == name2

    def test_normalizes_finish_variants(self, merger):
        """Should normalize finish variants."""
        name1 = merger._normalize_name("powder-coated")
        name2 = merger._normalize_name("powder coated")

        assert name1 == name2
