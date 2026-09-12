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
    duration_minutes: int | None = Field(default=None, ge=30, le=1440)
    availability_windows: list[str] = Field(default_factory=list, min_length=1, max_length=6)
    location: str | None = Field(default=None, max_length=300)
    style_direction: str | None = Field(default=None, max_length=500)

class InquiryReply(BaseModel):
    answers: str = Field(min_length=1)

class ClientDecision(BaseModel):
    note: str | None = None
    cancellation_policy_accepted: bool = False

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

class ScheduleChangeRequest(BaseModel):
    shoot_date: str = Field(min_length=10, max_length=32)
    availability_windows: list[str] = Field(min_length=1, max_length=6)
    note: str | None = Field(default=None, max_length=1200)

class CancellationRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=1200)

class CancellationDecision(BaseModel):
    message: str | None = Field(default=None, max_length=1200)
    fee_mode: str = Field(default="POLICY", pattern="^(POLICY|WAIVED|CUSTOM)$")
    cancellation_fee: float | None = Field(default=None, ge=0)


class ScheduleProposal(BaseModel):
    suggestions: list[ScheduleSuggestion] = Field(min_length=1, max_length=5)

class ClientUpdateDraft(BaseModel):
    message: str = Field(min_length=1, max_length=1200)

class ChangeAssessment(BaseModel):
    request_summary: str = Field(min_length=1, max_length=500)
    impacts: list[str] = Field(default_factory=list)
    proposed_updates: dict[str, list[str]] = Field(default_factory=dict)
    decision: str = Field(default="FOLLOW_UP", pattern="^(APPLY|FOLLOW_UP|REVIEW)$")
    decision_reason: str = Field(default="", max_length=500)
    missing_information: list[str] = Field(default_factory=list)
    confirmed_meeting_location: str | None = Field(default=None, max_length=500)

class ChangeApproval(BaseModel):
    client_message: str = Field(min_length=1, max_length=1200)

class InquiryAnalysis(BaseModel):
    status: str
    summary: str
    # A short display name lets the workspace describe a shoot without replaying
    # the client's raw inquiry (or their follow-up transcript) as a heading.
    concept_name: str = Field(default="", max_length=80)
    missing_information: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


class ShootIdea(BaseModel):
    """A low-commitment creative prompt a client can turn into an inquiry."""
    title: str = Field(min_length=3, max_length=80)
    description: str = Field(min_length=12, max_length=220)
    prompt: str = Field(min_length=12, max_length=600)


class ShootIdeaRecommendations(BaseModel):
    ideas: list[ShootIdea] = Field(min_length=2, max_length=3)


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
    city: str | None = Field(default=None, max_length=120)
    bio: str | None = Field(default=None, max_length=500)
    specialties: str | None = Field(default=None, max_length=300)

class ProfileUpdate(BaseModel):
    name: str | None = None
    city: str | None = Field(default=None, max_length=120)
    bio: str | None = Field(default=None, max_length=500)
    specialties: str | None = Field(default=None, max_length=300)
    profile_image: str | None = Field(default=None, max_length=2_800_000)
