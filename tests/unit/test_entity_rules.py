"""
Unit tests for the entity rules engine.

Tests deterministic extraction patterns for:
- Dimensions (mm, cm, m, inch)
- Materials (dictionary lookup)
- Finishes (dictionary lookup)
- Standards (regex patterns)
- Environments (dictionary lookup)
- Care/warranty (pattern matching)
"""
import pytest
from pathlib import Path

from src.fluxer.services.entity_rules import EntityRulesEngine, RulesExtractionResult


class TestDimensionExtraction:
    """Tests for dimension extraction patterns."""

    @pytest.fixture
    def engine(self):
        return EntityRulesEngine()

    def test_extracts_mm_dimensions(self, engine):
        """Should extract millimeter dimensions."""
        result = engine.extract(
            product_name="Outdoor Table",
            tfidf_terms=[{"phrase": "1200mm width"}],
            description="The table is 1200mm W x 600mm D x 750mm H."
        )

        dim_entities = [e for e in result.rule_entities if e.entity_type == 'dimension']
        assert len(dim_entities) >= 1
        assert any('1200' in e.value for e in dim_entities if e.value)

    def test_extracts_cm_dimensions(self, engine):
        """Should extract centimeter dimensions."""
        result = engine.extract(
            product_name="Small Table",
            tfidf_terms=[],
            description="Height is 75cm and width is 120cm."
        )

        dim_entities = [e for e in result.rule_entities if e.entity_type == 'dimension']
        assert len(dim_entities) >= 1

    def test_extracts_inch_dimensions(self, engine):
        """Should extract inch dimensions."""
        result = engine.extract(
            product_name="American Table",
            tfidf_terms=[],
            description='48 inch width, 24" depth'
        )

        dim_entities = [e for e in result.rule_entities if e.entity_type == 'dimension']
        assert len(dim_entities) >= 1


class TestMaterialExtraction:
    """Tests for material extraction from dictionary."""

    @pytest.fixture
    def engine(self):
        return EntityRulesEngine()

    def test_extracts_stainless_steel(self, engine):
        """Should extract stainless steel material."""
        result = engine.extract(
            product_name="Kitchen Table",
            tfidf_terms=[{"phrase": "stainless steel frame"}],
            description="Built with a stainless steel frame for durability."
        )

        mat_entities = [e for e in result.rule_entities if e.entity_type == 'material']
        assert len(mat_entities) >= 1
        assert any('stainless' in e.name.lower() for e in mat_entities)

    def test_extracts_teak_wood(self, engine):
        """Should extract teak wood material."""
        result = engine.extract(
            product_name="Outdoor Chair",
            tfidf_terms=[{"phrase": "teak wood construction"}],
            description="Crafted from premium teak wood."
        )

        mat_entities = [e for e in result.rule_entities if e.entity_type == 'material']
        assert len(mat_entities) >= 1
        assert any('teak' in e.name.lower() for e in mat_entities)

    def test_extracts_aluminium_with_alias(self, engine):
        """Should recognize aluminum as aluminium alias."""
        result = engine.extract(
            product_name="Modern Chair",
            tfidf_terms=[{"phrase": "aluminum legs"}],
            description="Features lightweight aluminum legs."
        )

        mat_entities = [e for e in result.rule_entities if e.entity_type == 'material']
        assert len(mat_entities) >= 1
        assert any('aluminium' in e.name.lower() or 'aluminum' in e.name.lower() for e in mat_entities)


class TestStandardExtraction:
    """Tests for standard/certification extraction."""

    @pytest.fixture
    def engine(self):
        return EntityRulesEngine()

    def test_extracts_as_nzs_standard(self, engine):
        """Should extract AS/NZS standards."""
        result = engine.extract(
            product_name="Gas Cooktop",
            tfidf_terms=[{"phrase": "AS/NZS 4386 compliant"}],
            description="Certified to AS/NZS 4386 safety standard."
        )

        std_entities = [e for e in result.rule_entities if e.entity_type in ('standard', 'certification', 'rating')]
        assert len(std_entities) >= 1
        assert any('AS/NZS' in e.name for e in std_entities)

    def test_extracts_ip_rating(self, engine):
        """Should extract IP ratings."""
        result = engine.extract(
            product_name="Outdoor Light",
            tfidf_terms=[{"phrase": "IP65 rated"}],
            description="IP65 water and dust resistant."
        )

        rating_entities = [e for e in result.rule_entities if 'IP' in e.name]
        assert len(rating_entities) >= 1

    def test_extracts_iso_certification(self, engine):
        """Should extract ISO certifications."""
        result = engine.extract(
            product_name="Quality Product",
            tfidf_terms=[],
            description="Manufactured under ISO 9001 quality management."
        )

        std_entities = [e for e in result.rule_entities if 'ISO' in e.name]
        assert len(std_entities) >= 1


class TestEnvironmentExtraction:
    """Tests for environment/usage context extraction."""

    @pytest.fixture
    def engine(self):
        return EntityRulesEngine()

    def test_extracts_outdoor_environment(self, engine):
        """Should extract outdoor environment."""
        result = engine.extract(
            product_name="Patio Set",
            tfidf_terms=[{"phrase": "outdoor use"}],
            description="Designed for outdoor use on your patio."
        )

        env_entities = [e for e in result.rule_entities if e.entity_type == 'environment']
        assert len(env_entities) >= 1
        assert any('outdoor' in e.name.lower() for e in env_entities)

    def test_extracts_coastal_environment(self, engine):
        """Should extract coastal environment."""
        result = engine.extract(
            product_name="Beach Furniture",
            tfidf_terms=[{"phrase": "coastal rated"}],
            description="Perfect for coastal environments with salt air resistance."
        )

        env_entities = [e for e in result.rule_entities if e.entity_type == 'environment']
        assert len(env_entities) >= 1
        assert any('coastal' in e.name.lower() for e in env_entities)


class TestConfidenceCalculation:
    """Tests for confidence score calculation."""

    @pytest.fixture
    def engine(self):
        return EntityRulesEngine()

    def test_high_confidence_with_many_entities(self, engine):
        """Should have higher confidence with more entities found."""
        result = engine.extract(
            product_name="Premium Outdoor Teak Table",
            tfidf_terms=[
                {"phrase": "stainless steel frame"},
                {"phrase": "teak wood top"},
                {"phrase": "powder coated"},
                {"phrase": "outdoor rated"},
                {"phrase": "5 year warranty"}
            ],
            description="1200mm W x 600mm D outdoor table with stainless steel frame, teak top, powder coated finish. 5 year warranty."
        )

        assert result.confidence > 0.5

    def test_low_confidence_with_no_entities(self, engine):
        """Should have low confidence when no entities found."""
        result = engine.extract(
            product_name="Mystery Product",
            tfidf_terms=[],
            description="This is a product."
        )

        assert result.confidence < 0.5

    def test_missing_types_populated(self, engine):
        """Should track missing entity types."""
        result = engine.extract(
            product_name="Simple Product",
            tfidf_terms=[],
            description="A simple product description."
        )

        assert len(result.missing_types) > 0


class TestPrimaryEntityPath:
    """Tests for primary entity path identification."""

    @pytest.fixture
    def engine(self):
        return EntityRulesEngine()

    def test_identifies_furniture_entity(self, engine):
        """Should identify furniture as primary entity."""
        result = engine.extract(
            product_name="Dining Table Set",
            tfidf_terms=[{"phrase": "dining table"}, {"phrase": "furniture"}],
            description="A beautiful dining table for your home."
        )

        assert 'Furniture' in result.primary_entity_path

    def test_identifies_appliance_entity(self, engine):
        """Should identify appliance as primary entity."""
        result = engine.extract(
            product_name="Induction Cooktop",
            tfidf_terms=[{"phrase": "induction cooktop"}, {"phrase": "appliance"}],
            description="A modern induction cooktop for your kitchen."
        )

        assert 'Appliance' in result.primary_entity_path

    def test_fallback_to_product_name(self, engine):
        """Should fallback to product name when no match."""
        result = engine.extract(
            product_name="Custom Widget",
            tfidf_terms=[],
            description="A custom widget."
        )

        assert 'Product' in result.primary_entity_path or 'Custom Widget' in result.primary_entity_path
