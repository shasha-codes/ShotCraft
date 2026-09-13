import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import main, storage
from app.models import CancellationDecision, CancellationRequest, Inquiry, InquiryMessageCreate


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

    def test_agent_review_waits_for_photographer_and_keeps_booking(self):
        class Tasks:
            def __init__(self):
                self.pending = []

            def add_task(self, function, *args):
                self.pending.append((function, args))

        tasks = Tasks()
        client = SimpleNamespace(state=SimpleNamespace(user={"user_type": "client", "email": "client@example.com", "name": "Client"}))
        photographer = SimpleNamespace(state=SimpleNamespace(user={"user_type": "photographer", "email": "photo@example.com", "name": "Photographer"}))
        result = main.create_cancellation_request(self.inquiry_id, CancellationRequest(reason="Plans changed", note="Need another date"), client, tasks)
        self.assertEqual(result["status"], "PENDING")
        self.assertEqual(storage.get_cancellation_agent_review(self.inquiry_id)["status"], "RUNNING")
        self.assertEqual(len(tasks.pending), 1)

        def fake_agent(_id, get_booking, get_policy, get_request, get_history):
            self.assertEqual(get_booking()["status"], "SCHEDULED")
            self.assertEqual(get_booking()["booking_amount"], 400)
            self.assertEqual(get_policy()["policy_fee"], result["suggested_fee"])
            self.assertEqual(get_request()["reason"], "Plans changed")
            self.assertTrue(any(item["milestone"] == "Cancellation requested" for item in get_history()))
            return {"decision": {"recommended_action": "MESSAGE_FIRST", "rationale": "The client may prefer to reschedule the booking.", "message_draft": "Would a new date work for you?"}, "activity": ["Read the confirmed booking", "Checked the accepted cancellation policy and calculated fee", "Read the client's cancellation reason and note", "Reviewed 2 project milestones"]}

        with patch.object(main, "coordinate_cancellation_review", side_effect=fake_agent):
            function, args = tasks.pending[0]
            function(*args)
        review = main.cancellation_agent_review(self.inquiry_id, photographer)
        self.assertEqual(review["status"], "COMPLETE")
        self.assertEqual(review["review"]["decision"]["recommended_action"], "MESSAGE_FIRST")
        self.assertEqual(storage.get_inquiry(self.inquiry_id)["status"], "SCHEDULED")
        self.assertEqual(storage.get_inquiry(self.inquiry_id)["cancellation_status"], "PENDING")
        decision = main.review_cancellation(self.inquiry_id, "approve", CancellationDecision(fee_mode="WAIVED", message="I can waive the fee."), photographer)
        self.assertEqual(decision["status"], "CANCELLED")
        self.assertEqual(decision["cancellation_fee"], 0)
        self.assertEqual(storage.get_inquiry(self.inquiry_id)["status"], "CANCELLED")
        with sqlite3.connect(self.db_path) as db:
            booking_status = db.execute("SELECT status FROM schedule_requests WHERE inquiry_id=?", (self.inquiry_id,)).fetchone()[0]
        self.assertEqual(booking_status, "RELEASED")

    def test_agent_failure_does_not_decide_cancellation(self):
        self.assertTrue(storage.request_cancellation(self.inquiry_id, "Plans changed", None, 100, 300, 30))
        storage.save_cancellation_agent_review(self.inquiry_id, "RUNNING")
        with patch.object(main, "coordinate_cancellation_review", side_effect=RuntimeError("Model unavailable")):
            main.run_cancellation_agent_review(self.inquiry_id)
        self.assertEqual(storage.get_cancellation_agent_review(self.inquiry_id)["status"], "UNAVAILABLE")
        self.assertEqual(storage.get_inquiry(self.inquiry_id)["status"], "SCHEDULED")
        self.assertEqual(storage.get_inquiry(self.inquiry_id)["cancellation_status"], "PENDING")

    def test_cancellation_draft_is_returned_unchanged_and_placeholder_is_flagged(self):
        storage.save_cancellation_agent_review(self.inquiry_id, "COMPLETE", {
            "decision": {
                "recommended_action": "APPROVE",
                "rationale": "Within the policy.",
                "message_draft": "I can help with this cancellation. Best regards, [Photographer's Name]",
            },
        })
        photographer = SimpleNamespace(state=SimpleNamespace(user={
            "user_type": "photographer", "email": "photo@example.com", "name": "Alex Rivera",
        }))
        result = main.cancellation_agent_review(self.inquiry_id, photographer)
        draft = result["review"]["decision"]["message_draft"]
        self.assertEqual(draft, "I can help with this cancellation. Best regards, [Photographer's Name]")
        self.assertIn("draft_issue", result)

    def test_cancellation_draft_with_relative_date_is_flagged_not_rewritten(self):
        storage.save_cancellation_agent_review(self.inquiry_id, "COMPLETE", {
            "decision": {
                "recommended_action": "APPROVE",
                "rationale": "Within the policy.",
                "message_draft": "Your Seattle shoot is scheduled for today at 10 AM.\n\nBest regards,\nAlex Rivera\nphoto@example.com",
            },
            "agent_execution": "local-strands",
        })
        photographer = SimpleNamespace(state=SimpleNamespace(user={
            "user_type": "photographer", "email": "photo@example.com", "name": "Alex Rivera",
        }))
        result = main.cancellation_agent_review(self.inquiry_id, photographer)
        draft = result["review"]["decision"]["message_draft"]
        self.assertIn("scheduled for today", draft)
        self.assertEqual(draft.count("photo@example.com"), 1)
        self.assertIn("relative shoot date", result["draft_issue"])

    def test_cancellation_draft_with_alternate_placeholder_is_flagged(self):
        storage.save_cancellation_agent_review(self.inquiry_id, "COMPLETE", {
            "decision": {
                "recommended_action": "APPROVE",
                "rationale": "Within the policy.",
                "message_draft": "We can approve your request. Best regards, [Photographer Name] (ShotCraft)",
            },
        })
        photographer = SimpleNamespace(state=SimpleNamespace(user={
            "user_type": "photographer", "email": "photo@example.com", "name": "Alex Rivera",
        }))
        result = main.cancellation_agent_review(self.inquiry_id, photographer)
        draft = result["review"]["decision"]["message_draft"]
        self.assertIn("[Photographer Name]", draft)
        self.assertIn("draft_issue", result)
        self.assertEqual(draft.lower().count("best regards"), 1)

    def test_cancellation_draft_with_company_placeholder_is_flagged_not_rewritten(self):
        storage.save_cancellation_agent_review(self.inquiry_id, "COMPLETE", {
            "decision": {
                "recommended_action": "APPROVE",
                "rationale": "Within the policy.",
                "message_draft": "Your cancellation was approved and you will receive a full refund of $400. We will process the refund within the next 5‑7 business days. Best regards, [Your Company Name] Team",
            },
        })
        photographer = SimpleNamespace(state=SimpleNamespace(user={
            "user_type": "photographer", "email": "photo@example.com", "name": "Alex Rivera",
        }))
        result = main.cancellation_agent_review(self.inquiry_id, photographer)
        draft = result["review"]["decision"]["message_draft"]
        self.assertIn("5‑7 business days", draft)
        self.assertIn("Company Name", draft)
        self.assertIn("draft_issue", result)
        self.assertEqual(draft.lower().count("best regards"), 1)

    def test_cancellation_agent_receives_photographer_account_identity(self):
        self.assertTrue(storage.request_cancellation(self.inquiry_id, "Plans changed", None, 0, 400, 72))
        with patch.object(main, "get_photographer_identity", return_value={"name": "Alex Rivera", "email": "photo@example.com"}):
            def fake_agent(_id, get_booking, get_policy, get_request, get_history):
                self.assertEqual(get_booking()["photographer_name"], "Alex Rivera")
                self.assertEqual(get_booking()["photographer_email"], "photo@example.com")
                return {"decision": {"recommended_action": "APPROVE", "rationale": "Within policy.", "message_draft": "I can approve your request.\n\nBest regards,\nAlex Rivera\nphoto@example.com"}, "activity": []}
            with patch.object(main, "coordinate_cancellation_review", side_effect=fake_agent):
                main.run_cancellation_agent_review(self.inquiry_id)
        photographer = SimpleNamespace(state=SimpleNamespace(user={"user_type": "photographer", "email": "photo@example.com", "name": "Alex Rivera"}))
        result = main.cancellation_agent_review(self.inquiry_id, photographer)
        self.assertNotIn("draft_issue", result)
        self.assertEqual(result["review"]["decision"]["message_draft"], "I can approve your request.\n\nBest regards,\nAlex Rivera\nphoto@example.com")

    def test_photographer_can_queue_ai_regeneration_for_old_draft(self):
        self.assertTrue(storage.request_cancellation(self.inquiry_id, "Plans changed", None, 0, 400, 72))
        storage.save_cancellation_agent_review(self.inquiry_id, "COMPLETE", {
            "decision": {"recommended_action": "APPROVE", "rationale": "Within policy.", "message_draft": "Best regards, [Your Company Name]"},
        })
        tasks = SimpleNamespace(pending=[], add_task=lambda function, *args: tasks.pending.append((function, args)))
        photographer = SimpleNamespace(state=SimpleNamespace(user={"user_type": "photographer", "email": "photo@example.com", "name": "Alex Rivera"}))
        response = main.regenerate_cancellation_agent_review(self.inquiry_id, photographer, tasks)
        self.assertEqual(response["status"], "RUNNING")
        self.assertEqual(storage.get_cancellation_agent_review(self.inquiry_id)["status"], "RUNNING")
        self.assertEqual(tasks.pending[0][0], main.run_cancellation_agent_review)

    def test_message_first_and_client_reply_are_visible_without_closing_request(self):
        self.assertTrue(storage.request_cancellation(self.inquiry_id, "Plans changed", None, 100, 300, 30))
        storage.update_planning_workflow(self.inquiry_id, "CANCELLATION_REVIEW", "WAITING_FOR_PHOTOGRAPHER", "Ready for review")
        main.post_inquiry_message(self.inquiry_id, InquiryMessageCreate(body="Would another date work?", sender_role="photographer", sender_name="Photographer"), SimpleNamespace(add_task=lambda *args: None))
        detail = main.get_inquiry_detail(self.inquiry_id)
        self.assertIsNotNone(detail["cancellation_conversation"]["photographer_message"])
        self.assertIsNone(detail["cancellation_conversation"]["client_reply"])
        self.assertEqual(detail["planning_workflow"]["stage"], "CANCELLATION_CONTACTED")
        self.assertEqual(detail["status"], "SCHEDULED")
        self.assertEqual(detail["cancellation_status"], "PENDING")

        main.post_inquiry_message(self.inquiry_id, InquiryMessageCreate(body="Yes, let me think about it.", sender_role="client", sender_name="Client"), SimpleNamespace(add_task=lambda *args: None))
        detail = main.get_inquiry_detail(self.inquiry_id)
        self.assertIsNotNone(detail["cancellation_conversation"]["client_reply"])
        self.assertEqual(detail["planning_workflow"]["stage"], "CANCELLATION_CLIENT_REPLIED")
        self.assertEqual(detail["cancellation_status"], "PENDING")


if __name__ == "__main__":
    unittest.main()
