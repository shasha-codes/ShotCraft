"""ShotCraft Strands agents."""
import json
import logging
import os
import uuid
from collections.abc import Callable
from dotenv import load_dotenv
from strands import Agent, tool
from strands.models.openai import OpenAIModel
from .models import AgenticScheduleDecision, BriefRequest, CancellationAgentDecision, ChangeAssessment, ClientUpdateDraft, CreativeBrief, Inquiry, InquiryAnalysis, Moodboard, MoodboardRequest, ProductionPack, ShootIdeaRecommendations
from .prompts import BRIEF_PROMPT, CHANGE_CLIENT_UPDATE_PROMPT, CHANGE_REQUEST_PROMPT, MOODBOARD_PROMPT, PRODUCTION_PROMPT, SHOOT_IDEAS_PROMPT, SYSTEM_PROMPT

# Local development uses the AWS profile and region recorded in .env. The call is
# harmless in deployed environments where those variables are already provided.
load_dotenv()

# Use one capable model consistently across intake, briefs, planning, scheduling,
# and client communications. Individual roles can still be overridden when needed.
MODEL_ID = os.getenv("SHOTCRAFT_MODEL", "openai.gpt-oss-120b-1:0")
if MODEL_ID == "openai.gpt-oss-120b":
    MODEL_ID = "openai.gpt-oss-120b-1:0"
PLANNING_MODEL_ID = os.getenv("SHOTCRAFT_PLANNING_MODEL", MODEL_ID)
INTAKE_MODEL_ID = os.getenv("SHOTCRAFT_INTAKE_MODEL", MODEL_ID)
BEDROCK_API_KEY = os.getenv("AWS_BEARER_TOKEN_BEDROCK")
BEDROCK_REGION = os.getenv("AWS_REGION", "us-west-2")
BEDROCK_OPENAI_ENDPOINT = os.getenv("SHOTCRAFT_BEDROCK_ENDPOINT", f"https://bedrock-mantle.{BEDROCK_REGION}.api.aws/v1")
log = logging.getLogger("shotcraft.agent")


def _invoke_agentcore(payload: dict) -> dict | None:
    """Invoke the deployed ShotCraft AgentCore runtime."""
    runtime_arn = os.getenv("SHOTCRAFT_AGENTCORE_RUNTIME_ARN")
    if not runtime_arn or os.getenv("SHOTCRAFT_AGENTCORE_ENABLED", "").lower() not in {"1", "true", "yes"}:
        return None
    try:
        import boto3
        client = boto3.client("bedrock-agentcore", region_name=BEDROCK_REGION)
        response = client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            runtimeSessionId=f"shotcraft-{uuid.uuid4().hex}",
            payload=json.dumps(payload).encode("utf-8"),
        )
        chunks = []
        for chunk in response.get("response", []):
            if isinstance(chunk, dict):
                chunk = chunk.get("chunk", chunk.get("bytes", b""))
            chunks.append(chunk if isinstance(chunk, str) else bytes(chunk).decode("utf-8"))
        result = json.loads("".join(chunks))
        if not isinstance(result, dict) or result.get("agent_execution") != "agentcore":
            raise ValueError("AgentCore response did not identify remote execution")
        result["agent_execution"] = "agentcore"
        log.info("AgentCore scheduling invocation succeeded")
        return result
    except Exception as exc:
        log.exception("AgentCore scheduling invocation failed")
        return {"error": f"{type(exc).__name__}: {exc}"}


def _invoke_agentcore_schedule(payload: dict) -> dict | None:
    """Ask the deployed AgentCore reviewer to rank already validated candidates."""
    result = _invoke_agentcore(payload)
    if result and "error" not in result and not result.get("agent_used_tools"):
        return {"error": "AgentCore scheduling response did not prove tool use"}
    return result

def _json(response):
    raw = str(response).strip()
    if raw.startswith("```"):
        raw = raw.strip("`").removeprefix("json").strip()
    return raw


def _openai_model_id(model_id: str) -> str:
    """Return the model ID accepted by the configured Bedrock OpenAI endpoint."""
    configured = os.getenv("SHOTCRAFT_OPENAI_MODEL", model_id)
    if "bedrock-mantle" in BEDROCK_OPENAI_ENDPOINT:
        return configured.removesuffix("-1:0")
    return configured if configured.endswith("-1:0") else f"{configured}-1:0" if configured.startswith("openai.") else configured


def _complete(system_prompt: str, prompt: str, model_id: str) -> str:
    """Run a text completion through Strands using the Bedrock Mantle API."""
    if os.getenv("SHOTCRAFT_AGENTCORE_ENABLED", "").lower() in {"1", "true", "yes"}:
        remote = _invoke_agentcore({
            "operation": "structured_completion",
            "system_prompt": system_prompt,
            "prompt": prompt,
        })
        if remote and "result" in remote:
            return json.dumps(remote["result"])
        if remote and remote.get("error"):
            log.warning("AgentCore structured workflow failed; using local Strands fallback: %s", remote["error"])
    if not BEDROCK_API_KEY:
        raise RuntimeError("AWS_BEARER_TOKEN_BEDROCK is required for ShotCraft text agents")
    model = OpenAIModel(
        model_id=_openai_model_id(model_id),
        client_args={
            "api_key": BEDROCK_API_KEY,
            "base_url": BEDROCK_OPENAI_ENDPOINT,
        },
    )
    agent = Agent(model=model, system_prompt=system_prompt, callback_handler=None)
    return str(agent(prompt))

def analyze_inquiry(inquiry: Inquiry, followups: list[dict] | None = None) -> InquiryAnalysis:
    payload = {"inquiry": inquiry.model_dump(), "client_followups": followups or []}
    return InquiryAnalysis.model_validate_json(_json(_complete(SYSTEM_PROMPT, f"Analyze this photography inquiry and all client follow-ups:\n{json.dumps(payload, indent=2)}", INTAKE_MODEL_ID)))


def recommend_next_shoot_ideas(history: list[dict]) -> ShootIdeaRecommendations:
    """Generate fresh, editable concepts from a client's prior shoot history."""
    return ShootIdeaRecommendations.model_validate_json(
        _json(_complete(SHOOT_IDEAS_PROMPT, f"Client shoot history:\n{json.dumps(history, indent=2)}", PLANNING_MODEL_ID))
    )

def create_creative_brief(request: BriefRequest) -> CreativeBrief:
    payload = {"inquiry": request.inquiry.model_dump(), "client_answers": request.client_answers}
    return CreativeBrief.model_validate_json(_json(_complete(BRIEF_PROMPT, f"Create the creative brief from:\n{json.dumps(payload, indent=2)}", PLANNING_MODEL_ID)))

def create_moodboard(request: MoodboardRequest) -> Moodboard:
    moodboard = Moodboard.model_validate_json(_json(_complete(MOODBOARD_PROMPT, f"Create a moodboard plan from:\n{request.brief.model_dump_json(indent=2)}", PLANNING_MODEL_ID)))
    lock = f"HARD SUBJECT LOCK: {request.brief.subject_profile}. Client brief: {request.brief.creative_summary} Location and setting: {request.brief.location_direction} Wardrobe: {request.brief.wardrobe_direction}. Preserve the subject lock exactly; never change presentation, number of people, or wardrobe."
    for tile in moodboard.tiles:
        tile.visual_prompt = f"{lock} Tile direction: {tile.visual_prompt}"
    return moodboard


def build_production_pack(inquiry: Inquiry, moodboard: dict | None = None) -> ProductionPack:
    """Create a production pack scoped exclusively to one inquiry."""
    payload = {"inquiry": inquiry.model_dump(), "creative_direction": moodboard or {}}
    return ProductionPack.model_validate_json(
        _json(_complete(PRODUCTION_PROMPT, f"Create the production pack from:\n{json.dumps(payload, indent=2)}", PLANNING_MODEL_ID))
    )


def coordinate_inquiry_intake(inquiry_id: int, inquiry: Inquiry, followups: list[dict]) -> dict:
    """Use a Strands tool loop to collect the facts before intake analysis."""
    if os.getenv("SHOTCRAFT_AGENTCORE_ENABLED", "").lower() in {"1", "true", "yes"}:
        remote = _invoke_agentcore({"operation": "inquiry_intake", "inquiry": inquiry.model_dump(), "followups": followups, "specialist_prompt": SYSTEM_PROMPT})
        if remote and "analysis" in remote:
            return {"analysis": InquiryAnalysis.model_validate(remote["analysis"]), "activity": remote.get("activity", []), "agent_used_tools": True, "agent_execution": "agentcore"}
        if remote and remote.get("error"):
            log.warning("AgentCore inquiry intake failed; using local fallback: %s", remote["error"])
    if not BEDROCK_API_KEY:
        raise RuntimeError("AWS_BEARER_TOKEN_BEDROCK is required for inquiry coordination")
    activity: list[str] = []
    state: dict = {"inquiry_read": False, "followups_read": False}

    @tool
    def read_inquiry_context() -> str:
        """Read the complete client inquiry, including scheduling and deliverable requirements."""
        state["inquiry_read"] = True
        activity.append("Read the complete client inquiry")
        return inquiry.model_dump_json()

    @tool
    def read_followup_history() -> str:
        """Read the client's previous responses to follow-up questions."""
        state["followups_read"] = True
        activity.append(f"Reviewed {len(followups)} follow-up response{'s' if len(followups) != 1 else ''}")
        return json.dumps(followups)

    @tool
    def analyze_requirements() -> str:
        """Ask the Strands intake specialist which shoot details are still missing."""
        if not state["inquiry_read"] or not state["followups_read"]:
            return "Read the inquiry and follow-up history first."
        if "analysis" not in state:
            state["analysis"] = analyze_inquiry(inquiry, followups)
            activity.append("Analyzed missing requirements and follow-up questions")
        return state["analysis"].model_dump_json()

    agent = Agent(
        model=OpenAIModel(model_id=_openai_model_id(INTAKE_MODEL_ID), client_args={"api_key": BEDROCK_API_KEY, "base_url": BEDROCK_OPENAI_ENDPOINT}),
        tools=[read_inquiry_context, read_followup_history, analyze_requirements],
        system_prompt="""You coordinate ShotCraft inquiry intake. Call read_inquiry_context and read_followup_history, then call analyze_requirements. The specialist tool provides the authoritative structured assessment; do not invent or edit its result. If information is missing, the app will ask the client and pause before creative planning. Never book or send a plan yourself. Summarize the completed assessment in one sentence.""",
        callback_handler=None,
    )
    agent(f"Assess inquiry {inquiry_id} using every required tool.")
    if not all(state.get(key) for key in ("inquiry_read", "followups_read", "analysis")):
        raise RuntimeError("The inquiry coordinator did not complete every required tool step")
    return {"analysis": state["analysis"], "activity": activity, "agent_used_tools": True}


def coordinate_creative_direction(
    inquiry_id: int,
    inquiry: Inquiry,
    followups: list[dict],
    on_brief: Callable[[CreativeBrief], None],
    on_moodboard: Callable[[Moodboard], None],
) -> dict:
    """Let a Strands agent gather context and invoke the creative specialists.

    The tools have strict dependencies and persist each completed artifact through
    callbacks. Image rendering and publishing remain durable server-side jobs.
    """
    if os.getenv("SHOTCRAFT_AGENTCORE_ENABLED", "").lower() in {"1", "true", "yes"}:
        remote = _invoke_agentcore({"operation": "creative_direction", "inquiry": inquiry.model_dump(), "followups": followups, "brief_prompt": BRIEF_PROMPT, "moodboard_prompt": MOODBOARD_PROMPT})
        if remote and "brief" in remote and "moodboard" in remote:
            brief = CreativeBrief.model_validate(remote["brief"])
            moodboard = Moodboard.model_validate(remote["moodboard"])
            lock = f"HARD SUBJECT LOCK: {brief.subject_profile}. Client brief: {brief.creative_summary} Location and setting: {brief.location_direction} Wardrobe: {brief.wardrobe_direction}. Preserve the subject lock exactly; never change presentation, number of people, or wardrobe."
            for tile in moodboard.tiles:
                tile.visual_prompt = f"{lock} Tile direction: {tile.visual_prompt}"
            on_brief(brief)
            on_moodboard(moodboard)
            return {"brief": brief, "moodboard": moodboard, "activity": remote.get("activity", []), "agent_used_tools": True, "agent_execution": "agentcore"}
        if remote and remote.get("error"):
            log.warning("AgentCore creative direction failed; using local fallback: %s", remote["error"])
    if not BEDROCK_API_KEY:
        raise RuntimeError("AWS_BEARER_TOKEN_BEDROCK is required for creative coordination")
    activity: list[str] = []
    state: dict = {"inquiry_read": False, "followups_read": False}

    @tool
    def read_inquiry_context() -> str:
        """Read the client's shoot request, date, duration, budget, and creative preferences."""
        state["inquiry_read"] = True
        activity.append("Read the client inquiry and structured shoot requirements")
        return inquiry.model_dump_json()

    @tool
    def read_followup_history() -> str:
        """Read all client follow-up answers before creating the creative direction."""
        state["followups_read"] = True
        activity.append(f"Reviewed {len(followups)} client follow-up response{'s' if len(followups) != 1 else ''}")
        return json.dumps(followups)

    @tool
    def draft_creative_brief() -> str:
        """Ask the Strands brief specialist to create a structured, editable creative brief."""
        if not state["inquiry_read"] or not state["followups_read"]:
            return "Read the inquiry and follow-up history first."
        if "brief" not in state:
            answers = {f"response_{item.get('id', index)}": item.get("answers", "") for index, item in enumerate(followups)}
            brief = create_creative_brief(BriefRequest(inquiry=inquiry, client_answers=answers, inquiry_id=inquiry_id))
            on_brief(brief)
            state["brief"] = brief
            activity.append("Created and saved the editable creative brief")
        return state["brief"].model_dump_json()

    @tool
    def plan_moodboard() -> str:
        """Ask the Strands moodboard specialist to plan visual references from the saved brief."""
        if "brief" not in state:
            return "Draft the creative brief first."
        if "moodboard" not in state:
            moodboard = create_moodboard(MoodboardRequest(brief=state["brief"], inquiry_id=inquiry_id))
            on_moodboard(moodboard)
            state["moodboard"] = moodboard
            activity.append(f"Planned and saved {len(state['moodboard'].tiles)} moodboard image directions")
        return json.dumps({"title": state["moodboard"].title, "tiles": [tile.title for tile in state["moodboard"].tiles]})

    agent = Agent(
        model=OpenAIModel(model_id=_openai_model_id(PLANNING_MODEL_ID), client_args={"api_key": BEDROCK_API_KEY, "base_url": BEDROCK_OPENAI_ENDPOINT}),
        tools=[read_inquiry_context, read_followup_history, draft_creative_brief, plan_moodboard],
        system_prompt="""You coordinate ShotCraft's creative planning. Call read_inquiry_context and read_followup_history first. Then call draft_creative_brief and plan_moodboard in that order. These specialist tools create the actual artifacts; do not invent their results. The photographer must review the final production plan. Never send anything to the client or confirm a booking. After all tools complete, summarize the prepared direction in one sentence.""",
        callback_handler=None,
    )
    agent(f"Prepare the creative direction for inquiry {inquiry_id}. Use every required tool.")
    if not all(state.get(key) for key in ("inquiry_read", "followups_read", "brief", "moodboard")):
        raise RuntimeError("The creative coordinator did not complete every required tool step")
    return {"brief": state["brief"], "moodboard": state["moodboard"], "activity": activity, "agent_used_tools": True}

def coordinate_schedule_slots(
    inquiry_id: int,
    get_context: Callable[[], dict],
    get_bookings: Callable[[], list[dict]],
    find_slots: Callable[[str], list[dict]],
    get_change_history: Callable[[], dict] | None = None,
) -> dict:
    """Use a Strands tool loop to inspect and rank safe schedule candidates.

    Tools are deliberately read-only. The caller remains responsible for validating,
    persisting, and sending the photographer-approved options.
    """
    activity: list[str] = []
    slot_scopes: list[str] = []

    @tool
    def get_shoot_context() -> str:
        """Read the requested date, preferred windows, duration, and location for this shoot."""
        context = get_context()
        activity.append(f"Read shoot context for inquiry {inquiry_id}")
        return json.dumps(context)

    @tool
    def get_confirmed_bookings() -> str:
        """Read the photographer's confirmed bookings that must be avoided."""
        bookings = get_bookings()
        activity.append(f"Checked {len(bookings)} confirmed booking{'s' if len(bookings) != 1 else ''}")
        return json.dumps(bookings)

    @tool
    def find_available_slots(scope: str) -> str:
        """Find duration-matched, conflict-free slots. Scope must be preferred_window or later_same_day."""
        normalized = "later_same_day" if scope == "later_same_day" else "preferred_window"
        if normalized == "later_same_day" and "preferred_window" not in slot_scopes:
            return "Call find_available_slots with preferred_window first; only then inspect later_same_day."
        slot_scopes.append(normalized)
        slots = find_slots(normalized)
        activity.append(f"Found {len(slots)} conflict-free option{'s' if len(slots) != 1 else ''} in {normalized.replace('_', ' ')}")
        return json.dumps(slots)

    @tool
    def get_reschedule_context() -> str:
        """Read the protected current booking and prior client preference rounds."""
        if get_change_history is None:
            return json.dumps({})
        context = get_change_history()
        activity.append(f"Reviewed current booking and {len(context.get('previous_rounds', []))} prior preference round{'s' if len(context.get('previous_rounds', [])) != 1 else ''}")
        return json.dumps(context)

    rescheduling = get_change_history is not None
    system_prompt = """You are ShotCraft's scheduling coordinator. You must call all three tools before deciding. First inspect the shoot and bookings. ALWAYS call find_available_slots(scope=\"preferred_window\") even if the context suggests it is full. Only when that tool returns no options, call find_available_slots(scope=\"later_same_day\"). Select up to three option_id values returned by find_available_slots, in the best client-friendly order. Never invent or alter a time. Return only JSON: {\"selected_option_ids\":[\"...\"],\"summary\":\"brief explanation\"}."""
    if rescheduling:
        system_prompt = """You are ShotCraft's rescheduling agent. You must call get_shoot_context, get_reschedule_context, get_confirmed_bookings, and find_available_slots before deciding. The existing confirmed booking remains protected until the client accepts a photographer-approved alternative. Review prior preference rounds to avoid repeating rejected options when possible. ALWAYS call find_available_slots(scope=\"preferred_window\") first; only call it with scope=\"later_same_day\" if the preferred-window result is empty. Select up to three option_id values actually returned by find_available_slots. Never invent or alter a time or claim a booking has changed. Return only JSON: {\"selected_option_ids\":[\"...\"],\"summary\":\"one sentence explaining the recommendation for photographer review\"}."""

    if os.getenv("SHOTCRAFT_AGENTCORE_ENABLED", "").lower() in {"1", "true", "yes"}:
        context_data = get_context()
        bookings_data = get_bookings()
        candidates = find_slots("preferred_window")
        if not candidates:
            candidates = find_slots("later_same_day")
        agentcore_candidates = [
            {**candidate, "id": candidate.get("id") or candidate.get("option_id")}
            for candidate in candidates[:3]
        ]
        remote = _invoke_agentcore_schedule({
            "context": context_data,
            "bookings": bookings_data,
            "candidates": agentcore_candidates,
        })
        if remote and "decision" in remote:
            return {"decision": remote["decision"], "activity": remote.get("activity", []), "agent_execution": "agentcore"}
        if remote and remote.get("error"):
            activity.append(f"AgentCore invocation failed: {remote['error']}")

    agent = Agent(
        model=OpenAIModel(
            model_id=_openai_model_id(PLANNING_MODEL_ID),
            client_args={"api_key": BEDROCK_API_KEY, "base_url": BEDROCK_OPENAI_ENDPOINT},
        ),
        tools=[get_shoot_context, get_confirmed_bookings, find_available_slots] + ([get_reschedule_context] if rescheduling else []),
        system_prompt=system_prompt,
        callback_handler=None,
    )
    if not BEDROCK_API_KEY:
        raise RuntimeError("AWS_BEARER_TOKEN_BEDROCK is required for agentic scheduling")
    decision = AgenticScheduleDecision.model_validate_json(_json(agent(
        f"Coordinate safe options for inquiry {inquiry_id}. Use the tools and respect the photographer approval boundary."
    )))
    required_steps = ("Read shoot context", "Checked ", "Found ") + (("Reviewed current booking",) if rescheduling else ())
    if not all(any(entry.startswith(prefix) for entry in activity) for prefix in required_steps):
        raise RuntimeError("The scheduling agent did not complete every required tool check")
    if "preferred_window" not in slot_scopes or ("later_same_day" in slot_scopes and slot_scopes.index("later_same_day") < slot_scopes.index("preferred_window")):
        raise RuntimeError("The scheduling agent did not inspect the preferred window first")
    activity.append("Ranked safe options for photographer review")
    execution = "local-strands-after-agentcore-error" if any(item.startswith("AgentCore invocation failed:") for item in activity) else "local-strands"
    return {"decision": decision.model_dump(), "activity": activity, "agent_execution": execution}

def coordinate_cancellation_review(
    inquiry_id: int,
    get_booking: Callable[[], dict],
    get_policy: Callable[[], dict],
    get_request: Callable[[], dict],
    get_history: Callable[[], list[dict]],
) -> dict:
    """Gather cancellation facts with Strands; leave every decision to the photographer."""
    if os.getenv("SHOTCRAFT_AGENTCORE_ENABLED", "").lower() in {"1", "true", "yes"}:
        remote = _invoke_agentcore({
            "operation": "cancellation_review",
            "facts": {
                "booking": get_booking(),
                "policy": get_policy(),
                "request": get_request(),
                "history": get_history(),
            },
        })
        if remote and "decision" in remote:
            return {"decision": remote["decision"], "activity": remote.get("activity", []), "agent_execution": "agentcore"}
        if remote and remote.get("error"):
            log.warning("AgentCore cancellation review failed; using local fallback: %s", remote["error"])
    activity: list[str] = []

    @tool
    def read_confirmed_booking() -> str:
        """Read the current confirmed shoot date, location, duration, and booking amount."""
        activity.append("Read the confirmed booking")
        return json.dumps(get_booking())

    @tool
    def read_accepted_policy() -> str:
        """Read the policy accepted at booking and the server-calculated fee and refund."""
        activity.append("Checked the accepted cancellation policy and calculated fee")
        return json.dumps(get_policy())

    @tool
    def read_client_request() -> str:
        """Read the client's cancellation reason, note, and request time."""
        activity.append("Read the client's cancellation reason and note")
        return json.dumps(get_request())

    @tool
    def read_project_history() -> str:
        """Read the shoot's own project milestones for relevant context."""
        history = get_history()
        activity.append(f"Reviewed {len(history)} project milestone{'s' if len(history) != 1 else ''}")
        return json.dumps(history)

    if not BEDROCK_API_KEY:
        raise RuntimeError("AWS_BEARER_TOKEN_BEDROCK is required for cancellation review")
    agent = Agent(
        model=OpenAIModel(model_id=_openai_model_id(PLANNING_MODEL_ID), client_args={"api_key": BEDROCK_API_KEY, "base_url": BEDROCK_OPENAI_ENDPOINT}),
        tools=[read_confirmed_booking, read_accepted_policy, read_client_request, read_project_history],
        system_prompt="""You are ShotCraft's cancellation review assistant. Call all four tools before responding. Use only their facts. Recommend APPROVE, DECLINE, or MESSAGE_FIRST for photographer consideration. If the reason or policy context is unclear, favor MESSAGE_FIRST. The fee and refund are server-calculated guidance; never recalculate them, promise payment, or imply you can waive or charge a fee yourself. The booking remains active until the photographer approves cancellation. Write one concise, empathetic, editable message draft appropriate to your recommended action. Do not send it. Return only JSON: {\"recommended_action\":\"APPROVE|DECLINE|MESSAGE_FIRST\",\"rationale\":\"...\",\"message_draft\":\"...\"}.""",
        callback_handler=None,
    )
    decision = CancellationAgentDecision.model_validate_json(_json(agent(f"Review cancellation request for inquiry {inquiry_id}. The photographer makes the final decision.")))
    if len(activity) < 4 or not all(any(item.startswith(prefix) for item in activity) for prefix in ("Read the confirmed", "Checked the accepted", "Read the client's", "Reviewed ")):
        raise RuntimeError("The cancellation agent did not complete every required tool check")
    return {"decision": decision.model_dump(), "activity": activity, "agent_execution": "local-strands"}

def assess_change_request(inquiry: Inquiry, production_pack: dict, client_message: str) -> ChangeAssessment:
    context = {"inquiry": inquiry.model_dump(), "production_pack": production_pack, "client_message": client_message}
    return ChangeAssessment.model_validate_json(_json(_complete(CHANGE_REQUEST_PROMPT, f"Assess this change request:\n{json.dumps(context, indent=2)}", PLANNING_MODEL_ID)))

def draft_change_client_update(inquiry: Inquiry, production_pack: dict, source_message: str, assessment: dict) -> ClientUpdateDraft:
    context = {"inquiry": inquiry.model_dump(), "production_pack": production_pack, "client_request": source_message, "assessment": assessment}
    return ClientUpdateDraft.model_validate_json(_json(_complete(CHANGE_CLIENT_UPDATE_PROMPT, f"Draft a response to this change request:\n{json.dumps(context, indent=2)}", PLANNING_MODEL_ID)))
