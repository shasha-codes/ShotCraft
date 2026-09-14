import json
import os
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from model.load import load_model

app = BedrockAgentCoreApp()
log = app.logger


def _coordinator_model():
    return load_model(os.environ.get("SHOTCRAFT_COORDINATOR_MODEL", "openai.gpt-oss-20b"))


def _intake_model():
    return load_model(os.environ.get("SHOTCRAFT_INTAKE_MODEL", "openai.gpt-oss-20b"))


async def _json_agent(system_prompt: str, prompt: str) -> dict:
    result = await Agent(model=load_model(), system_prompt=system_prompt).invoke_async(prompt)
    fence = chr(96) * 3
    return json.loads(str(result).strip().replace(fence + "json", "").replace(fence, "").strip())


async def _structured_completion(payload: dict) -> dict:
    system_prompt = payload.get("system_prompt")
    prompt = payload.get("prompt")
    if not isinstance(system_prompt, str) or not isinstance(prompt, str):
        raise ValueError("system_prompt and prompt are required")
    return {
        "result": await _json_agent(system_prompt, prompt),
        "activity": ["Ran structured Strands workflow in AgentCore"],
        "agent_used_tools": False,
        "agent_execution": "agentcore",
    }


async def _inquiry_intake(payload: dict) -> dict:
    inquiry = payload.get("inquiry")
    followups = payload.get("followups", [])
    specialist_prompt = payload.get("specialist_prompt")
    if not isinstance(inquiry, dict) or not isinstance(followups, list) or not isinstance(specialist_prompt, str):
        raise ValueError("inquiry, followups, and specialist_prompt are required")
    activity: list[str] = []
    state: dict = {}

    @tool
    def read_intake_context() -> str:
        """Read the complete inquiry and all prior client follow-up responses."""
        activity.append("Read the complete client inquiry")
        activity.append(f"Reviewed {len(followups)} follow-up responses")
        state["context_read"] = True
        return json.dumps({"inquiry": inquiry, "client_followups": followups})

    coordinator = Agent(
        model=_intake_model(),
        tools=[read_intake_context],
        system_prompt=(
            specialist_prompt
            + "\n\nYou are operating as ShotCraft's bounded intake coordinator. "
              "You MUST call read_intake_context exactly once before assessing the request. "
              "Base the required JSON only on that tool result. Never book, publish a plan, or contact anyone."
        ),
    )
    result = await coordinator.invoke_async("Read the intake context, assess missing details, and return only the required JSON.")
    if not state.get("context_read"):
        raise RuntimeError("intake agent did not read the intake context")
    fence = chr(96) * 3
    analysis = json.loads(str(result).strip().replace(fence + "json", "").replace(fence, "").strip())
    activity.append("Analyzed missing requirements and follow-up questions")
    return {"analysis": analysis, "activity": activity, "agent_used_tools": True, "agent_execution": "agentcore"}


async def _creative_direction(payload: dict) -> dict:
    inquiry = payload.get("inquiry")
    followups = payload.get("followups", [])
    brief_prompt = payload.get("brief_prompt")
    moodboard_prompt = payload.get("moodboard_prompt")
    if not isinstance(inquiry, dict) or not isinstance(followups, list) or not isinstance(brief_prompt, str) or not isinstance(moodboard_prompt, str):
        raise ValueError("creative workflow payload is incomplete")
    activity: list[str] = []
    state: dict = {}

    @tool
    def read_inquiry_context() -> str:
        """Read the client inquiry and shoot requirements."""
        activity.append("Read the client inquiry and structured shoot requirements")
        state["inquiry_read"] = True
        return json.dumps(inquiry)

    @tool
    def read_followup_history() -> str:
        """Read all client follow-up answers."""
        activity.append(f"Reviewed {len(followups)} client follow-up responses")
        state["followups_read"] = True
        return json.dumps(followups)

    @tool
    async def draft_creative_brief() -> str:
        """Create a structured, editable creative brief."""
        if not state.get("inquiry_read") or not state.get("followups_read"):
            return "Read inquiry and follow-ups first."
        answers = {f"response_{item.get('id', index)}": item.get("answers", "") for index, item in enumerate(followups)}
        state["brief"] = await _json_agent(brief_prompt, f"Create the creative brief from:\n{json.dumps({'inquiry': inquiry, 'client_answers': answers}, indent=2)}")
        activity.append("Created the editable creative brief")
        return json.dumps(state["brief"])

    @tool
    async def plan_moodboard() -> str:
        """Plan moodboard image directions from the creative brief."""
        if "brief" not in state:
            return "Draft the creative brief first."
        state["moodboard"] = await _json_agent(moodboard_prompt, f"Create a moodboard plan from:\n{json.dumps(state['brief'], indent=2)}")
        activity.append(f"Planned {len(state['moodboard'].get('tiles', []))} moodboard image directions")
        return json.dumps(state["moodboard"])

    coordinator = Agent(model=_coordinator_model(), tools=[read_inquiry_context, read_followup_history, draft_creative_brief, plan_moodboard], system_prompt="Call every tool in order. Never publish, message, or confirm a booking. Briefly confirm completion after all tools finish.")
    await coordinator.invoke_async("Coordinate the complete creative direction workflow.")
    if "brief" not in state or "moodboard" not in state:
        raise RuntimeError("creative direction did not complete every required tool")
    return {"brief": state["brief"], "moodboard": state["moodboard"], "activity": activity, "agent_used_tools": True, "agent_execution": "agentcore"}


async def _cancellation_review(payload: dict) -> dict:
    facts = payload.get("facts")
    if not isinstance(facts, dict):
        raise ValueError("cancellation facts are required")
    activity: list[str] = []

    @tool
    def review_cancellation_context() -> str:
        """Read the booking, accepted policy, client request, and project history together."""
        history = facts.get("history", [])
        activity.extend([
            "Read the confirmed booking",
            "Checked the accepted cancellation policy and calculated fee",
            "Read the client's cancellation reason and note",
            f"Reviewed {len(history)} project milestones",
        ])
        return json.dumps(facts)

    agent = Agent(
        model=load_model(),
        tools=[review_cancellation_context],
        system_prompt=(
            "You are ShotCraft's cancellation review assistant. You must call review_cancellation_context before responding. "
            "Recommend APPROVE, DECLINE, or MESSAGE_FIRST for photographer consideration. "
            "Never recalculate fees, promise payment, send a message, or cancel a booking. "
            "Return JSON only with recommended_action, rationale, and message_draft."
        ),
    )
    result = await agent.invoke_async("Review this cancellation request for the photographer.")
    fence = chr(96) * 3
    decision = json.loads(str(result).strip().replace(fence + "json", "").replace(fence, "").strip())
    if len(activity) < 4:
        raise RuntimeError("cancellation review did not use every required tool")
    return {"decision": decision, "activity": activity, "agent_used_tools": True, "agent_execution": "agentcore"}


def _validated_payload(payload: Any) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    context = payload.get("context")
    bookings = payload.get("bookings")
    candidates = payload.get("candidates")
    if not isinstance(context, dict) or not isinstance(bookings, list):
        raise ValueError("context and bookings are required")
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 3:
        raise ValueError("candidates must contain between one and three options")
    for candidate in candidates:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("id"), str):
            raise ValueError("each candidate must have a string id")
    return {"context": context, "bookings": bookings, "candidates": candidates}


def _parse_decision(text: str, candidate_ids: set[str]) -> dict:
    fence = chr(96) * 3
    cleaned = text.strip().replace(fence + "json", "").replace(fence, "").strip()
    decision = json.loads(cleaned)
    selected = decision.get("selected_option_ids")
    if not isinstance(selected, list) or any(
        not isinstance(option_id, str) or option_id not in candidate_ids
        for option_id in selected
    ):
        raise ValueError("agent returned an invalid candidate selection")
    return {
        "selected_option_ids": selected,
        "summary": str(decision.get("summary", "Options ranked for photographer review.")),
    }


@app.entrypoint
async def invoke(payload, context):
    if isinstance(payload, dict) and payload.get("operation") == "structured_completion":
        return await _structured_completion(payload)
    if isinstance(payload, dict) and payload.get("operation") == "cancellation_review":
        return await _cancellation_review(payload)
    if isinstance(payload, dict) and payload.get("operation") == "inquiry_intake":
        return await _inquiry_intake(payload)
    if isinstance(payload, dict) and payload.get("operation") == "creative_direction":
        return await _creative_direction(payload)
    data = _validated_payload(payload)
    activity: list[str] = []

    @tool
    def read_shoot_context() -> str:
        """Read the client's requested date, time window, duration, and location."""
        activity.append("Read shoot context")
        return json.dumps(data["context"])

    @tool
    def read_confirmed_bookings() -> str:
        """Read confirmed bookings that must be avoided."""
        activity.append(f"Checked {len(data['bookings'])} confirmed bookings")
        return json.dumps(data["bookings"])

    @tool
    def find_validated_candidates() -> str:
        """Read server-validated duration-matched candidate slots."""
        activity.append(f"Reviewed {len(data['candidates'])} server-validated candidates")
        return json.dumps(data["candidates"])

    agent = Agent(
        model=load_model(),
        system_prompt=(
            "You are ShotCraft's scheduling review agent. You must call all three tools "
            "before deciding. Rank only the supplied candidate IDs. Never invent a time, "
            "change a candidate, write a booking, or contact anyone. Return JSON only with "
            "selected_option_ids (an ordered list of supplied IDs) and summary."
        ),
        tools=[read_shoot_context, read_confirmed_bookings, find_validated_candidates],
    )
    result = await agent.invoke_async(
        "Review the scheduling candidates and rank the safest, best-fitting options."
    )
    decision = _parse_decision(
        str(result), {candidate["id"] for candidate in data["candidates"]}
    )
    activity.append("Ranked safe options for photographer review")
    log.info("AgentCore scheduling review completed")
    return {
        "decision": decision,
        "activity": activity,
        "agent_used_tools": len(activity) == 4,
        "agent_execution": "agentcore",
    }


if __name__ == "__main__":
    app.run()
