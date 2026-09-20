import unittest

from app.services.observability_service import ObservabilityService


class ObservabilityServiceTests(unittest.TestCase):
    def test_normalizes_record_ids_in_metric_paths(self) -> None:
        service = ObservabilityService()

        self.assertEqual(
            service._normalize_path("/bills/123e4567-e89b-12d3-a456-426614174000"),
            "/bills/{id}",
        )

    def test_percentile_uses_sorted_values(self) -> None:
        service = ObservabilityService()

        self.assertEqual(service._percentile([80, 10, 50, 30], 0.95), 80)
        self.assertEqual(service._percentile([80, 10, 50, 30], 0.5), 50)
