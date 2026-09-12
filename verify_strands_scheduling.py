"""Live, read-only Strands scheduling proof with and without a conflict.

Run with ``python verify_strands_scheduling.py``. This makes two real Bedrock
agent calls but does not write the application database or send proposals.
"""

import json
from unittest.mock import patch

from app import main
from app.models import Inquiry


def verify(name: str, busy: list[dict], earliest_allowed: str, outside_preference: bool) -> dict:
    inquiry = Inquiry(
        client_name="Demo client", client_email="demo@example.com",
        photographer_email="demo-photographer@example.com", message="Editorial portrait",
        shoot_date="2027-06-16", duration_minutes=60,
        availability_windows=["09:00–12:00"], location="Seattle, WA",
    )
    record = {"payload": inquiry.model_dump_json()}
    with patch.object(main, "scheduled_times", return_value=busy), patch.object(main, "get_change_request", return_value=None):
        result = main._schedule_recommendation_result(9001, record)
    if not result["agent_used_tools"]:
        raise AssertionError(f"{name}: scheduling used the deterministic fallback, not a completed Strands tool loop")
    if not result["suggestions"]:
        raise AssertionError(f"{name}: no options returned")
    for option in result["suggestions"]:
        start = main._parse_datetime(option["starts_at"])
        end = main._parse_datetime(option["ends_at"])
        if start < main._parse_datetime(earliest_allowed) or bool(option.get("outside_preferred_window")) != outside_preference:
            raise AssertionError(f"{name}: option is not in the expected safe window")
        if main._slots_overlap(start, end, busy):
            raise AssertionError(f"{name}: a suggested option conflicts with a confirmed booking")
        if int((end - start).total_seconds() / 60) != 60:
            raise AssertionError(f"{name}: a suggested option has the wrong duration")
    return {"case": name, "agent_used_tools": True, "agent_activity": result["agent_activity"], "suggestions": result["suggestions"]}


def main_run() -> None:
    cases = [
        verify("preferred window free", [], "2027-06-16T09:00", False),
        verify("preferred window occupied", [{"inquiry_id": 9002, "starts_at": "2027-06-16T09:00", "ends_at": "2027-06-16T12:00"}], "2027-06-16T12:30", True),
    ]
    print(json.dumps({"live_strands_scheduling": "passed", "cases": cases}, indent=2))
    print("The photographer-share and client-confirmation steps remain separate human approvals; validate those in the UI.")


if __name__ == "__main__":
    main_run()
