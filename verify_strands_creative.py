"""Live, read-only proof of Strands creative tool orchestration.

Run with ``python verify_strands_creative.py``. This calls Bedrock but does not
render images, create a project, or change the application database.
"""

import json

from app.agent import coordinate_creative_direction, coordinate_inquiry_intake
from app.models import Inquiry


def main() -> None:
    inquiry = Inquiry(
        client_name="Demo client", client_email="demo@example.com",
        photographer_email="demo-photographer@example.com",
        message="An outdoor editorial portrait in Seattle with soft morning light and natural poses, for my personal portfolio.",
        shoot_date="2027-06-16", duration_minutes=60,
        availability_windows=["09:00–12:00"], location="Seattle, WA",
        subject_presentation="one woman", subject_count=1,
        wardrobe_details="blue linen dress", deliverable_count=10,
        budget=500, style_direction="natural editorial",
    )
    intake = coordinate_inquiry_intake(9001, inquiry, [])
    if not intake["agent_used_tools"] or intake["analysis"].missing_information:
        raise AssertionError("Live Strands intake did not complete the required tool checks")
    saved: dict = {}
    result = coordinate_creative_direction(
        9001, inquiry, [],
        on_brief=lambda brief: saved.update(brief=brief),
        on_moodboard=lambda moodboard: saved.update(moodboard=moodboard),
    )
    if not result["agent_used_tools"] or not saved.get("brief") or not saved.get("moodboard"):
        raise AssertionError("Creative tool loop did not finish")
    print(json.dumps({
        "live_strands_creative": "passed",
        "agent_used_tools": result["agent_used_tools"],
        "intake_activity": intake["activity"],
        "intake_missing_information": intake["analysis"].missing_information,
        "agent_activity": result["activity"],
        "brief": saved["brief"].concept_name,
        "moodboard": saved["moodboard"].title,
        "planned_tiles": len(saved["moodboard"].tiles),
    }, indent=2))


if __name__ == "__main__":
    main()
