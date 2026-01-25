import json
import pathlib
import unittest
from unittest.mock import patch

from serp_services.get_popular_products import AggregatedResults, ProductHit, SerpProcessor


class TestSerpProcessor(unittest.TestCase):
    def setUp(self) -> None:
        sample_path = pathlib.Path("sample_data") / "blue dress.json"
        self.sample_payload = json.loads(sample_path.read_text())

    @patch("serp_processor.GoogleSearch")
    def test_fetch_products_from_sample_file(self, mock_search_cls):
        mock_instance = mock_search_cls.return_value
        mock_instance.get_dict.return_value = self.sample_payload

        limit = 3
        result: AggregatedResults = SerpProcessor.fetch_products(
            ["blue dress"], limit=limit, api_key="test-key"
        )

        self.assertIn("blue dress", result.by_query)
        products = result.by_query["blue dress"]
        self.assertEqual(len(products), limit)

        first = self.sample_payload["immersive_products"][0]
        expected_first = ProductHit(
            title=first["title"],
            price=first.get("price"),
            source=first.get("source"),
        )
        self.assertEqual(products[first["title"]], expected_first)

        mock_search_cls.assert_called_once()
        mock_instance.get_dict.assert_called_once()


if __name__ == "__main__":
    unittest.main()
