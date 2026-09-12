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
            patch.object(main, "coordinate_schedule_slots", side_effect=RuntimeError("agent unavailable")),
        ):
            slots = main._recommend_schedule_for_record(1, self.record)
        self.assertEqual(slots[0]["starts_at"], "2026-09-14T12:30")
        self.assertEqual(slots[0]["ends_at"], "2026-09-14T13:30")
        self.assertTrue(all(slot["outside_preferred_window"] for slot in slots))
        self.assertTrue(all(slot["starts_at"].startswith("2026-09-14") for slot in slots))

    def test_full_day_does_not_suggest_another_date(self):
        busy = [{"inquiry_id": 2, "starts_at": "2026-09-14T09:00", "ends_at": "2026-09-15T00:00"}]
        with (
            patch.object(main, "scheduled_times", return_value=busy),
            patch.object(main, "get_change_request", return_value=None),
            patch.object(main, "coordinate_schedule_slots", side_effect=RuntimeError("agent unavailable")),
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
            patch.object(main, "coordinate_schedule_slots", side_effect=RuntimeError("agent unavailable")),
        ):
            slots = main._recommend_schedule_for_record(1, self.record)

        for left, right in zip(slots, slots[1:]):
            self.assertLessEqual(main._parse_datetime(left["ends_at"]), main._parse_datetime(right["starts_at"]))
        self.assertEqual(slots[0]["starts_at"], "2026-09-14T10:30")
        self.assertTrue(all(not slot.get("outside_preferred_window") for slot in slots))

    def test_buffer_applies_before_an_existing_booking(self):
        busy = [{"inquiry_id": 2, "starts_at": "2026-09-14T10:00", "ends_at": "2026-09-14T11:00"}]
        self.assertTrue(main._slots_overlap(
            main._parse_datetime("2026-09-14T09:00"),
            main._parse_datetime("2026-09-14T09:45"),
            busy,
        ))
        self.assertFalse(main._slots_overlap(
            main._parse_datetime("2026-09-14T08:30"),
            main._parse_datetime("2026-09-14T09:30"),
            busy,
        ))

    def test_agent_can_rank_only_server_generated_options(self):
        coordination = {
            "decision": {"selected_option_ids": ["preferred-2", "preferred-1"], "summary": "Best spacing"},
            "activity": ["Ranked safe options for photographer review"],
        }
        with (
            patch.object(main, "scheduled_times", return_value=[]),
            patch.object(main, "get_change_request", return_value=None),
            patch.object(main, "coordinate_schedule_slots", return_value=coordination),
        ):
            result = main._schedule_recommendation_result(1, self.record)
        self.assertEqual(result["suggestions"][0]["starts_at"], "2026-09-14T10:00")
        self.assertEqual(result["suggestions"][1]["starts_at"], "2026-09-14T09:00")
        self.assertTrue(result["agent_used_tools"])

    def test_hallucinated_agent_option_is_not_accepted(self):
        coordination = {
            "decision": {"selected_option_ids": ["invented-99"], "summary": "Invalid output"},
            "activity": ["Ranked safe options for photographer review"],
        }
        with (
            patch.object(main, "scheduled_times", return_value=[]),
            patch.object(main, "get_change_request", return_value=None),
            patch.object(main, "coordinate_schedule_slots", return_value=coordination),
        ):
            result = main._schedule_recommendation_result(1, self.record)
        self.assertEqual(result["suggestions"][0]["starts_at"], "2026-09-14T09:00")
        self.assertNotIn("option_id", result["suggestions"][0])
        self.assertFalse(result["agent_used_tools"])

    def test_reschedule_agent_receives_current_booking_and_prior_rounds(self):
        record = {**self.record, "call_time": "2026-09-14T08:00", "meeting_location": "Seattle"}
        change = {"status": "PENDING", "source_message": "Please try afternoon", "assessment": {"schedule_change": {"shoot_date": "2026-09-15", "availability_windows": ["12:00–17:00"]}}, "history": [{"source_message": "Morning did not work", "status": "AWAITING_CLIENT"}]}
        captured = {}
        def coordinate(_id, **kwargs):
            captured.update(kwargs["get_change_history"]())
            return {"decision": {"selected_option_ids": ["preferred-1"], "summary": "Afternoon matches the new request."}, "activity": ["Reviewed current booking and 1 prior preference round", "Ranked safe options for photographer review"]}
        with patch.object(main, "scheduled_times", return_value=[]), patch.object(main, "get_change_request", return_value=change), patch.object(main, "coordinate_schedule_slots", side_effect=coordinate):
            result = main._schedule_recommendation_result(1, record)
        self.assertEqual(captured["current_booking"]["starts_at"], "2026-09-14T08:00")
        self.assertEqual(len(captured["previous_rounds"]), 1)
        self.assertEqual(result["suggestions"][0]["starts_at"], "2026-09-15T12:00")


if __name__ == "__main__":
    unittest.main()
