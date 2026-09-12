import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import storage
from app.models import Inquiry


class CancellationWorkflowTests(unittest.TestCase):
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
            budget=400,
        )
        self.inquiry_id = storage.save_inquiry(inquiry)
        with sqlite3.connect(self.db_path) as db:
            storage._ensure_schema(db)
            db.execute(
                "UPDATE inquiries SET status='SCHEDULED', production_pack='{}', production_approved=1, call_time='2026-10-10T10:00', cancellation_policy='{}', cancellation_policy_accepted_at=CURRENT_TIMESTAMP WHERE id=?",
                (self.inquiry_id,),
            )
            db.execute(
                "INSERT INTO schedule_requests (inquiry_id, photographer_email, suggestions, selected_starts_at, selected_ends_at, selected_location, status) VALUES (?, ?, ?, ?, ?, ?, 'CONFIRMED')",
                (self.inquiry_id, "photo@example.com", json.dumps([]), "2026-10-10T10:00", "2026-10-10T11:00", "Seattle"),
            )
            db.commit()

    def tearDown(self):
        self.db_patch.stop()
        self.tempdir.cleanup()

    def test_approval_cancels_and_releases_booking(self):
        self.assertTrue(storage.request_cancellation(self.inquiry_id, "Plans changed", None, 100, 300, 30))
        self.assertTrue(storage.decide_cancellation(self.inquiry_id, True, "POLICY", 100, 300))
        record = storage.get_inquiry(self.inquiry_id)
        self.assertEqual(record["status"], "CANCELLED")
        self.assertEqual(record["cancellation_fee"], 100)
        with sqlite3.connect(self.db_path) as db:
            status = db.execute("SELECT status FROM schedule_requests WHERE inquiry_id=?", (self.inquiry_id,)).fetchone()[0]
        self.assertEqual(status, "RELEASED")

    def test_decline_keeps_booking_and_closes_request(self):
        self.assertTrue(storage.request_cancellation(self.inquiry_id, "Plans changed", None, 100, 300, 30))
        self.assertTrue(storage.decide_cancellation(self.inquiry_id, False))
        record = storage.get_inquiry(self.inquiry_id)
        self.assertEqual(record["status"], "SCHEDULED")
        self.assertEqual(record["cancellation_status"], "DECLINED")
        with sqlite3.connect(self.db_path) as db:
            status = db.execute("SELECT status FROM schedule_requests WHERE inquiry_id=?", (self.inquiry_id,)).fetchone()[0]
        self.assertEqual(status, "CONFIRMED")


if __name__ == "__main__":
    unittest.main()
