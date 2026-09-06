"""FastAPI entry point for ShotCraft."""

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from .storage import append_reply, list_inquiries, save_inquiry, update_analysis, create_user, authenticate_user, save_moodboard, save_production_pack, approve_production_pack, set_client_decision, schedule_inquiry
from fastapi.staticfiles import StaticFiles
import json
from urllib.parse import urlencode
from urllib.request import urlopen

from .agent import analyze_inquiry, create_creative_brief, create_moodboard
from .images import generate_moodboard_images
from .models import (
    BriefRequest,
    CreativeBrief,
    Inquiry,
    InquiryAnalysis,
    Moodboard,
    MoodboardRequest,
    GeneratedMoodboard,
    MoodboardResult,
    ProductionPack,
    InquiryReply,
    AuthRequest,
    ClientDecision,
    ScheduleRequest,
)

app = FastAPI(title="ShotCraft API", version="0.1.0")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def health_check() -> FileResponse:
    return FileResponse("static/index.html")

@app.get("/auth")
def auth_page() -> FileResponse:
    return FileResponse("static/auth.html")

@app.post("/api/auth/signup")
def signup(request: AuthRequest) -> dict:
    if not request.name or len(request.password) < 8: return {"error": "Name and a password of at least 8 characters are required."}
    user = create_user(request.name, request.email, request.password, request.user_type)
    return user or {"error": "Email already exists or user type is invalid."}

@app.post("/api/auth/login")
def login(request: AuthRequest) -> dict:
    return authenticate_user(request.email, request.password, request.user_type or "") or {"error": "Invalid email or password."}


@app.get("/client")
def client_inquiry_page() -> FileResponse:
    return FileResponse("static/client.html")

@app.get("/client/follow-up")
def client_follow_up_page(id: int | None = None) -> RedirectResponse:
    suffix = f"?view=followup&id={id}" if id else ""
    return RedirectResponse(f"/client{suffix}", status_code=303)

@app.get("/client/inquiries")
def client_inquiries_page() -> RedirectResponse:
    return RedirectResponse("/client?view=shoots", status_code=303)

@app.get("/client/confirmation")
def client_confirmation_page(id: int | None = None) -> RedirectResponse:
    suffix = f"&id={id}" if id else ""
    return RedirectResponse(f"/client?view=details{suffix}", status_code=303)

@app.get("/client/plan")
def client_plan_page(id: int | None = None) -> RedirectResponse:
    suffix = f"&id={id}" if id else ""
    return RedirectResponse(f"/client?view=plan{suffix}", status_code=303)

@app.get("/photographer")
def photographer_dashboard() -> FileResponse:
    return FileResponse("static/photographer.html")

@app.get("/photographer/inquiries")
def photographer_inquiries() -> RedirectResponse:
    return RedirectResponse("/photographer?view=inquiries", status_code=303)

@app.get("/photographer/production")
def photographer_production() -> RedirectResponse:
    return RedirectResponse("/photographer?view=projects", status_code=303)

@app.get("/photographer/calendar")
def photographer_calendar() -> RedirectResponse:
    return RedirectResponse("/photographer?view=calendar", status_code=303)

@app.get("/photographer/settings")
def photographer_settings() -> RedirectResponse:
    return RedirectResponse("/photographer", status_code=303)

@app.get("/photographer/project")
def photographer_project(id: int | None = None) -> RedirectResponse:
    suffix = f"&id={id}" if id else ""
    return RedirectResponse(f"/photographer?view=project{suffix}", status_code=303)

@app.get("/photographer/project/production")
def photographer_project_production(id: int | None = None) -> RedirectResponse:
    suffix = f"&id={id}" if id else ""
    return RedirectResponse(f"/photographer?view=production{suffix}", status_code=303)

@app.get("/photographer/project/schedule")
def photographer_project_schedule(id: int | None = None) -> RedirectResponse:
    suffix = f"&id={id}" if id else ""
    return RedirectResponse(f"/photographer?view=schedule{suffix}", status_code=303)

@app.get("/photographer/project/brief")
def photographer_brief_page(id: int | None = None) -> RedirectResponse:
    suffix = f"&id={id}" if id else ""
    return RedirectResponse(f"/photographer?view=brief{suffix}", status_code=303)


def process_inquiry(inquiry_id: int, inquiry: Inquiry) -> None:
    """Run intake after the HTTP response and persist the agent result."""
    try:
        result = analyze_inquiry(inquiry)
        # Deliverable count is required for both pricing and the production brief.
        # Enforce this contract even if the intake model overlooks it.
        if inquiry.deliverable_count is None and "final_image_count" not in result.missing_information:
            result.missing_information.append("final_image_count")
            result.questions.append("How many final edited photos would you like delivered?")
        status = "NEEDS_INFORMATION" if result.missing_information else "READY_FOR_REVIEW"
        update_analysis(inquiry_id, status, result.model_dump())
        print(f"[ShotCraft notification] Inquiry {inquiry_id}: {status}")
    except Exception as exc:
        update_analysis(inquiry_id, "PROCESSING_ERROR", {"error": str(exc)})
        print(f"[ShotCraft notification] Inquiry {inquiry_id} failed: {exc}")

@app.post("/api/inquiries")
def submit_inquiry(inquiry: Inquiry, background_tasks: BackgroundTasks) -> dict[str, object]:
    inquiry_id = save_inquiry(inquiry)
    background_tasks.add_task(process_inquiry, inquiry_id, inquiry)
    return {"id": inquiry_id, "status": "NEW", "message": "Inquiry received."}

@app.get("/api/inquiries")
def get_inquiries(client_email: str | None = None, photographer_email: str | None = None) -> list[dict]:
    inquiries = list_inquiries()
    if client_email:
        inquiries = [item for item in inquiries if item.get("client_email", "").lower() == client_email.lower()]
    if photographer_email:
        def assigned(item: dict) -> bool:
            try:
                target = json.loads(item.get("payload", "{}")).get("photographer_email")
            except Exception:
                target = None
            # Keep legacy records visible until they are explicitly assigned.
            return not target or target.lower() == photographer_email.lower()
        inquiries = [item for item in inquiries if assigned(item)]
    return inquiries

@app.get("/api/inquiries/{inquiry_id}")
def get_inquiry_detail(inquiry_id: int) -> dict:
    record = next((r for r in list_inquiries() if r["id"] == inquiry_id), None)
    if not record: return {"error": "Inquiry not found"}
    return record

@app.post("/api/inquiries/{inquiry_id}/reply")
def reply_to_inquiry(inquiry_id: int, reply: InquiryReply, background_tasks: BackgroundTasks) -> dict[str, object]:
    inquiry = append_reply(inquiry_id, reply.answers)
    if not inquiry: return {"error": "Inquiry not found"}
    background_tasks.add_task(process_inquiry, inquiry_id, Inquiry(**inquiry))
    return {"id": inquiry_id, "status": "NEW", "message": "Reply received and queued for re-analysis."}

@app.post("/api/inquiries/{inquiry_id}/production/approve")
def approve_production(inquiry_id: int) -> dict[str, object]:
    if not approve_production_pack(inquiry_id):
        return {"error": "Production pack not found."}
    return {"id": inquiry_id, "production_approved": True, "message": "Production pack approved."}

@app.post("/api/inquiries/{inquiry_id}/client-confirm")
def client_confirm(inquiry_id: int, decision: ClientDecision) -> dict[str, object]:
    if not set_client_decision(inquiry_id, "CLIENT_CONFIRMED", decision.note): return {"error": "An approved production pack is required."}
    return {"id": inquiry_id, "status": "CLIENT_CONFIRMED"}

@app.post("/api/inquiries/{inquiry_id}/client-change-request")
def client_change_request(inquiry_id: int, decision: ClientDecision) -> dict[str, object]:
    if not set_client_decision(inquiry_id, "CLIENT_CHANGE_REQUESTED", decision.note): return {"error": "An approved production pack is required."}
    return {"id": inquiry_id, "status": "CLIENT_CHANGE_REQUESTED"}

@app.post("/api/inquiries/{inquiry_id}/schedule")
def schedule_project(inquiry_id: int, schedule: ScheduleRequest) -> dict[str, object]:
    if not schedule_inquiry(inquiry_id, schedule.call_time, schedule.meeting_location):
        raise HTTPException(status_code=409, detail="The client must confirm the production plan before it can be scheduled.")
    return {"id": inquiry_id, "status": "SCHEDULED"}


@app.post("/api/inquiries/analyze", response_model=InquiryAnalysis)
def analyze_inquiry_endpoint(inquiry: Inquiry) -> InquiryAnalysis:
    return analyze_inquiry(inquiry)


@app.post("/api/inquiries/brief", response_model=CreativeBrief)
def create_brief_endpoint(request: BriefRequest) -> CreativeBrief:
    brief = create_creative_brief(request)
    if request.inquiry.deliverable_count and not brief.deliverables:
        brief.deliverables = [f"{request.inquiry.deliverable_count} final edited photos"]
    if not brief.deliverables:
        question = "How many final edited photos would you like delivered?"
        if question not in brief.remaining_questions:
            brief.remaining_questions.append(question)
        if request.inquiry_id:
            update_analysis(request.inquiry_id, "NEEDS_INFORMATION", {
                "status": "needs_information",
                "summary": "The creative direction is captured; the final photo count is still needed.",
                "missing_information": ["final_image_count"],
                "questions": [question],
            })
    return brief


@app.post("/api/moodboards/create", response_model=Moodboard)
def create_moodboard_endpoint(request: MoodboardRequest) -> Moodboard:
    return create_moodboard(request)


@app.post("/api/moodboards/generate", response_model=GeneratedMoodboard)
def generate_moodboard_endpoint(moodboard: Moodboard) -> GeneratedMoodboard:
    return generate_moodboard_images(moodboard)


@app.post("/api/moodboards/create-and-generate", response_model=MoodboardResult)
def create_and_generate_moodboard_endpoint(request: MoodboardRequest) -> MoodboardResult:
    """Create the AI moodboard plan and render its tiles in one demo-friendly call."""
    # A moodboard is a visual planning aid, so optional questions suggested by the
    # brief agent must not deadlock the workflow after intake has already marked an
    # inquiry ready. Deliverables are the one hard prerequisite because they affect
    # the agreed scope and downstream production plan.
    if not request.brief.deliverables:
        raise HTTPException(
            status_code=409,
            detail="Add the requested number of final photos before generating a moodboard.",
        )
    try:
        moodboard = create_moodboard(request)
        generated = generate_moodboard_images(moodboard)
    except Exception as exc:
        print(f"[ShotCraft moodboard] Generation failed: {exc}")
        raise HTTPException(status_code=502, detail="Moodboard generation could not be completed. Please try again in a moment.") from exc
    result = MoodboardResult(moodboard=moodboard, generated=generated)
    inquiry_id = getattr(request, "inquiry_id", None)
    if inquiry_id: save_moodboard(inquiry_id, result.model_dump())
    return result

@app.post("/api/production-packs/create", response_model=ProductionPack)
def create_production_pack(request: BriefRequest, inquiry_id: int | None = None) -> ProductionPack:
    """Create a practical shoot-day plan from the approved brief."""
    b = request.inquiry
    brief = request.inquiry.message
    weather_note = "Check the Seattle forecast 48 hours and again 3 hours before call time."
    if b.shoot_date:
        try:
            params = urlencode({"latitude": 47.6062, "longitude": -122.3321, "start_date": b.shoot_date, "end_date": b.shoot_date, "daily": "weather_code,temperature_2m_max,precipitation_probability_max,wind_speed_10m_max", "timezone": "America/Los_Angeles"})
            with urlopen("https://api.open-meteo.com/v1/forecast?" + params, timeout=3) as response:
                forecast = json.loads(response.read())
            daily = forecast.get("daily", {})
            weather_note = f"Seattle forecast for {b.shoot_date}: high {daily.get('temperature_2m_max', ['—'])[0]}°C, rain probability {daily.get('precipitation_probability_max', ['—'])[0]}%, wind up to {daily.get('wind_speed_10m_max', ['—'])[0]} km/h. Recheck 3 hours before call time."
        except Exception:
            pass
    pack = ProductionPack(
        title=f"{b.client_name} · Shoot production pack",
        location_plan=["Primary: Seattle Center / Space Needle plaza for recognizable architecture and open sightlines.", "Alternate: Pike Place waterfront or a covered Pioneer Square brick arcade.", "Confirm permit, parking, restrooms, and a nearby indoor fallback."],
        shot_list=["Establishing environmental portrait", "Three-quarter hero portrait", "Full-body wardrobe frame", "Close-up lighting portrait", "Walking and candid movement frames"],
        lighting_plan=["Prioritize overcast or open shade for soft light.", "Carry a 5-in-1 reflector and small LED for edge light.", "Expose for skin and protect highlights in the sky."],
        wardrobe_checklist=["Blue polo shirt", "Black jeans", "Boots", "Black sunglasses", "Lint roller and backup shirt"],
        call_sheet={"client": b.client_name, "email": b.client_email, "date": b.shoot_date or "To be confirmed", "duration": "2 hours", "budget": f"${b.budget or 'TBD'}"},
        weather_note=weather_note,
        backup_plan="If rain or unsafe conditions are forecast, move to a covered architectural location and preserve the cinematic palette."
    )
    target_inquiry_id = inquiry_id or request.inquiry_id
    if target_inquiry_id:
        save_production_pack(target_inquiry_id, pack.model_dump())
    return pack
