"""ShotCraft Strands agents."""
import json
import os
from strands import Agent
from strands.models import BedrockModel
from .models import BriefRequest, CreativeBrief, Inquiry, InquiryAnalysis, Moodboard, MoodboardRequest
from .prompts import BRIEF_PROMPT, MOODBOARD_PROMPT, SYSTEM_PROMPT

PLANNING_MODEL_ID = os.getenv("SHOTCRAFT_PLANNING_MODEL", "openai.gpt-oss-20b-1:0")
INTAKE_MODEL_ID = "google.gemma-3-4b-it"

def _json(response):
    raw = str(response).strip()
    if raw.startswith("```"):
        raw = raw.strip("`").removeprefix("json").strip()
    return raw

def analyze_inquiry(inquiry: Inquiry) -> InquiryAnalysis:
    agent = Agent(model=BedrockModel(model_id=INTAKE_MODEL_ID), system_prompt=SYSTEM_PROMPT, callback_handler=None)
    return InquiryAnalysis.model_validate_json(_json(agent(f"Analyze this photography inquiry:\n{inquiry.model_dump_json(indent=2)}")))

def create_creative_brief(request: BriefRequest) -> CreativeBrief:
    agent = Agent(model=BedrockModel(model_id=PLANNING_MODEL_ID), system_prompt=BRIEF_PROMPT, callback_handler=None)
    payload = {"inquiry": request.inquiry.model_dump(), "client_answers": request.client_answers}
    return CreativeBrief.model_validate_json(_json(agent(f"Create the creative brief from:\n{json.dumps(payload, indent=2)}")))

def create_moodboard(request: MoodboardRequest) -> Moodboard:
    agent = Agent(model=BedrockModel(model_id=PLANNING_MODEL_ID), system_prompt=MOODBOARD_PROMPT, callback_handler=None)
    moodboard = Moodboard.model_validate_json(_json(agent(f"Create a moodboard plan from:\n{request.brief.model_dump_json(indent=2)}")))
    lock = f"Client brief lock: {request.brief.creative_summary} Location and setting: {request.brief.location_direction} Wardrobe: {request.brief.wardrobe_direction} Preserve the requested subject presentation exactly."
    for tile in moodboard.tiles:
        tile.visual_prompt = f"{lock} Tile direction: {tile.visual_prompt}"
    return moodboard
