import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import main, storage
from app.models import Inquiry, ScheduleChangeRequest


class ScheduleChangeRoundTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "shotcraft.db"
        self.db_patch = patch.object(storage, "DB_PATH", self.db_path)
        self.db_patch.start()
        inquiry = Inquiry(
            client_name="Client",
            client_email="client@example.com",
            photographer_email="photo@example.com",
            message="Portrait",
            shoot_date="2026-10-10",
            duration_minutes=60,
            availability_windows=["09:00–12:00"],
        )
        self.inquiry_id = storage.save_inquiry(inquiry)

    def tearDown(self):
        self.db_patch.stop()
        self.tempdir.cleanup()

    def test_new_preferences_supersede_options_and_preserve_previous_round(self):
        first = {"schedule_change": {"shoot_date": "2026-10-11", "availability_windows": ["09:00–12:00"]}}
        storage.save_change_request(self.inquiry_id, "First request", first)
        storage.save_schedule_suggestions(self.inquiry_id, "photo@example.com", [{
            "starts_at": "2026-10-11T09:00", "ends_at": "2026-10-11T10:00",
            "location": "Seattle", "rationale": "Available",
        }])
        self.assertEqual(storage.get_change_request(self.inquiry_id)["status"], "AWAITING_CLIENT")

        second = {"schedule_change": {"shoot_date": "2026-10-12", "availability_windows": ["12:00–17:00"]}}
        storage.save_change_request(self.inquiry_id, "Second request", second)

        request = storage.get_change_request(self.inquiry_id)
        self.assertEqual(request["source_message"], "Second request")
        self.assertEqual(len(request["history"]), 1)
        self.assertEqual(request["history"][0]["source_message"], "First request")
        self.assertEqual(storage.get_schedule_request(self.inquiry_id)["status"], "SUPERSEDED")

    def test_schedule_summary_exposes_client_action_state(self):
        storage.save_schedule_suggestions(self.inquiry_id, "photo@example.com", [{
            "starts_at": "2026-10-11T09:00", "ends_at": "2026-10-11T10:00",
            "location": "Seattle", "rationale": "Available",
        }])
        summary = storage.schedule_request_summaries([self.inquiry_id])[self.inquiry_id]
        self.assertEqual(summary["status"], "PENDING_CLIENT")
        self.assertEqual(len(summary["suggestions"]), 1)

    def test_client_request_preserves_booking_and_saves_agent_review(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute("UPDATE inquiries SET status='SCHEDULED', call_time='2026-10-10T10:00', meeting_location='Seattle' WHERE id=?", (self.inquiry_id,))
            db.commit()
        slot = {"starts_at": "2026-10-12T13:00", "ends_at": "2026-10-12T14:00", "location": "Seattle", "rationale": "Free after the required buffer"}
        review = {"suggestions": [slot], "summary": "A clear afternoon option fits the client's new window.", "agent_activity": ["Reviewed current booking and 0 prior preference rounds", "Checked 1 confirmed booking", "Ranked safe options for photographer review"], "agent_used_tools": True}
        user_request = SimpleNamespace(state=SimpleNamespace(user={"user_type": "client", "email": "client@example.com", "name": "Client"}))
        with patch.object(main, "_schedule_recommendation_result", return_value=review), patch.object(main, "add_inquiry_message"):
            result = main.request_schedule_change(self.inquiry_id, ScheduleChangeRequest(shoot_date="2026-10-12", availability_windows=["12:00–17:00"]), user_request)
        self.assertEqual(result["suggestion_count"], 1)
        self.assertEqual(storage.get_inquiry(self.inquiry_id)["call_time"], "2026-10-10T10:00")
        self.assertEqual(storage.get_schedule_request(self.inquiry_id)["status"], "PENDING_PHOTOGRAPHER_REVIEW")
        self.assertEqual(storage.get_change_request(self.inquiry_id)["assessment"]["agent_review"]["summary"], review["summary"])
        self.assertEqual(storage.get_planning_workflow(self.inquiry_id)["status"], "WAITING_FOR_PHOTOGRAPHER")


if __name__ == "__main__":
    unittest.main()
