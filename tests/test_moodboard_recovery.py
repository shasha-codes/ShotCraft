import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import main
from app.models import CreativeBrief, Inquiry


class MoodboardRecoveryTests(unittest.TestCase):
    def test_automatic_plan_failure_is_persisted_as_failed(self):
        inquiry = Inquiry(client_name="Test client", client_email="test@example.com", message="Portrait shoot", deliverable_count=10)
        analysis = SimpleNamespace(missing_information=[], model_dump=lambda: {})
        brief = CreativeBrief(
            concept_name="Test", creative_summary="Portrait", shoot_type="portrait",
            location_direction="studio", lighting_direction="soft", posing_direction="standing",
            wardrobe_direction="casual", budget_notes="within budget", deliverables=["10 images"],
        )
        saved = []
        with (
            patch.object(main, "analyze_inquiry", return_value=analysis),
            patch.object(main, "create_creative_brief", return_value=brief),
            patch.object(main, "create_moodboard", side_effect=RuntimeError("provider unavailable")) as create_plan,
            patch.object(main, "save_creative_brief") as save_brief,
            patch.object(main, "save_moodboard", side_effect=lambda _id, data: saved.append(data)),
            patch.object(main, "update_analysis"),
            patch.object(main, "record_event"),
        ):
            main.process_inquiry(99991, inquiry)
        self.assertEqual(saved[-1]["status"], "failed")
        self.assertEqual(saved[-1]["moodboard"]["tiles"], [])
        self.assertEqual(saved[0]["job_id"], saved[-1]["job_id"])
        create_plan.assert_called_once()
        save_brief.assert_called_once()

    def test_orphaned_generation_becomes_interrupted_on_read(self):
        placeholder = {"status": "generating", "moodboard": {"title": "Preparing", "tiles": []}}
        record = {"id": 99992, "moodboard": json.dumps(placeholder)}
        with (
            patch.object(main, "list_inquiries", return_value=[record]),
            patch.object(main, "save_moodboard") as save,
            patch.object(main, "change_request_summaries", return_value={}),
            patch.object(main, "list_inquiry_followups", return_value=[]),
            patch.object(main, "inquiry_timeline", return_value={}),
            patch.object(main, "pre_shoot_checkin_summaries", return_value={}),
        ):
            result = main.get_inquiry_detail(99992)
        self.assertEqual(json.loads(result["moodboard"])["status"], "interrupted")
        self.assertEqual(save.call_args.args[1]["status"], "interrupted")


if __name__ == "__main__":
    unittest.main()
