"""Messages stay in the inbox; notification history tracks workflow events."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import storage


class NotificationMessageSeparationTests(unittest.TestCase):
    def test_client_decisions_stay_out_of_notifications(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, "DB_PATH", Path(directory) / "shotcraft.db"):
            with sqlite3.connect(storage.DB_PATH) as db:
                storage._ensure_schema(db)
                db.executemany(
                    "INSERT INTO inquiries(id, client_email, payload, status, analysis) VALUES(?, ?, ?, ?, ?)",
                    [
                        (1, "client@example.com", json.dumps({"client_name": "Client", "photographer_email": "photo@example.com"}), "NEEDS_INFORMATION", json.dumps({"missing_information": ["wardrobe"]})),
                        (2, "client@example.com", json.dumps({"client_name": "Client", "photographer_email": "photo@example.com"}), "SCHEDULED", json.dumps({})),
                    ],
                )
                db.execute("UPDATE inquiries SET call_time='2026-09-25T18:00' WHERE id=2")

            client = storage.list_client_notifications("client@example.com")
            photographer = storage.list_photographer_notifications("photo@example.com")
            confirmed = next(item for item in client if item["notification_type"] == "SHOOT_CONFIRMED")
            photographer_confirmed = next(item for item in photographer if item["notification_type"] == "SHOOT_CONFIRMED")
            self.assertFalse(any(item["notification_type"] == "FOLLOWUP_REQUESTED" for item in client))
            self.assertFalse(confirmed["action_required"])
            self.assertFalse(photographer_confirmed["action_required"])

    def test_old_client_decision_notifications_are_removed(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, "DB_PATH", Path(directory) / "shotcraft.db"):
            with sqlite3.connect(storage.DB_PATH) as db:
                storage._ensure_schema(db)
                db.execute("INSERT INTO inquiries(id, client_email, payload, status) VALUES(1, ?, '{}', 'NEEDS_INFORMATION')", ("client@example.com",))
                db.execute("INSERT INTO client_notifications(client_email, inquiry_id, notification_type, event_key, title, body, target_view, action_required) "
                           "VALUES('client@example.com', 1, 'FOLLOWUP_REQUESTED', 'old-client-decision', 'More details needed', 'Answer questions', 'followup', 1)")

            notifications = storage.list_client_notifications("client@example.com")
            self.assertFalse(any(item["event_key"] == "old-client-decision" for item in notifications))

    def test_saved_plan_notifications_use_new_copy_without_resetting_read_state(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, "DB_PATH", Path(directory) / "shotcraft.db"):
            with sqlite3.connect(storage.DB_PATH) as db:
                storage._ensure_schema(db)
                db.execute(
                    "INSERT INTO inquiries(id, client_email, payload, status) VALUES(1, ?, ?, 'NEW')",
                    ("client@example.com", json.dumps({"client_name": "Client", "photographer_email": "photo@example.com"})),
                )
                db.execute(
                    "INSERT INTO client_notifications(id, client_email, inquiry_id, notification_type, event_key, title, body, target_view, read_at) "
                    "VALUES(101, 'client@example.com', 1, 'PLAN_READY', 'old-client-plan', 'Production plan ready', 'Review the production plan.', 'plan', '2026-09-12 12:00:00')"
                )
                db.execute(
                    "INSERT INTO photographer_notifications(id, photographer_email, inquiry_id, notification_type, event_key, title, body, target_view) "
                    "VALUES(102, 'photo@example.com', 1, 'PLAN_READY', 'old-photographer-plan', 'Production plan ready', 'Share the production plan.', 'production')"
                )

            client = next(item for item in storage.list_client_notifications("client@example.com") if item["id"] == 101)
            photographer = next(item for item in storage.list_photographer_notifications("photo@example.com") if item["id"] == 102)
            self.assertEqual((client["title"], client["body"]), ("Shoot plan ready", "Review the shoot plan."))
            self.assertEqual(client["read_at"], "2026-09-12 12:00:00")
            self.assertEqual((photographer["title"], photographer["body"]), ("Shoot plan ready", "Share the shoot plan."))
            self.assertIsNone(photographer["read_at"])

    def test_cancellation_decision_creates_one_persistent_client_notification(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, "DB_PATH", Path(directory) / "shotcraft.db"):
            with sqlite3.connect(storage.DB_PATH) as db:
                storage._ensure_schema(db)
                db.execute(
                    "INSERT INTO inquiries(id, client_email, payload, status, cancellation_status, cancellation_fee, cancellation_refund, cancellation_reviewed_at) VALUES(1, ?, ?, 'CANCELLED', 'APPROVED', 50, 50, '2026-09-12 12:00:00')",
                    ("client@example.com", json.dumps({"style_direction": "Seattle portraits"})),
                )
            first = storage.list_client_notifications("client@example.com")
            self.assertEqual(len(first), 1)
            self.assertEqual(first[0]["notification_type"], "SHOOT_CANCELLED")
            self.assertEqual(first[0]["target_view"], "plan")
            self.assertFalse(first[0]["action_required"])
            self.assertTrue(storage.mark_client_notification_read(first[0]["id"], "client@example.com"))
            second = storage.list_client_notifications("client@example.com")
            self.assertEqual(len(second), 1)
            self.assertEqual(second[0]["id"], first[0]["id"])
            self.assertIsNotNone(second[0]["read_at"])

    def test_messages_do_not_appear_in_either_notification_feed(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, "DB_PATH", Path(directory) / "shotcraft.db"):
            with sqlite3.connect(storage.DB_PATH) as db:
                storage._ensure_schema(db)
                db.execute(
                    "INSERT INTO inquiries(id, client_email, payload, status) VALUES(1, ?, ?, ?)",
                    ("client@example.com", json.dumps({"client_name": "Client", "photographer_email": "photo@example.com"}), "READY_FOR_REVIEW"),
                )
                db.execute(
                    "INSERT INTO inquiries(id, client_email, payload, status, production_approved) VALUES(2, ?, ?, ?, 1)",
                    ("client@example.com", json.dumps({"client_name": "Client", "photographer_email": "photo@example.com"}), "READY_FOR_REVIEW"),
                )
                db.executemany(
                    "INSERT INTO inquiry_messages(inquiry_id, sender_role, sender_name, body) VALUES(1, ?, ?, ?)",
                    [("client", "Client", "Hello"), ("photographer", "Photographer", "Hi")],
                )
                db.executemany(
                    "INSERT INTO client_notifications(client_email, inquiry_id, notification_type, event_key, title, body, target_view) VALUES(?, 1, 'NEW_MESSAGE', ?, 'Message', 'Old entry', 'messages')",
                    [("client@example.com", "old-client-message")],
                )
                db.execute(
                    "INSERT INTO photographer_notifications(photographer_email, inquiry_id, notification_type, event_key, title, body, target_view) VALUES(?, 1, 'NEW_MESSAGE', ?, 'Message', 'Old entry', 'messages')",
                    ("photo@example.com", "old-photographer-message"),
                )

            client = storage.list_client_notifications("client@example.com")
            photographer = storage.list_photographer_notifications("photo@example.com")
            self.assertFalse(any(item["notification_type"] == "NEW_MESSAGE" for item in client + photographer))
            self.assertFalse(any(item["notification_type"] == "INQUIRY_READY" for item in photographer))
            with sqlite3.connect(storage.DB_PATH) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM inquiry_messages").fetchone()[0], 2)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM client_notifications WHERE notification_type='NEW_MESSAGE'").fetchone()[0], 0)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM photographer_notifications WHERE notification_type='NEW_MESSAGE'").fetchone()[0], 0)

    def test_photographer_decisions_do_not_create_notifications_and_old_ones_resolve(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, "DB_PATH", Path(directory) / "shotcraft.db"):
            with sqlite3.connect(storage.DB_PATH) as db:
                storage._ensure_schema(db)
                db.execute("INSERT INTO inquiries(id, client_email, payload, status) VALUES(1, ?, ?, 'READY_FOR_REVIEW')",
                           ("client@example.com", json.dumps({"client_name": "Client", "photographer_email": "photo@example.com"})))
                db.execute("INSERT INTO photographer_notifications(photographer_email, inquiry_id, notification_type, event_key, title, body, target_view, action_required) "
                           "VALUES('photo@example.com', 1, 'INQUIRY_READY', 'old-decision', 'Ready', 'Review', 'project', 1)")

            notifications = storage.list_photographer_notifications("photo@example.com")
            self.assertEqual(len(notifications), 1)
            self.assertEqual(notifications[0]["event_key"], "old-decision")
            self.assertIsNotNone(notifications[0]["resolved_at"])
            self.assertFalse(any(item["event_key"] == "inquiry-ready:1" for item in notifications))

    def test_followup_completion_is_one_informational_photographer_update(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, "DB_PATH", Path(directory) / "shotcraft.db"):
            with sqlite3.connect(storage.DB_PATH) as db:
                storage._ensure_schema(db)
                db.execute(
                    "INSERT INTO inquiries(id, client_email, payload, status, analysis) VALUES(1, ?, ?, 'DRAFTING_PLAN', ?)",
                    ("client@example.com", json.dumps({"client_name": "Client", "photographer_email": "photo@example.com", "style_direction": "Seattle portraits"}), json.dumps({"concept_name": "Seattle portraits", "missing_information": []})),
                )
                db.execute(
                    "INSERT INTO inquiry_followups(inquiry_id, answers) VALUES(1, ?)",
                    ("The client supplied the missing creative details.",),
                )

            notifications = storage.list_photographer_notifications("photo@example.com")
            complete = [item for item in notifications if item["notification_type"] == "FOLLOWUP_COMPLETE"]
            self.assertEqual(len(complete), 1)
            self.assertFalse(complete[0]["action_required"])
            self.assertIn("generating the creative brief and moodboard", complete[0]["body"])

            # Materialization is idempotent for the same completed follow-up.
            refreshed = storage.list_photographer_notifications("photo@example.com")
            self.assertEqual(len([item for item in refreshed if item["notification_type"] == "FOLLOWUP_COMPLETE"]), 1)

    def test_time_change_submission_creates_one_informational_client_notification(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, "DB_PATH", Path(directory) / "shotcraft.db"):
            with sqlite3.connect(storage.DB_PATH) as db:
                storage._ensure_schema(db)
                db.execute(
                    "INSERT INTO inquiries(id, client_email, payload, status, analysis) VALUES(1, ?, ?, 'SCHEDULED', ?)",
                    (
                        "client@example.com",
                        json.dumps({"client_name": "Client", "photographer_email": "photo@example.com", "style_direction": "Seattle portraits"}),
                        json.dumps({"concept_name": "Seattle portraits"}),
                    ),
                )
            storage.save_change_request(
                1,
                "Schedule change request\nRequested date: Oct 12, 2026\nPreferred time windows: Afternoon",
                {"schedule_change": {"shoot_date": "2026-10-12", "availability_windows": ["12:00–17:00"]}},
            )

            first = storage.list_client_notifications("client@example.com")
            submitted = [item for item in first if item["notification_type"] == "TIME_CHANGE_REQUESTED"]
            self.assertEqual(len(submitted), 1)
            self.assertEqual(submitted[0]["title"], "Time change request sent")
            self.assertEqual(submitted[0]["target_view"], "details")
            self.assertFalse(submitted[0]["action_required"])
            self.assertIsNone(submitted[0]["read_at"])
            self.assertIn("current booking stays confirmed", submitted[0]["body"])

            # Refreshing the notification feed does not duplicate the same request round.
            refreshed = storage.list_client_notifications("client@example.com")
            self.assertEqual(len([item for item in refreshed if item["notification_type"] == "TIME_CHANGE_REQUESTED"]), 1)


if __name__ == "__main__":
    unittest.main()
