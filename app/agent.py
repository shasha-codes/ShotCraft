"""ShotCraft Strands agents."""
import json
import os
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

def analyze_inquiry(inquiry: Inquiry) -> InquiryAnalysis:
    return InquiryAnalysis.model_validate_json(_json(_complete(SYSTEM_PROMPT, f"Analyze this photography inquiry:\n{inquiry.model_dump_json(indent=2)}", INTAKE_MODEL_ID)))


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
    system_prompt = """You are ShotCraft's scheduling coordinator. You must call all three tools before deciding. First inspect the shoot and bookings. Search preferred_window. Only when it has no options, search later_same_day. Select up to three option_id values returned by find_available_slots, in the best client-friendly order. Never invent or alter a time. Return only JSON: {\"selected_option_ids\":[\"...\"],\"summary\":\"brief explanation\"}."""
    if rescheduling:
        system_prompt = """You are ShotCraft's rescheduling agent. You must call get_shoot_context, get_reschedule_context, get_confirmed_bookings, and find_available_slots before deciding. The existing confirmed booking remains protected until the client accepts a photographer-approved alternative. Review prior preference rounds to avoid repeating rejected options when possible. Search preferred_window first; only search later_same_day if it is empty. Select up to three option_id values actually returned by find_available_slots. Never invent or alter a time or claim a booking has changed. Return only JSON: {\"selected_option_ids\":[\"...\"],\"summary\":\"one sentence explaining the recommendation for photographer review\"}."""

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
    activity.append("Ranked safe options for photographer review")
    return {"decision": decision.model_dump(), "activity": activity}

def coordinate_cancellation_review(
    inquiry_id: int,
    get_booking: Callable[[], dict],
    get_policy: Callable[[], dict],
    get_request: Callable[[], dict],
    get_history: Callable[[], list[dict]],
) -> dict:
    """Gather cancellation facts with Strands; leave every decision to the photographer."""
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
    return {"decision": decision.model_dump(), "activity": activity}

def assess_change_request(inquiry: Inquiry, production_pack: dict, client_message: str) -> ChangeAssessment:
    context = {"inquiry": inquiry.model_dump(), "production_pack": production_pack, "client_message": client_message}
    return ChangeAssessment.model_validate_json(_json(_complete(CHANGE_REQUEST_PROMPT, f"Assess this change request:\n{json.dumps(context, indent=2)}", PLANNING_MODEL_ID)))

def draft_change_client_update(inquiry: Inquiry, production_pack: dict, source_message: str, assessment: dict) -> ClientUpdateDraft:
    context = {"inquiry": inquiry.model_dump(), "production_pack": production_pack, "client_request": source_message, "assessment": assessment}
    return ClientUpdateDraft.model_validate_json(_json(_complete(CHANGE_CLIENT_UPDATE_PROMPT, f"Draft a response to this change request:\n{json.dumps(context, indent=2)}", PLANNING_MODEL_ID)))
