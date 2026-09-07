"""FastAPI entry point for ShotCraft."""

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from .storage import add_inquiry_message, append_reply, confirm_schedule_request, get_schedule_request, inquiry_timeline, list_inquiries, list_inquiry_messages, message_summaries, record_event, save_inquiry, save_schedule_suggestions, scheduled_times, select_schedule_suggestion, unread_message_counts, update_analysis, create_user, authenticate_user, save_moodboard, save_production_pack, approve_production_pack, set_client_decision, schedule_inquiry
from fastapi.staticfiles import StaticFiles
import json
from datetime import datetime, timedelta
from urllib.parse import urlencode
from urllib.request import urlopen

from .agent import analyze_inquiry, build_production_pack, create_creative_brief, create_moodboard, recommend_schedule_slots
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
    ScheduleSelection,
    InquiryMessageCreate,
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
        if not result.missing_information:
            record_event(inquiry_id, "QUESTIONS_ANSWERED")
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
    recipient_role = "client" if client_email else "photographer" if photographer_email else None
    if recipient_role:
        counts = unread_message_counts([int(item["id"]) for item in inquiries], recipient_role)
        summaries = message_summaries([int(item["id"]) for item in inquiries])
        for item in inquiries:
            item["unread_messages"] = counts.get(int(item["id"]), 0)
            item.update(summaries.get(int(item["id"]), {"message_count": 0, "latest_message": None}))
    return inquiries

@app.get("/api/inquiries/{inquiry_id}")
def get_inquiry_detail(inquiry_id: int) -> dict:
    record = next((r for r in list_inquiries() if r["id"] == inquiry_id), None)
    if not record: return {"error": "Inquiry not found"}
    record["timeline"] = inquiry_timeline(inquiry_id)
    return record

@app.get("/api/inquiries/{inquiry_id}/timeline")
def get_inquiry_timeline(inquiry_id: int) -> dict:
    return {"inquiry_id": inquiry_id, "timeline": inquiry_timeline(inquiry_id)}

@app.get("/api/inquiries/{inquiry_id}/messages")
def get_inquiry_messages(inquiry_id: int, reader_role: str | None = None) -> list[dict]:
    if not next((item for item in list_inquiries() if item["id"] == inquiry_id), None):
        raise HTTPException(status_code=404, detail="Inquiry not found.")
    if reader_role not in {None, "client", "photographer"}:
        raise HTTPException(status_code=422, detail="reader_role must be client or photographer.")
    return list_inquiry_messages(inquiry_id, reader_role)

@app.post("/api/inquiries/{inquiry_id}/messages", status_code=201)
def post_inquiry_message(inquiry_id: int, message: InquiryMessageCreate) -> dict:
    created = add_inquiry_message(inquiry_id, message.sender_role, message.sender_name, message.body)
    if not created:
        raise HTTPException(status_code=404, detail="Inquiry not found.")
    return created

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

@app.put("/api/inquiries/{inquiry_id}/production-pack", response_model=ProductionPack)
def update_production_pack(inquiry_id: int, pack: ProductionPack) -> ProductionPack:
    record = next((item for item in list_inquiries() if item["id"] == inquiry_id), None)
    if not record:
        raise HTTPException(status_code=404, detail="Inquiry not found.")
    if record["status"] in {"CLIENT_CONFIRMED", "SCHEDULED"}:
        raise HTTPException(status_code=409, detail="This plan is already confirmed. Create a change request before revising it.")
    save_production_pack(inquiry_id, pack.model_dump(), draft=True)
    return pack

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

def _parse_datetime(value: str) -> datetime | None:
    try:
        if not isinstance(value, str) or not value:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None

def _slots_overlap(start: datetime, end: datetime, busy: list[dict]) -> bool:
    for item in busy:
        busy_start = _parse_datetime(item.get("starts_at", ""))
        busy_end = _parse_datetime(item.get("ends_at", "")) or (busy_start + timedelta(hours=2) if busy_start else None)
        if busy_start and busy_end and start < busy_end and end > busy_start:
            return True
    return False

def _fallback_schedule_slots(record: dict, busy: list[dict]) -> list[dict]:
    payload = json.loads(record.get("payload") or "{}")
    preferred = _parse_datetime(payload.get("shoot_date", "")) or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    duration = max(1, min(8, int(payload.get("duration_hours") or 2)))
    location = payload.get("location") or payload.get("city") or "Location to be confirmed"
    slots: list[dict] = []
    for day_offset in range(14):
        day = preferred + timedelta(days=day_offset)
        if day.weekday() >= 5: continue
        for hour in (10, 13, 16):
            start = day.replace(hour=hour, minute=0)
            end = start + timedelta(hours=duration)
            if end.hour > 18 or _slots_overlap(start, end, busy): continue
            slots.append({"starts_at": start.isoformat(timespec="minutes"), "ends_at": end.isoformat(timespec="minutes"), "location": location, "rationale": "Fits the requested timing and avoids the photographer’s confirmed sessions."})
            if len(slots) == 3: return slots
    return slots

def _inquiry_schedule_location(record: dict) -> str:
    payload = json.loads(record.get("payload") or "{}")
    if payload.get("location"):
        return str(payload["location"])
    message = str(payload.get("message") or "")
    for city in ("Seattle", "New Delhi", "Delhi", "Bangalore"):
        if city.lower() in message.lower():
            return city
    if record.get("meeting_location"):
        return str(record["meeting_location"])
    return "Location to be confirmed with your photographer"

def _valid_suggestions(suggestions: list[dict], busy: list[dict], preferred_date: datetime | None, location: str) -> list[dict]:
    valid = []
    for suggestion in suggestions:
        start, end = _parse_datetime(suggestion.get("starts_at", "")), _parse_datetime(suggestion.get("ends_at", ""))
        if not start or not end or end <= start or _slots_overlap(start, end, busy): continue
        if preferred_date and start.date() != preferred_date.date(): continue
        valid.append({"starts_at": start.isoformat(timespec="minutes"), "ends_at": end.isoformat(timespec="minutes"), "location": location, "rationale": "Available on your requested date and clear of the photographer’s existing shoots."})
    return valid[:3]

@app.get("/api/calendar")
def get_calendar(client_email: str | None = None, photographer_email: str | None = None) -> dict:
    if not client_email and not photographer_email:
        raise HTTPException(status_code=422, detail="client_email or photographer_email is required.")
    records = get_inquiries(client_email=client_email, photographer_email=photographer_email)
    entries = []
    for record in records:
        request = get_schedule_request(int(record["id"]))
        if record.get("status") == "SCHEDULED" and record.get("call_time"):
            entries.append({"inquiry_id": record["id"], "kind": "scheduled", "starts_at": record["call_time"], "location": record.get("meeting_location"), "status": "CONFIRMED"})
        if request and request.get("status") == "PENDING_PHOTOGRAPHER":
            entries.append({"inquiry_id": record["id"], "kind": "requested", "starts_at": request.get("selected_starts_at"), "ends_at": request.get("selected_ends_at"), "location": request.get("selected_location"), "status": request.get("status")})
    return {"entries": entries}

@app.get("/api/inquiries/{inquiry_id}/schedule-recommendations")
def get_schedule_recommendations(inquiry_id: int) -> dict:
    record = next((item for item in list_inquiries() if item["id"] == inquiry_id), None)
    if not record: raise HTTPException(status_code=404, detail="Inquiry not found.")
    request = get_schedule_request(inquiry_id)
    if request and request.get("status") == "PENDING_CLIENT":
        preferred = _parse_datetime(json.loads(record.get("payload") or "{}").get("shoot_date", ""))
        expected_location = _inquiry_schedule_location(record)
        suggestions = request.get("suggestions") or []
        if preferred and any((_parse_datetime(item.get("starts_at")) or datetime.min).date() != preferred.date() for item in suggestions):
            request = None
        elif any(item.get("location") != expected_location for item in suggestions):
            request = None
    return request or {"inquiry_id": inquiry_id, "status": None, "suggestions": []}

@app.post("/api/inquiries/{inquiry_id}/schedule-recommendations")
def create_schedule_recommendations(inquiry_id: int) -> dict:
    record = next((item for item in list_inquiries() if item["id"] == inquiry_id), None)
    if not record: raise HTTPException(status_code=404, detail="Inquiry not found.")
    if record.get("status") not in {"CLIENT_CONFIRMED", "SCHEDULED"}:
        raise HTTPException(status_code=409, detail="Confirm the production plan before choosing a shoot time.")
    inquiry = Inquiry(**json.loads(record["payload"]))
    photographer_email = inquiry.photographer_email or ""
    busy = [item for item in scheduled_times(photographer_email) if int(item.get("inquiry_id", -1)) != inquiry_id]
    preferred_date = _parse_datetime(inquiry.shoot_date or "")
    location = _inquiry_schedule_location(record)
    try:
        suggestions = _valid_suggestions([item.model_dump() for item in recommend_schedule_slots(inquiry, busy)], busy, preferred_date, location)
    except Exception:
        suggestions = []
    if len(suggestions) < 3:
        existing = {(item["starts_at"], item["ends_at"]) for item in suggestions}
        suggestions.extend(item for item in _fallback_schedule_slots(record, busy) if (item["starts_at"], item["ends_at"]) not in existing)
    if not suggestions:
        raise HTTPException(status_code=409, detail="No conflict-free times are available yet. Please contact the photographer.")
    return save_schedule_suggestions(inquiry_id, photographer_email, suggestions[:3])

@app.post("/api/inquiries/{inquiry_id}/schedule-selection")
def select_schedule_time(inquiry_id: int, selection: ScheduleSelection) -> dict:
    request = get_schedule_request(inquiry_id)
    if not request: raise HTTPException(status_code=409, detail="Get recommended times before making a selection.")
    matches = any(item["starts_at"] == selection.starts_at and item["ends_at"] == selection.ends_at for item in request["suggestions"])
    if not matches: raise HTTPException(status_code=422, detail="Please select one of the recommended times.")
    if not select_schedule_suggestion(inquiry_id, selection.starts_at, selection.ends_at, selection.location):
        raise HTTPException(status_code=409, detail="This time is no longer available for selection.")
    return get_schedule_request(inquiry_id) or {}

@app.post("/api/inquiries/{inquiry_id}/schedule-confirmation")
def confirm_schedule_time(inquiry_id: int, schedule: ScheduleRequest, photographer_email: str) -> dict:
    start = _parse_datetime(schedule.call_time)
    if not start:
        raise HTTPException(status_code=422, detail="Provide a valid date and time.")
    busy = [item for item in scheduled_times(photographer_email) if int(item.get("inquiry_id", -1)) != inquiry_id]
    if _slots_overlap(start, start + timedelta(hours=2), busy):
        raise HTTPException(status_code=409, detail="That time overlaps another shoot or client time request. Choose a different time.")
    if not confirm_schedule_request(inquiry_id, photographer_email, schedule.call_time, schedule.meeting_location):
        raise HTTPException(status_code=409, detail="This request is not ready for photographer confirmation.")
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
        root = exc
        while getattr(root, "__cause__", None):
            root = root.__cause__
        message = str(root).lower()
        if "moderation" in message or "safety system" in message:
            detail = "The image provider rejected this visual prompt for safety. Try again to generate a safer variation."
        elif "api key" in message or "authentication" in message or "401" in message:
            detail = "Image generation is not configured on the server. Add a valid image-provider API key and restart the app."
        elif "quota" in message or "rate limit" in message or "429" in message:
            detail = "The image provider is temporarily rate-limited or out of credits. Try again later."
        else:
            detail = "The image provider could not complete this request. Check the server logs for the provider error and try again."
        raise HTTPException(status_code=502, detail=detail) from exc
    result = MoodboardResult(moodboard=moodboard, generated=generated)
    inquiry_id = getattr(request, "inquiry_id", None)
    if inquiry_id:
        record_event(inquiry_id, "BRIEF_APPROVED")
        save_moodboard(inquiry_id, result.model_dump())
    return result

@app.post("/api/production-packs/create", response_model=ProductionPack)
def create_production_pack(request: BriefRequest, inquiry_id: int | None = None) -> ProductionPack:
    """Create a practical shoot-day plan from the approved brief."""
    b = request.inquiry
    target_inquiry_id = inquiry_id or request.inquiry_id
    record = next((item for item in list_inquiries() if item["id"] == target_inquiry_id), None) if target_inquiry_id else None
    moodboard = json.loads(record["moodboard"]) if record and record.get("moodboard") else None
    try:
        pack = build_production_pack(b, moodboard)
    except Exception as exc:
        print(f"[ShotCraft production pack] Generation failed: {exc}")
        raise HTTPException(status_code=502, detail="The shoot-specific production pack could not be generated. Please try again.") from exc

    if b.shoot_date and "seattle" in b.message.lower():
        try:
            params = urlencode({"latitude": 47.6062, "longitude": -122.3321, "start_date": b.shoot_date, "end_date": b.shoot_date, "daily": "weather_code,temperature_2m_max,precipitation_probability_max,wind_speed_10m_max", "timezone": "America/Los_Angeles"})
            with urlopen("https://api.open-meteo.com/v1/forecast?" + params, timeout=3) as response:
                forecast = json.loads(response.read())
            daily = forecast.get("daily", {})
            pack.weather_note = f"Seattle forecast for {b.shoot_date}: high {daily.get('temperature_2m_max', ['—'])[0]}°C, rain probability {daily.get('precipitation_probability_max', ['—'])[0]}%, wind up to {daily.get('wind_speed_10m_max', ['—'])[0]} km/h. Recheck 3 hours before call time."
        except Exception:
            pass
    if target_inquiry_id:
        save_production_pack(target_inquiry_id, pack.model_dump())
    return pack
