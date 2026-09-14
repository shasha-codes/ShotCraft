import json
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import main
from app.models import CreativeBrief, Inquiry, Moodboard, MoodboardTile


class MoodboardRecoveryTests(unittest.TestCase):
    def test_production_pack_build_overlaps_image_rendering(self):
        inquiry = Inquiry(client_name="Test client", client_email="test@example.com", message="Portrait shoot", deliverable_count=10)
        analysis = SimpleNamespace(missing_information=[], model_dump=lambda: {})
        brief = CreativeBrief(
            concept_name="Test", creative_summary="Portrait", shoot_type="portrait",
            location_direction="studio", lighting_direction="soft", posing_direction="standing",
            wardrobe_direction="casual", budget_notes="within budget", deliverables=["10 images"],
        )
        moodboard = Moodboard(
            title="Portrait board", creative_direction="soft",
            tiles=[MoodboardTile(title="Hero", visual_prompt="portrait", caption="hero", styling_notes="soft")],
        )
        plan_started = threading.Event()
        images_started = threading.Event()

        def direction(_id, _inquiry, _followups, on_brief, on_moodboard):
            on_brief(brief)
            on_moodboard(moodboard)
            return {"moodboard": moodboard, "agent_used_tools": True, "activity": []}

        def build_plan(*_args):
            plan_started.set()
            self.assertTrue(images_started.wait(1), "image rendering did not start while the plan was building")
            return SimpleNamespace(model_dump=lambda: {"title": "Plan"})

        def render_images(*_args, **_kwargs):
            images_started.set()
            self.assertTrue(plan_started.wait(1), "production planning did not start before image rendering completed")
            return SimpleNamespace(model_dump=lambda: {"title": "Board", "tiles": []})

        with (
            patch.object(main, "coordinate_inquiry_intake", return_value={"analysis": analysis, "activity": [], "agent_used_tools": True}),
            patch.object(main, "coordinate_creative_direction", side_effect=direction),
            patch.object(main, "build_production_pack", side_effect=build_plan),
            patch.object(main, "generate_moodboard_images", side_effect=render_images),
            patch.object(main, "list_inquiry_followups", return_value=[]),
            patch.object(main, "save_creative_brief"), patch.object(main, "save_moodboard"),
            patch.object(main, "save_production_pack") as save_pack,
            patch.object(main, "update_analysis"), patch.object(main, "update_planning_workflow"),
            patch.object(main, "record_event"), patch.object(main, "notify_client_followups_complete"),
        ):
            main.process_inquiry(99990, inquiry)

        save_pack.assert_called_once_with(99990, {"title": "Plan"}, draft=True)

    def test_automatic_plan_failure_is_persisted_as_failed(self):
        inquiry = Inquiry(client_name="Test client", client_email="test@example.com", message="Portrait shoot", deliverable_count=10)
        analysis = SimpleNamespace(missing_information=[], model_dump=lambda: {})
        brief = CreativeBrief(
            concept_name="Test", creative_summary="Portrait", shoot_type="portrait",
            location_direction="studio", lighting_direction="soft", posing_direction="standing",
            wardrobe_direction="casual", budget_notes="within budget", deliverables=["10 images"],
        )
        saved = []
        def interrupted_direction(_id, _inquiry, _followups, on_brief, _on_moodboard):
            on_brief(brief)
            raise RuntimeError("provider unavailable")
        with (
            patch.object(main, "coordinate_inquiry_intake", return_value={"analysis": analysis, "activity": [], "agent_used_tools": True}),
            patch.object(main, "coordinate_creative_direction", side_effect=interrupted_direction) as create_plan,
            patch.object(main, "list_inquiry_followups", return_value=[]),
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
