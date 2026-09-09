"""FastAPI entry point for ShotCraft."""

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from .storage import add_inquiry_message, append_reply, change_request_summaries, confirm_schedule_request, get_change_request, get_schedule_request, get_client_shoot_ideas, inquiry_event_flags, inquiry_timeline, list_inquiries, list_inquiry_messages, message_summaries, pre_shoot_checkin_summaries, record_event, resolve_change_request, save_change_request, save_client_shoot_ideas, save_inquiry, save_pre_shoot_checkin, save_schedule_suggestions, scheduled_times, select_schedule_suggestion, unread_message_counts, update_analysis, update_meeting_location, create_user, authenticate_user, save_moodboard, save_production_pack, approve_production_pack, set_client_decision, schedule_inquiry
from fastapi.staticfiles import StaticFiles
import json
import hashlib
from datetime import datetime, timedelta
from urllib.parse import urlencode
from urllib.request import urlopen

from .agent import analyze_inquiry, assess_change_request, build_production_pack, create_creative_brief, create_moodboard, draft_change_client_update, draft_client_update, recommend_next_shoot_ideas, recommend_schedule_slots
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
    ClientUpdateDraft,
    ChangeApproval,
    ChangeAssessment,
    ShootIdeaRecommendations,
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
    flags = inquiry_event_flags([int(item["id"]) for item in inquiries])
    changes = change_request_summaries([int(item["id"]) for item in inquiries])
    checkins = pre_shoot_checkin_summaries([int(item["id"]) for item in inquiries])
    for item in inquiries:
        item["client_update_sent"] = "CLIENT_UPDATE_SENT" in flags.get(int(item["id"]), set())
        item["change_request"] = changes.get(int(item["id"]))
        item["pre_shoot_checkin"] = checkins.get(int(item["id"]))
    return inquiries

@app.get("/api/client/shoot-ideas", response_model=ShootIdeaRecommendations)
def get_client_shoot_ideas_endpoint(client_email: str, refresh: bool = False) -> ShootIdeaRecommendations:
    """Offer AI concepts without creating an inquiry or persisting a draft."""
    records = [item for item in list_inquiries() if item.get("client_email", "").lower() == client_email.lower()]
    history: list[dict] = []
    for record in records[-8:]:
        try:
            inquiry = json.loads(record.get("payload", "{}"))
            analysis = json.loads(record.get("analysis", "{}"))
        except json.JSONDecodeError:
            continue
        history.append({
            "concept_name": analysis.get("concept_name"),
            "summary": analysis.get("summary"),
            "message": inquiry.get("message"),
            "shoot_date": inquiry.get("shoot_date"),
        })
    if not history:
        history = [{"message": "The client has not planned a shoot yet. Offer broad, approachable portrait concepts."}]
    signature = hashlib.sha256(json.dumps(history, sort_keys=True).encode()).hexdigest()
    cached = None if refresh else get_client_shoot_ideas(client_email, signature)
    if cached:
        return ShootIdeaRecommendations(ideas=cached)
    try:
        recommendations = recommend_next_shoot_ideas(history)
        save_client_shoot_ideas(client_email, signature, [idea.model_dump() for idea in recommendations.ideas])
        return recommendations
    except Exception as exc:
        raise HTTPException(status_code=502, detail="ShotCraft could not generate ideas right now.") from exc


@app.get("/api/inquiries/{inquiry_id}")
def get_inquiry_detail(inquiry_id: int) -> dict:
    record = next((r for r in list_inquiries() if r["id"] == inquiry_id), None)
    if not record: return {"error": "Inquiry not found"}
    record["timeline"] = inquiry_timeline(inquiry_id)
    record["pre_shoot_checkin"] = pre_shoot_checkin_summaries([inquiry_id]).get(inquiry_id)
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

def _fallback_change_assessment(message: str) -> ChangeAssessment:
    lower = message.lower()
    impacts, updates = [], {}
    decision, reason, missing = "FOLLOW_UP", "The request needs one or more details before the plan can be safely changed.", []
    if any(word in lower for word in ("location", "venue", "indoor", "outdoor", "studio", "park")):
        impacts.extend(["Location plan", "Lighting plan", "Weather contingency", "Call sheet"])
        missing.append("Preferred new location")
    if any(word in lower for word in ("time", "date", "schedule", "reschedule")):
        impacts.extend(["Call sheet", "Shoot schedule"])
        decision, reason = "REVIEW", "A date or time change affects a confirmed booking and needs photographer approval."
    if any(word in lower for word in ("wardrobe", "outfit", "dress", "clothes")):
        impacts.append("Wardrobe checklist")
        missing.append("Revised wardrobe details")
    if any(word in lower for word in ("photo", "image", "deliverable", "edit")):
        impacts.append("Deliverables and budget")
        decision, reason = "REVIEW", "A deliverable or budget change needs photographer approval before it becomes a commitment."
    return ChangeAssessment(request_summary="Client requested a change to the current shoot plan.", impacts=impacts or ["Production plan"], proposed_updates=updates, decision=decision, decision_reason=reason, missing_information=missing)

def process_change_request(inquiry_id: int, message: str) -> None:
    record = next((item for item in list_inquiries() if item["id"] == inquiry_id), None)
    if not record or not record.get("production_pack"):
        return
    inquiry = Inquiry(**json.loads(record["payload"]))
    pack = json.loads(record["production_pack"])
    existing = get_change_request(inquiry_id)
    source_message = message
    if existing and existing.get("status") == "PENDING":
        source_message = f"Original client request:\n{existing['source_message']}\n\nClient follow-up:\n{message}"
    try:
        assessment = assess_change_request(inquiry, pack, source_message)
    except Exception as exc:
        print(f"[ShotCraft change request] Assessment failed: {exc}")
        assessment = _fallback_change_assessment(source_message)
    save_change_request(inquiry_id, source_message, assessment.model_dump())

@app.post("/api/inquiries/{inquiry_id}/messages", status_code=201)
def post_inquiry_message(inquiry_id: int, message: InquiryMessageCreate, background_tasks: BackgroundTasks) -> dict:
    created = add_inquiry_message(inquiry_id, message.sender_role, message.sender_name, message.body)
    if not created:
        raise HTTPException(status_code=404, detail="Inquiry not found.")
    change_terms = ("change", "move", "reschedule", "location", "venue", "indoor", "outdoor", "time", "date", "wardrobe", "outfit", "deliverable")
    pending_change = get_change_request(inquiry_id)
    if message.sender_role == "client" and ((pending_change and pending_change.get("status") == "PENDING") or any(term in message.body.lower() for term in change_terms)):
        background_tasks.add_task(process_change_request, inquiry_id, message.body)
    return created

@app.get("/api/inquiries/{inquiry_id}/change-request")
def get_inquiry_change_request(inquiry_id: int) -> dict:
    request = get_change_request(inquiry_id)
    if not request:
        raise HTTPException(status_code=404, detail="No pending change request for this inquiry.")
    return request

@app.post("/api/inquiries/{inquiry_id}/pre-shoot-checkin")
def confirm_pre_shoot_readiness(inquiry_id: int) -> dict:
    record = next((item for item in list_inquiries() if item["id"] == inquiry_id), None)
    if not record:
        raise HTTPException(status_code=404, detail="Inquiry not found.")
    if record.get("status") != "SCHEDULED":
        raise HTTPException(status_code=409, detail="A shoot must be scheduled before confirming readiness.")
    if not save_pre_shoot_checkin(inquiry_id, "READY"):
        raise HTTPException(status_code=500, detail="Could not save the readiness check-in.")
    return {"inquiry_id": inquiry_id, "status": "READY"}

@app.post("/api/inquiries/{inquiry_id}/change-request/approve")
def approve_inquiry_change_request(inquiry_id: int, approval: ChangeApproval) -> dict:
    record = next((item for item in list_inquiries() if item["id"] == inquiry_id), None)
    request = get_change_request(inquiry_id)
    if not record or not request or request.get("status") != "PENDING":
        raise HTTPException(status_code=409, detail="No pending change request is available to approve.")
    if request["assessment"].get("decision") != "APPLY":
        raise HTTPException(status_code=409, detail="This request needs more information or photographer review before the plan can be updated.")
    pack = json.loads(record.get("production_pack") or "{}")
    for section, items in (request["assessment"].get("proposed_updates") or {}).items():
        if section in {"location_plan", "lighting_plan", "wardrobe_checklist"} and isinstance(items, list):
            pack[section] = items
    save_production_pack(inquiry_id, pack)
    meeting_location = request["assessment"].get("confirmed_meeting_location")
    if isinstance(meeting_location, str) and meeting_location.strip():
        update_meeting_location(inquiry_id, meeting_location)
    add_inquiry_message(inquiry_id, "photographer", "Photographer", approval.client_message)
    resolve_change_request(inquiry_id)
    return {"inquiry_id": inquiry_id, "status": "APPROVED"}

@app.post("/api/inquiries/{inquiry_id}/change-request/follow-up")
def send_change_request_follow_up(inquiry_id: int, approval: ChangeApproval) -> dict:
    request = get_change_request(inquiry_id)
    if not request or request.get("status") != "PENDING":
        raise HTTPException(status_code=409, detail="No open change request is available for follow-up.")
    created = add_inquiry_message(inquiry_id, "photographer", "Photographer", approval.client_message)
    if not created:
        raise HTTPException(status_code=404, detail="Inquiry not found.")
    return {"inquiry_id": inquiry_id, "status": "PENDING", "message": "Follow-up sent. The plan remains unchanged."}

@app.post("/api/inquiries/{inquiry_id}/change-request/client-update-draft", response_model=ClientUpdateDraft)
def create_change_client_update_draft(inquiry_id: int) -> ClientUpdateDraft:
    record = next((item for item in list_inquiries() if item["id"] == inquiry_id), None)
    request = get_change_request(inquiry_id)
    if not record or not request:
        raise HTTPException(status_code=404, detail="No change request was found.")
    inquiry = Inquiry(**json.loads(record["payload"]))
    pack = json.loads(record.get("production_pack") or "{}")
    try:
        return draft_change_client_update(inquiry, pack, request["source_message"], request["assessment"])
    except Exception as exc:
        print(f"[ShotCraft change response] Draft generation failed: {exc}")
        return ClientUpdateDraft(message=f"Hi {inquiry.client_name}, thanks for your request. I’m reviewing how it affects the current shoot plan and will confirm the next steps with you shortly.")

def _fallback_client_update(record: dict) -> ClientUpdateDraft:
    payload = json.loads(record.get("payload") or "{}")
    name = payload.get("client_name") or "there"
    if record.get("status") == "SCHEDULED" and record.get("call_time"):
        when = _parse_datetime(record["call_time"])
        date_text = when.strftime("%A, %B %-d at %-I:%M %p") if when else record["call_time"]
        location = record.get("meeting_location") or "the confirmed meeting point"
        return ClientUpdateDraft(message=f"Hi {name}, your shoot is confirmed for {date_text} at {location}. Your production pack has the final creative direction and preparation details. Please message us if anything changes before shoot day.")
    return ClientUpdateDraft(message=f"Hi {name}, your shoot plan has been updated. Please review the latest details in ShotCraft and message us with any questions.")

@app.post("/api/inquiries/{inquiry_id}/client-update-draft", response_model=ClientUpdateDraft)
def create_client_update_draft(inquiry_id: int) -> ClientUpdateDraft:
    record = next((item for item in list_inquiries() if item["id"] == inquiry_id), None)
    if not record:
        raise HTTPException(status_code=404, detail="Inquiry not found.")
    inquiry = Inquiry(**json.loads(record["payload"]))
    try:
        return draft_client_update(inquiry, record.get("status", ""), record.get("call_time"), record.get("meeting_location"))
    except Exception as exc:
        print(f"[ShotCraft client update] Draft generation failed: {exc}")
        return _fallback_client_update(record)

@app.post("/api/inquiries/{inquiry_id}/client-update-sent")
def mark_client_update_sent(inquiry_id: int) -> dict:
    if not next((item for item in list_inquiries() if item["id"] == inquiry_id), None):
        raise HTTPException(status_code=404, detail="Inquiry not found.")
    record_event(inquiry_id, "CLIENT_UPDATE_SENT")
    return {"inquiry_id": inquiry_id, "sent": True}

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

def _fallback_production_pack(inquiry: Inquiry, moodboard: dict | None = None) -> ProductionPack:
    """Keep the workflow moving when the planning model is unavailable or malformed."""
    message = inquiry.message or ""
    city = next((name for name in ("Seattle", "New Delhi", "Delhi", "Bangalore") if name.lower() in message.lower()), None)
    location = city or "Location to be confirmed with the client"
    deliverables = f"{inquiry.deliverable_count} final edited images" if inquiry.deliverable_count else "Final edited images to be confirmed"
    wardrobe = inquiry.wardrobe_details or "Client wardrobe to be confirmed"
    title = f"{inquiry.client_name} · Shoot production pack"
    return ProductionPack(
        title=title,
        location_plan=[f"Primary setting: {location}", "Confirm meeting point, access, and permissions before shoot day.", "Keep a nearby covered alternative available if conditions change."],
        shot_list=["Establishing environmental portrait", "Three-quarter portrait", "Close portrait", "Natural movement frame", "Final detail and variation frames"],
        lighting_plan=["Use available light appropriate to the confirmed setting.", "Check exposure and skin tone before the first set.", "Keep a simple reflector or shade option ready if practical."],
        wardrobe_checklist=[wardrobe, "Bring a clean backup option and comfortable walking shoes.", "Confirm final wardrobe before shoot day."],
        call_sheet={"client": inquiry.client_name, "email": inquiry.contact_email or inquiry.client_email, "date": inquiry.shoot_date or "To be confirmed", "duration": "To be confirmed", "budget": str(inquiry.budget) if inquiry.budget is not None else "To be confirmed", "deliverables": deliverables},
        weather_note="Review local conditions before the shoot and reconfirm the plan if outdoor weather changes.",
        backup_plan="Use a covered nearby setting or reschedule with the client if weather or access makes the planned shoot unsafe.",
    )

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
        pack = _fallback_production_pack(b, moodboard)

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
