import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app import main
from app.models import Inquiry


class ScheduleAlternativeTests(unittest.TestCase):
    def setUp(self):
        self.inquiry = Inquiry(
            client_name="Client", client_email="client@example.com",
            photographer_email="photographer@example.com", message="Portrait shoot",
            shoot_date="2026-09-14", duration_minutes=60,
            availability_windows=["09:00–12:00"], location="Seattle",
        )
        self.record = {"payload": self.inquiry.model_dump_json()}

    def test_full_preferred_window_offers_later_same_day(self):
        busy = [{"inquiry_id": 2, "starts_at": "2026-09-14T09:00", "ends_at": "2026-09-14T12:00"}]
        with (
            patch.object(main, "scheduled_times", return_value=busy),
            patch.object(main, "get_change_request", return_value=None),
            patch.object(main, "recommend_schedule_slots", return_value=[]),
        ):
            slots = main._recommend_schedule_for_record(1, self.record)
        self.assertEqual(slots[0]["starts_at"], "2026-09-14T12:00")
        self.assertEqual(slots[0]["ends_at"], "2026-09-14T13:00")
        self.assertTrue(all(slot["outside_preferred_window"] for slot in slots))
        self.assertTrue(all(slot["starts_at"].startswith("2026-09-14") for slot in slots))

    def test_full_day_does_not_suggest_another_date(self):
        busy = [{"inquiry_id": 2, "starts_at": "2026-09-14T09:00", "ends_at": "2026-09-15T00:00"}]
        with (
            patch.object(main, "scheduled_times", return_value=busy),
            patch.object(main, "get_change_request", return_value=None),
            patch.object(main, "recommend_schedule_slots", return_value=[]),
        ):
            with self.assertRaises(HTTPException) as raised:
                main._recommend_schedule_for_record(1, self.record)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertIn("another date", raised.exception.detail)

    def test_prefers_available_requested_window(self):
        busy = [{"inquiry_id": 2, "starts_at": "2026-09-14T09:00", "ends_at": "2026-09-14T10:00"}]
        with (
            patch.object(main, "scheduled_times", return_value=busy),
            patch.object(main, "get_change_request", return_value=None),
            patch.object(main, "recommend_schedule_slots", return_value=[]),
        ):
            slots = main._recommend_schedule_for_record(1, self.record)
        self.assertEqual(slots[0]["starts_at"], "2026-09-14T10:00")
        self.assertTrue(all(not slot.get("outside_preferred_window") for slot in slots))


if __name__ == "__main__":
    unittest.main()
