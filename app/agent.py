"""ShotCraft Strands agents."""
import json
import os
from dotenv import load_dotenv
from strands import Agent
from strands.models.openai import OpenAIModel
from .models import BriefRequest, ChangeAssessment, ClientUpdateDraft, CreativeBrief, Inquiry, InquiryAnalysis, Moodboard, MoodboardRequest, ProductionPack, ScheduleSuggestion, ShootIdeaRecommendations
from .prompts import BRIEF_PROMPT, CHANGE_CLIENT_UPDATE_PROMPT, CHANGE_REQUEST_PROMPT, CLIENT_UPDATE_PROMPT, MOODBOARD_PROMPT, PRODUCTION_PROMPT, SCHEDULING_PROMPT, SHOOT_IDEAS_PROMPT, SYSTEM_PROMPT

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

def recommend_schedule_slots(inquiry: Inquiry, busy_times: list[dict]) -> list[ScheduleSuggestion]:
    result = json.loads(_json(_complete(SCHEDULING_PROMPT, f"Inquiry:\n{inquiry.model_dump_json(indent=2)}\nBusy times:\n{json.dumps(busy_times, indent=2)}", PLANNING_MODEL_ID)))
    return [ScheduleSuggestion.model_validate(item) for item in result["suggestions"]]

def draft_client_update(inquiry: Inquiry, status: str, call_time: str | None, meeting_location: str | None) -> ClientUpdateDraft:
    context = {"inquiry": inquiry.model_dump(), "status": status, "call_time": call_time, "meeting_location": meeting_location}
    return ClientUpdateDraft.model_validate_json(_json(_complete(CLIENT_UPDATE_PROMPT, f"Draft a client update from:\n{json.dumps(context, indent=2)}", PLANNING_MODEL_ID)))

def assess_change_request(inquiry: Inquiry, production_pack: dict, client_message: str) -> ChangeAssessment:
    context = {"inquiry": inquiry.model_dump(), "production_pack": production_pack, "client_message": client_message}
    return ChangeAssessment.model_validate_json(_json(_complete(CHANGE_REQUEST_PROMPT, f"Assess this change request:\n{json.dumps(context, indent=2)}", PLANNING_MODEL_ID)))

def draft_change_client_update(inquiry: Inquiry, production_pack: dict, source_message: str, assessment: dict) -> ClientUpdateDraft:
    context = {"inquiry": inquiry.model_dump(), "production_pack": production_pack, "client_request": source_message, "assessment": assessment}
    return ClientUpdateDraft.model_validate_json(_json(_complete(CHANGE_CLIENT_UPDATE_PROMPT, f"Draft a response to this change request:\n{json.dumps(context, indent=2)}", PLANNING_MODEL_ID)))
