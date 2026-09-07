"""Data contracts for the ShotCraft inquiry workflow."""

from pydantic import BaseModel, Field


class Inquiry(BaseModel):
    client_name: str = Field(min_length=1)
    client_email: str = Field(min_length=3)
    contact_email: str | None = None
    message: str = Field(min_length=1)
    budget: float | None = Field(default=None, ge=0)
    shoot_date: str | None = None
    reference_images: list[str] = Field(default_factory=list)
    photographer_email: str | None = None
    subject_presentation: str | None = None
    subject_count: int | None = Field(default=None, ge=1, le=10)
    wardrobe_details: str | None = None
    deliverable_count: int | None = Field(default=None, ge=1, le=100)

class InquiryReply(BaseModel):
    answers: str = Field(min_length=1)

class ClientDecision(BaseModel):
    note: str | None = None

class InquiryMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    sender_role: str = Field(pattern="^(client|photographer)$")
    sender_name: str = Field(min_length=1, max_length=120)

class ScheduleRequest(BaseModel):
    call_time: str = Field(min_length=1)
    meeting_location: str = Field(min_length=1)

class ScheduleSuggestion(BaseModel):
    starts_at: str = Field(min_length=1)
    ends_at: str = Field(min_length=1)
    location: str = Field(min_length=1)
    rationale: str = Field(min_length=1)

class ScheduleSelection(BaseModel):
    starts_at: str = Field(min_length=1)
    ends_at: str = Field(min_length=1)
    location: str = Field(min_length=1)

class InquiryAnalysis(BaseModel):
    status: str
    summary: str
    missing_information: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


class BriefRequest(BaseModel):
    inquiry: Inquiry
    client_answers: dict[str, str] = Field(default_factory=dict)
    inquiry_id: int | None = None


class CreativeBrief(BaseModel):
    concept_name: str
    creative_summary: str
    shoot_type: str
    location_direction: str
    lighting_direction: str
    posing_direction: str
    wardrobe_direction: str
    subject_profile: str = ""
    deliverables: list[str] = Field(default_factory=list)
    budget_notes: str
    remaining_questions: list[str] = Field(default_factory=list)


class MoodboardRequest(BaseModel):
    brief: CreativeBrief
    inquiry_id: int | None = None


class MoodboardTile(BaseModel):
    title: str
    visual_prompt: str
    caption: str
    palette: list[str] = Field(default_factory=list)
    styling_notes: str


class Moodboard(BaseModel):
    title: str
    creative_direction: str
    tiles: list[MoodboardTile]
    photographer_notes: list[str] = Field(default_factory=list)


class GeneratedTile(BaseModel):
    title: str
    image_url: str


class GeneratedMoodboard(BaseModel):
    title: str
    model_id: str
    tiles: list[GeneratedTile]


class MoodboardResult(BaseModel):
    moodboard: Moodboard
    generated: GeneratedMoodboard

class ProductionPack(BaseModel):
    title: str
    location_plan: list[str]
    shot_list: list[str]
    lighting_plan: list[str]
    wardrobe_checklist: list[str]
    call_sheet: dict[str, str]
    weather_note: str
    backup_plan: str

class AuthRequest(BaseModel):
    name: str | None = None
    email: str
    password: str
    user_type: str | None = None
