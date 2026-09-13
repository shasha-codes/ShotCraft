"""FastAPI entry point for ShotCraft."""

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from dotenv import load_dotenv

# Load local development secrets before importing modules that configure model clients.
# Production values still come from the systemd EnvironmentFile on EC2.
load_dotenv()

from .storage import add_inquiry_message, append_reply, change_request_summaries, confirm_client_schedule_selection, confirm_schedule_request, create_auth_session, get_cancellation_agent_review, get_change_request, get_schedule_request, get_client_shoot_ideas, get_inquiry, get_planning_workflow, get_session_user, inquiry_timeline, list_inquiries, list_inquiry_followups, list_inquiry_messages, list_photographers, message_summaries, pre_shoot_checkin_summaries, record_event, resolve_change_request, revoke_auth_session, save_cancellation_agent_review, save_change_request, save_client_shoot_ideas, save_inquiry, save_pre_shoot_checkin, save_schedule_agent_review, save_schedule_suggestions, schedule_request_summaries, scheduled_times, select_schedule_suggestion, unread_message_counts, update_analysis, update_meeting_location, update_planning_workflow, update_user_profile, create_user, authenticate_user, save_creative_brief, save_moodboard, save_production_pack, approve_production_pack, set_client_decision, schedule_inquiry, request_cancellation, decide_cancellation
from .storage import cancellation_conversation, get_photographer_identity, list_client_notifications, list_photographer_notifications, mark_all_client_notifications_read, mark_all_photographer_notifications_read, mark_client_notification_read, mark_photographer_notification_read, notify_client_followups_complete
from fastapi.staticfiles import StaticFiles
import json
import hashlib
import re
import threading
import uuid
import os
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest, urlopen

from .agent import assess_change_request, build_production_pack, coordinate_cancellation_review, coordinate_creative_direction, coordinate_inquiry_intake, coordinate_schedule_slots, create_creative_brief, create_moodboard, draft_change_client_update, recommend_next_shoot_ideas
from .images import generate_moodboard_images, public_image_error
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
    ScheduleChangeRequest,
    ScheduleProposal,
    InquiryMessageCreate,
    ClientUpdateDraft,
    ProfileUpdate,
    ChangeApproval,
    ChangeAssessment,
    CancellationRequest,
    CancellationDecision,
    ShootIdeaRecommendations,
)


_moodboard_jobs: dict[str, dict] = {}
_moodboard_jobs_lock = threading.Lock()
_city_image_cache: dict[str, tuple[float, dict]] = {}
_city_image_cache_lock = threading.Lock()


def _start_moodboard_job(inquiry_id: int | None, moodboard: Moodboard) -> str:
    job_id = uuid.uuid4().hex
    with _moodboard_jobs_lock:
        _moodboard_jobs[job_id] = {
            "status": "generating",
            "inquiry_id": inquiry_id,
            "moodboard": moodboard.model_dump(),
            "tiles": [None] * len(moodboard.tiles),
            "error": None,
        }
    if inquiry_id:
        save_moodboard(inquiry_id, {
            "moodboard": moodboard.model_dump(),
            "generated": {"title": moodboard.title, "model_id": "gpt-image-2.5-flare", "tiles": [None] * len(moodboard.tiles)},
            "status": "generating", "job_id": job_id,
        })

    def run() -> None:
        def on_tile(index, tile) -> None:
            with _moodboard_jobs_lock:
                job = _moodboard_jobs.get(job_id)
                if job:
                    job["tiles"][index] = tile.model_dump()
                    tiles = list(job["tiles"])
            # The project page reads persisted state, so save every completed
            # tile instead of waiting for the entire image job to finish.
            if inquiry_id:
                save_moodboard(inquiry_id, {
                    "moodboard": moodboard.model_dump(),
                    "generated": {"title": moodboard.title, "model_id": "gpt-image-2.5-flare", "tiles": tiles},
                    "status": "generating",
                    "job_id": job_id,
                })

        try:
            generated = generate_moodboard_images(moodboard, on_tile=on_tile)
            if inquiry_id:
                save_moodboard(inquiry_id, {"moodboard": moodboard.model_dump(), "generated": generated.model_dump(), "status": "complete", "job_id": job_id})
                record = get_inquiry(inquiry_id)
                if record and not record.get("production_pack"):
                    inquiry = Inquiry(**json.loads(record["payload"]))
                    update_planning_workflow(inquiry_id, "BUILDING_PLAN", "RUNNING", "Generated and verified all moodboard images")
                    try:
                        pack = build_production_pack(inquiry, {"moodboard": moodboard.model_dump()})
                    except Exception as exc:
                        print(f"[ShotCraft resumed shoot plan] Generation failed: {exc}")
                        pack = _fallback_production_pack(inquiry, {"moodboard": moodboard.model_dump()})
                    save_production_pack(inquiry_id, pack.model_dump(), draft=True)
                    record_event(inquiry_id, "DRAFT_PLAN_READY")
                    update_planning_workflow(inquiry_id, "PHOTOGRAPHER_REVIEW", "WAITING_FOR_PHOTOGRAPHER", "Resumed successfully and prepared an editable shoot plan")
            with _moodboard_jobs_lock:
                job = _moodboard_jobs.get(job_id)
                if job:
                    job["status"] = "complete"
        except Exception as exc:
            print(f"[ShotCraft moodboard] Async generation failed: {exc}")
            with _moodboard_jobs_lock:
                job = _moodboard_jobs.get(job_id)
                if job:
                    job["status"] = "failed"
                    job["error"] = public_image_error(exc)
            if inquiry_id:
                save_moodboard(inquiry_id, {
                    "moodboard": moodboard.model_dump(),
                    "generated": {"title": moodboard.title, "model_id": "gpt-image-2.5-flare", "tiles": tiles if 'tiles' in locals() else [None] * len(moodboard.tiles)},
                    "status": "failed", "job_id": job_id, "error": public_image_error(exc),
                })
                update_planning_workflow(inquiry_id, "INTERRUPTED", "NEEDS_ATTENTION", "Paused safely so moodboard generation can be retried", str(exc))

    threading.Thread(target=run, daemon=True).start()
    return job_id

app = FastAPI(title="ShotCraft API", version="0.1.0")


@app.middleware("http")
async def prevent_workspace_bundle_caching(request: Request, call_next):
    """Always serve the evolving client workspace assets fresh in development."""
    response = await call_next(request)
    if request.url.path in {"/static/client-workspace.js", "/static/client-workspace.css", "/static/client.html", "/static/us-cities.json", "/static/photographer-spa.js", "/static/photographer-spa.css", "/static/photographer.html"}:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse("static/brand/shotcraft-mark.png", media_type="image/png")

SESSION_COOKIE = "shotcraft_session"
SESSION_MAX_AGE = 14 * 24 * 60 * 60
PUBLIC_API_PATHS = {"/api/auth/login", "/api/auth/signup", "/api/auth/me", "/api/auth/logout", "/api/photographers"}

def _session_cookie_is_secure(request: Request) -> bool:
    """Use Secure cookies automatically once TLS terminates at the app or proxy."""
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").split(",")[0].strip() == "https"

def _set_session_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE, value=token, max_age=SESSION_MAX_AGE, httponly=True,
        secure=_session_cookie_is_secure(request), samesite="lax", path="/",
    )

def _current_user(request: Request) -> dict | None:
    return get_session_user(request.cookies.get(SESSION_COOKIE))

def _can_access_inquiry(user: dict, inquiry_id: int) -> bool:
    record = get_inquiry(inquiry_id)
    if not record:
        return True  # Let the endpoint return its normal 404 response.
    if user["user_type"] == "client":
        return record.get("client_email", "").lower() == user["email"].lower()
    try:
        assigned = json.loads(record.get("payload") or "{}").get("photographer_email", "")
    except json.JSONDecodeError:
        assigned = ""
    return bool(assigned) and assigned.lower() == user["email"].lower()

@app.middleware("http")
async def require_session_for_api(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.url.path not in PUBLIC_API_PATHS and request.method != "OPTIONS":
        user = _current_user(request)
        if not user:
            return JSONResponse(status_code=401, content={"detail": "Sign in to continue."})
        request.state.user = user
        match = re.fullmatch(r"/api/inquiries/(\d+)(?:/.*)?", request.url.path)
        if match and not _can_access_inquiry(user, int(match.group(1))):
            return JSONResponse(status_code=403, content={"detail": "You do not have access to this inquiry."})
    return await call_next(request)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Minimal unauthenticated health check for the EC2 service and reverse proxy."""
    return {"status": "ok"}


@app.get("/")
def health_check() -> FileResponse:
    return FileResponse("static/index.html")

@app.get("/auth")
def auth_page(request: Request):
    user = _current_user(request)
    if user:
        return RedirectResponse("/photographer" if user["user_type"] == "photographer" else "/client", status_code=303)
    return FileResponse("static/auth.html")

@app.post("/api/auth/signup")
def signup(payload: AuthRequest, request: Request, response: Response) -> dict:
    if not payload.name or len(payload.password) < 8:
        raise HTTPException(status_code=422, detail="Name and a password of at least 8 characters are required.")
    user = create_user(payload.name, payload.email, payload.password, payload.user_type, payload.city, payload.bio, payload.specialties)
    if not user:
        raise HTTPException(status_code=409, detail="An account with that email already exists, or the account type is invalid.")
    authenticated = authenticate_user(payload.email, payload.password, payload.user_type or "")
    if not authenticated:
        raise HTTPException(status_code=500, detail="Could not start a session. Please sign in.")
    _set_session_cookie(response, request, create_auth_session(authenticated["id"]))
    return {key: authenticated[key] for key in ("name", "email", "user_type", "city", "bio", "specialties", "profile_image")}

@app.post("/api/auth/login")
def login(payload: AuthRequest, request: Request, response: Response) -> dict:
    user = authenticate_user(payload.email, payload.password, payload.user_type or "")
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    _set_session_cookie(response, request, create_auth_session(user["id"]))
    return {key: user[key] for key in ("name", "email", "user_type", "city", "bio", "specialties", "profile_image")}

@app.get("/api/auth/me")
def current_session(request: Request) -> dict:
    user = _current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return {key: user[key] for key in ("name", "email", "user_type", "city", "bio", "specialties", "profile_image")}

@app.post("/api/auth/logout", status_code=204)
def logout(request: Request, response: Response) -> Response:
    revoke_auth_session(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response

@app.put("/api/auth/profile")
def update_profile(payload: ProfileUpdate, request: Request) -> dict:
    user = request.state.user
    if payload.profile_image and not re.fullmatch(r"data:image/(?:png|jpeg|jpg|webp);base64,[A-Za-z0-9+/=]+", payload.profile_image):
        raise HTTPException(status_code=422, detail="Profile pictures must be PNG, JPEG, or WebP images.")
    updated = update_user_profile(user["id"], payload.city, payload.bio, payload.specialties if user["user_type"] == "photographer" else None, payload.profile_image)
    if not updated:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return {key: updated[key] for key in ("name", "email", "user_type", "city", "bio", "specialties", "profile_image")}


@app.get("/api/photographers")
def get_photographers(search: str = "", city: str = "") -> list[dict[str, str | None]]:
    """A small client-facing directory of registered photographer workspaces."""
    return list_photographers(search, city)


@app.get("/api/city-images")
def get_city_images(city: str) -> dict:
    """Find a small, cached Pexels fallback gallery for an uncatalogued city."""
    label = re.sub(r"\s+", " ", city).strip()
    if not label or len(label) > 100:
        raise HTTPException(status_code=400, detail="Enter a valid city name.")
    cache_key = label.lower()
    now = time.monotonic()
    with _city_image_cache_lock:
        cached = _city_image_cache.get(cache_key)
        if cached and now - cached[0] < 86_400:
            return cached[1]

    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        return {"label": label, "gallery": [], "attribution": []}
    try:
        params = urlencode({"query": f"{label} city skyline", "orientation": "landscape", "per_page": 3})
        request = UrlRequest(
            f"https://api.pexels.com/v1/search?{params}",
            headers={"Authorization": api_key, "User-Agent": "ShotCraft city-image fallback"},
        )
        with urlopen(request, timeout=12) as response:
            photos = json.load(response).get("photos", [])
        result = {
            "label": label,
            "aliases": [label.lower()],
            "gallery": [photo["src"]["landscape"] for photo in photos[:3]],
            "attribution": [
                {"photographer": photo["photographer"], "photographer_url": photo["photographer_url"], "photo_url": photo["url"], "provider": "Pexels"}
                for photo in photos[:3]
            ],
        }
    except Exception as exc:
        print(f"[ShotCraft city images] Pexels fallback failed for {label}: {exc}")
        result = {"label": label, "gallery": [], "attribution": []}
    with _city_image_cache_lock:
        _city_image_cache[cache_key] = (now, result)
    return result


@app.get("/client")
def client_inquiry_page(request: Request):
    user = _current_user(request)
    if not user or user["user_type"] != "client":
        return RedirectResponse("/auth?mode=login", status_code=303)
    return FileResponse("static/client.html", headers={"Cache-Control": "no-store, max-age=0"})

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
def photographer_dashboard(request: Request):
    user = _current_user(request)
    if not user or user["user_type"] != "photographer":
        return RedirectResponse("/auth?mode=login", status_code=303)
    return FileResponse("static/photographer.html", headers={"Cache-Control": "no-store, max-age=0"})

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
    """Run the resumable Strands-backed shoot-planning workflow."""
    try:
        update_planning_workflow(inquiry_id, "ANALYZING", "RUNNING", "Read the inquiry and client follow-up history")
        intake = coordinate_inquiry_intake(inquiry_id, inquiry, list_inquiry_followups(inquiry_id))
        result = intake["analysis"]
        record_event(inquiry_id, "INTAKE_AGENT_TOOLS_COMPLETED", {
            "agent_used_tools": intake["agent_used_tools"], "activity": intake["activity"],
        })
        update_planning_workflow(inquiry_id, "ANALYZING", "COMPLETE", "Strands reviewed the inquiry and follow-ups with intake tools")
        # Deliverable count is required for both pricing and the production brief.
        # Enforce this contract even if the intake model overlooks it.
        if inquiry.deliverable_count is None and "final_image_count" not in result.missing_information:
            result.missing_information.append("final_image_count")
            result.questions.append("How many final edited photos would you like delivered?")
        status = "NEEDS_INFORMATION" if result.missing_information else "DRAFTING_PLAN"
        update_analysis(inquiry_id, status, result.model_dump())
        if result.missing_information:
            update_planning_workflow(inquiry_id, "NEEDS_DETAILS", "WAITING_FOR_CLIENT", f"Asked {len(result.questions)} targeted follow-up question{'s' if len(result.questions) != 1 else ''}")
        if not result.missing_information:
            # A follow-up acknowledgement belongs here—not at form submission—
            # because only completed intake analysis can prove no details remain.
            notify_client_followups_complete(inquiry_id)
            # The structured intake supplied the same information that the
            # legacy follow-up step collected, so keep the short journey linear.
            record_event(inquiry_id, "FOLLOWUP_SUBMITTED", {"source": "structured_intake"})
            record_event(inquiry_id, "QUESTIONS_ANSWERED")
            # Prepare one complete, editable plan for the photographer. A plan is
            # not considered drafted until the visual references have rendered.
            draft_job_id = uuid.uuid4().hex
            with _moodboard_jobs_lock:
                _moodboard_jobs[draft_job_id] = {
                    "status": "generating", "inquiry_id": inquiry_id,
                    "moodboard": {}, "tiles": [None] * 4, "error": None,
                }
            draft_moodboard = None
            partial_tiles = [None] * 4
            try:
                # Make the in-progress state visible to the photographer as soon
                # as the client submits their complete follow-up—before the brief
                # generation call itself has returned.
                save_moodboard(inquiry_id, {
                    "moodboard": {"title": "Preparing creative direction", "tiles": []},
                    "generated": {"title": "Preparing creative direction", "model_id": "gpt-image-2.5-flare", "tiles": [None, None, None, None]},
                    "status": "generating", "job_id": draft_job_id,
                })
                update_planning_workflow(inquiry_id, "CREATING_BRIEF", "RUNNING", "Strands is reviewing the inquiry and follow-ups with creative specialist tools")

                def on_brief(brief: CreativeBrief) -> None:
                    save_creative_brief(inquiry_id, brief.model_dump())
                    update_planning_workflow(inquiry_id, "CREATING_MOODBOARD", "RUNNING", "Strands created the brief and is planning the visual direction")

                def on_moodboard(moodboard: Moodboard) -> None:
                    nonlocal draft_moodboard, partial_tiles
                    draft_moodboard = moodboard
                    partial_tiles = [None] * len(moodboard.tiles)
                    with _moodboard_jobs_lock:
                        _moodboard_jobs[draft_job_id]["moodboard"] = moodboard.model_dump()
                        _moodboard_jobs[draft_job_id]["tiles"] = partial_tiles
                    save_moodboard(inquiry_id, {
                        "moodboard": moodboard.model_dump(),
                        "generated": {"title": moodboard.title, "model_id": "gpt-image-2.5-flare", "tiles": partial_tiles},
                        "status": "generating", "job_id": draft_job_id,
                    })

                direction = coordinate_creative_direction(
                    inquiry_id, inquiry, list_inquiry_followups(inquiry_id), on_brief, on_moodboard,
                )
                moodboard = direction["moodboard"]
                record_event(inquiry_id, "CREATIVE_AGENT_TOOLS_COMPLETED", {
                    "agent_used_tools": direction["agent_used_tools"], "activity": direction["activity"],
                })
                update_planning_workflow(inquiry_id, "GENERATING_IMAGES", "RUNNING", "Strands completed the brief and moodboard plan; rendering image references")

                def save_completed_tile(index, tile) -> None:
                    partial_tiles[index] = tile.model_dump()
                    save_moodboard(inquiry_id, {
                        "moodboard": moodboard.model_dump(),
                        "generated": {"title": moodboard.title, "model_id": "gpt-image-2.5-flare", "tiles": partial_tiles},
                        "status": "generating", "job_id": draft_job_id,
                    })

                generated = generate_moodboard_images(moodboard, on_tile=save_completed_tile)
                save_moodboard(inquiry_id, {"moodboard": moodboard.model_dump(), "generated": generated.model_dump(), "status": "complete", "job_id": draft_job_id})
                update_planning_workflow(inquiry_id, "BUILDING_PLAN", "RUNNING", "Generated and verified all moodboard images")
                with _moodboard_jobs_lock:
                    _moodboard_jobs[draft_job_id]["status"] = "complete"
                try:
                    pack = build_production_pack(inquiry, {"moodboard": moodboard.model_dump()})
                except Exception as exc:
                    print(f"[ShotCraft draft shoot plan] Generation failed: {exc}")
                    pack = _fallback_production_pack(inquiry, {"moodboard": moodboard.model_dump()})
                save_production_pack(inquiry_id, pack.model_dump(), draft=True)
                record_event(inquiry_id, "DRAFT_PLAN_READY")
                update_analysis(inquiry_id, "READY_FOR_REVIEW", result.model_dump())
                update_planning_workflow(inquiry_id, "PHOTOGRAPHER_REVIEW", "WAITING_FOR_PHOTOGRAPHER", "Prepared an editable shoot plan for photographer review")
            except Exception as exc:
                # Keep the request available to the photographer, but never mark
                # the shoot plan as drafted without its image references.
                with _moodboard_jobs_lock:
                    job = _moodboard_jobs[draft_job_id]
                    if job["status"] == "generating":
                        job["status"] = "failed"
                        job["error"] = public_image_error(exc) if draft_moodboard else "The moodboard plan could not be prepared."
                        title = draft_moodboard.title if draft_moodboard else "Preparing creative direction"
                        save_moodboard(inquiry_id, {
                            "moodboard": draft_moodboard.model_dump() if draft_moodboard else {"title": title, "tiles": []},
                            "generated": {"title": title, "model_id": "gpt-image-2.5-flare", "tiles": partial_tiles},
                            "status": "failed", "job_id": draft_job_id, "error": job["error"],
                        })
                update_analysis(inquiry_id, "READY_FOR_REVIEW", result.model_dump())
                update_planning_workflow(inquiry_id, "INTERRUPTED", "NEEDS_ATTENTION", "Paused safely so moodboard generation can be retried", str(exc))
                print(f"[ShotCraft draft plan] Generation failed for inquiry {inquiry_id}: {exc}")
        print(f"[ShotCraft notification] Inquiry {inquiry_id}: {status}")
    except Exception as exc:
        update_analysis(inquiry_id, "PROCESSING_ERROR", {"error": str(exc)})
        update_planning_workflow(inquiry_id, "INTERRUPTED", "NEEDS_ATTENTION", "The planning workflow stopped and can be resumed", str(exc))
        print(f"[ShotCraft notification] Inquiry {inquiry_id} failed: {exc}")

@app.post("/api/inquiries")
def submit_inquiry(inquiry: Inquiry, background_tasks: BackgroundTasks, request: Request) -> dict[str, object]:
    user = request.state.user
    if user["user_type"] != "client":
        raise HTTPException(status_code=403, detail="Only client accounts can create inquiries.")
    # Identity comes from the authenticated session, never from browser input.
    inquiry.client_name = user["name"]
    inquiry.client_email = user["email"]
    inquiry.contact_email = user["email"]
    inquiry_id = save_inquiry(inquiry)
    background_tasks.add_task(process_inquiry, inquiry_id, inquiry)
    return {"id": inquiry_id, "status": "NEW", "message": "Inquiry received."}

@app.get("/api/inquiries")
def get_inquiries(request: Request, client_email: str | None = None, photographer_email: str | None = None) -> list[dict]:
    user = request.state.user
    if user["user_type"] == "client":
        client_email, photographer_email = user["email"], None
    else:
        client_email, photographer_email = None, user["email"]
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
    inquiry_ids = [int(item["id"]) for item in inquiries]
    changes = change_request_summaries(inquiry_ids)
    schedule_requests = schedule_request_summaries(inquiry_ids)
    checkins = pre_shoot_checkin_summaries([int(item["id"]) for item in inquiries])
    for item in inquiries:
        item["change_request"] = changes.get(int(item["id"]))
        item["schedule_request"] = schedule_requests.get(int(item["id"]))
        item["pre_shoot_checkin"] = checkins.get(int(item["id"]))
    return inquiries

@app.get("/api/notifications")
def get_client_notifications(request: Request) -> dict:
    user = request.state.user
    if user["user_type"] != "client":
        raise HTTPException(status_code=403, detail="Notifications are available to client accounts.")
    notifications = list_client_notifications(user["email"])
    return {
        "notifications": notifications,
        "unread_count": sum(1 for item in notifications if not item.get("resolved_at") and not item.get("read_at")),
        "action_count": sum(1 for item in notifications if item.get("action_required") and not item.get("resolved_at")),
    }

@app.post("/api/notifications/{notification_id}/read")
def read_client_notification(notification_id: int, request: Request) -> dict:
    user = request.state.user
    if user["user_type"] != "client":
        raise HTTPException(status_code=403, detail="Notifications are available to client accounts.")
    if not mark_client_notification_read(notification_id, user["email"]):
        raise HTTPException(status_code=404, detail="Notification not found.")
    return {"ok": True}

@app.post("/api/notifications/read-all")
def read_all_client_notifications(request: Request) -> dict:
    user = request.state.user
    if user["user_type"] != "client":
        raise HTTPException(status_code=403, detail="Notifications are available to client accounts.")
    return {"ok": True, "updated": mark_all_client_notifications_read(user["email"])}

@app.get("/api/photographer/notifications")
def get_photographer_notifications(request: Request) -> dict:
    user = request.state.user
    if user["user_type"] != "photographer":
        raise HTTPException(status_code=403, detail="Notifications are available to photographer accounts.")
    notifications = list_photographer_notifications(user["email"])
    return {
        "notifications": notifications,
        "unread_count": sum(1 for item in notifications if not item.get("resolved_at") and not item.get("read_at")),
        "action_count": sum(1 for item in notifications if item.get("action_required") and not item.get("resolved_at")),
    }

@app.post("/api/photographer/notifications/read-all")
def read_all_photographer_notifications(request: Request) -> dict:
    user = request.state.user
    if user["user_type"] != "photographer":
        raise HTTPException(status_code=403, detail="Notifications are available to photographer accounts.")
    return {"ok": True, "updated": mark_all_photographer_notifications_read(user["email"])}

@app.post("/api/photographer/notifications/{notification_id}/read")
def read_photographer_notification(notification_id: int, request: Request) -> dict:
    user = request.state.user
    if user["user_type"] != "photographer":
        raise HTTPException(status_code=403, detail="Notifications are available to photographer accounts.")
    if not mark_photographer_notification_read(notification_id, user["email"]):
        raise HTTPException(status_code=404, detail="Notification not found.")
    return {"ok": True}

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
    moodboard = json.loads(record.get("moodboard") or "{}")
    if moodboard.get("status") == "generating":
        with _moodboard_jobs_lock:
            active = moodboard.get("job_id") in _moodboard_jobs and _moodboard_jobs[moodboard["job_id"]]["status"] == "generating"
        if not active:
            # Worker threads do not survive an app restart. Preserve any finished
            # tiles, but never leave the project spinning forever.
            moodboard["status"] = "interrupted"
            save_moodboard(inquiry_id, moodboard)
            record["moodboard"] = json.dumps(moodboard)
    record["change_request"] = change_request_summaries([inquiry_id]).get(inquiry_id)
    record["schedule_request"] = schedule_request_summaries([inquiry_id]).get(inquiry_id)
    record["followups"] = list_inquiry_followups(inquiry_id)
    record["timeline"] = inquiry_timeline(inquiry_id)
    record["pre_shoot_checkin"] = pre_shoot_checkin_summaries([inquiry_id]).get(inquiry_id)
    record["planning_workflow"] = get_planning_workflow(inquiry_id)
    record["cancellation_conversation"] = cancellation_conversation(inquiry_id) if record.get("cancellation_status") == "PENDING" else None
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
    return ChangeAssessment(request_summary="Client requested a change to the current shoot plan.", impacts=impacts or ["Shoot plan"], proposed_updates=updates, decision=decision, decision_reason=reason, missing_information=missing)

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
    record = get_inquiry(inquiry_id)
    if record and record.get("cancellation_status") == "PENDING":
        conversation = cancellation_conversation(inquiry_id)
        if message.sender_role == "photographer":
            update_planning_workflow(inquiry_id, "CANCELLATION_CONTACTED", "WAITING_FOR_CLIENT", "Photographer messaged the client; cancellation remains pending and the booking stays scheduled")
        elif message.sender_role == "client" and conversation["client_reply"]:
            update_planning_workflow(inquiry_id, "CANCELLATION_CLIENT_REPLIED", "WAITING_FOR_PHOTOGRAPHER", "Client replied; photographer can continue the conversation or approve or decline cancellation")
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

@app.post("/api/inquiries/{inquiry_id}/reply")
def reply_to_inquiry(inquiry_id: int, reply: InquiryReply, background_tasks: BackgroundTasks) -> dict[str, object]:
    inquiry = append_reply(inquiry_id, reply.answers)
    if not inquiry: return {"error": "Inquiry not found"}
    background_tasks.add_task(process_inquiry, inquiry_id, Inquiry(**inquiry))
    return {"id": inquiry_id, "status": "NEW", "message": "Reply received and queued for re-analysis."}

@app.post("/api/inquiries/{inquiry_id}/production/approve")
def approve_production(inquiry_id: int) -> dict[str, object]:
    if not approve_production_pack(inquiry_id):
        return {"error": "Shoot plan not found."}
    update_planning_workflow(inquiry_id, "CHECKING_AVAILABILITY", "RUNNING", "Photographer approved the creative plan; checking booking availability")
    return {"id": inquiry_id, "production_approved": True, "message": "Shoot plan approved."}

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
    if not decision.cancellation_policy_accepted:
        raise HTTPException(status_code=422, detail="Accept the cancellation policy before confirming this booking.")
    policy = {
        "version": "2026-09-v1",
        "summary": "Cancel 48+ hours before the shoot for no fee. Cancellations 24–48 hours before may incur a 25% fee; cancellations under 24 hours may incur a 50% fee.",
        "tiers": [{"minimum_notice_hours": 48, "fee_percent": 0}, {"minimum_notice_hours": 24, "fee_percent": 25}, {"minimum_notice_hours": 0, "fee_percent": 50}],
    }
    if not set_client_decision(inquiry_id, "CLIENT_CONFIRMED", decision.note, policy): return {"error": "An approved shoot plan is required."}
    return {"id": inquiry_id, "status": "CLIENT_CONFIRMED"}

@app.post("/api/inquiries/{inquiry_id}/client-change-request")
def client_change_request(inquiry_id: int, decision: ClientDecision) -> dict[str, object]:
    if not set_client_decision(inquiry_id, "CLIENT_CHANGE_REQUESTED", decision.note): return {"error": "An approved shoot plan is required."}
    return {"id": inquiry_id, "status": "CLIENT_CHANGE_REQUESTED"}

def _format_schedule_window_for_display(value: str) -> str:
    """Keep persisted schedule preferences machine-readable but message text human-readable."""
    match = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*[–-]\s*(\d{1,2}):(\d{2})\s*", value or "")
    if not match:
        return value
    def clock(hour: str, minute: str) -> str:
        hour_number = int(hour)
        return f"{(hour_number - 1) % 12 + 1}:{minute} {'AM' if hour_number < 12 else 'PM'}"
    return f"{clock(match.group(1), match.group(2))} – {clock(match.group(3), match.group(4))}"


def _format_schedule_datetime_for_display(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%b %-d, %Y at %-I:%M %p")
    except (TypeError, ValueError):
        return value.replace("T", " ")


@app.post("/api/inquiries/{inquiry_id}/schedule-change-request")
def request_schedule_change(inquiry_id: int, change: ScheduleChangeRequest, request: Request) -> dict:
    record = next((item for item in list_inquiries() if item["id"] == inquiry_id), None)
    if not record:
        raise HTTPException(status_code=404, detail="Inquiry not found.")
    if request.state.user["user_type"] != "client" or record.get("client_email", "").lower() != request.state.user["email"].lower():
        raise HTTPException(status_code=403, detail="Only the client who owns this shoot can request a schedule change.")
    if record.get("status") not in {"SCHEDULED", "CLIENT_CONFIRMED"}:
        raise HTTPException(status_code=409, detail="Schedule changes are available once a shoot plan has been confirmed.")
    requested = {"shoot_date": change.shoot_date, "availability_windows": change.availability_windows}
    requested_date = datetime.fromisoformat(change.shoot_date).strftime("%b %-d, %Y")
    display_windows = ", ".join(_format_schedule_window_for_display(window) for window in change.availability_windows)
    source = f"Schedule change request\nRequested date: {requested_date}\nPreferred time windows: {display_windows}"
    if change.note and change.note.strip():
        source += f"\nClient note: {change.note.strip()}"
    assessment = {"request_summary":"Client requested a new shoot date or preferred time window.","impacts":["The confirmed booking remains unchanged until the photographer proposes and the client selects a new time."],"proposed_updates":{},"decision":"REVIEW","decision_reason":"A confirmed date or time needs photographer approval.","missing_information":[],"confirmed_meeting_location":None,"schedule_change":requested}
    save_change_request(inquiry_id, source, assessment)
    update_planning_workflow(inquiry_id, "REVIEWING_TIME_CHANGE", "RUNNING", "Client sent new date and time preferences; the current booking remains confirmed")
    try:
        recommendation = _schedule_recommendation_result(inquiry_id, record)
        suggestions = recommendation["suggestions"]
        save_schedule_suggestions(
            inquiry_id,
            json.loads(record.get("payload") or "{}").get("photographer_email") or "",
            suggestions,
            status="PENDING_PHOTOGRAPHER_REVIEW",
        )
        save_schedule_agent_review(inquiry_id, {"summary": recommendation["summary"], "activity": recommendation["agent_activity"], "agent_used_tools": recommendation["agent_used_tools"], "agent_execution": recommendation.get("agent_execution", "unknown"), "suggestion_count": len(suggestions), "suggestions": suggestions})
        update_planning_workflow(inquiry_id, "PHOTOGRAPHER_REVIEW", "WAITING_FOR_PHOTOGRAPHER", f"Reviewed the time change and prepared {len(suggestions)} conflict-free alternative{'s' if len(suggestions) != 1 else ''}")
    except HTTPException as exc:
        suggestions = []
        save_schedule_agent_review(inquiry_id, {"summary": exc.detail, "activity": ["Checked requested duration, preferred windows, and confirmed bookings"], "agent_used_tools": False, "suggestion_count": 0})
        update_planning_workflow(inquiry_id, "PHOTOGRAPHER_REVIEW", "WAITING_FOR_PHOTOGRAPHER", "No safe time on the requested date; ask the client for another date")
    add_inquiry_message(inquiry_id, "client", request.state.user["name"], source)
    return {"inquiry_id": inquiry_id, "status": "PENDING", "schedule_change": requested, "suggestion_count": len(suggestions)}

def run_cancellation_agent_review(inquiry_id: int) -> None:
    """Prepare a read-only Strands review after the client request has been saved."""
    record = get_inquiry(inquiry_id)
    if not record or record.get("cancellation_status") != "PENDING":
        return
    inquiry = json.loads(record.get("payload") or "{}")
    amount = max(0.0, float(inquiry.get("budget") or 0))
    fee = float(record.get("cancellation_fee") or 0)
    timeline = inquiry_timeline(inquiry_id)
    request_event = next((item for item in timeline if item["type"] == "CANCELLATION_REQUESTED"), None)
    notice_hours = (request_event or {}).get("metadata", {}).get("notice_hours")
    policy = json.loads(record.get("cancellation_policy") or "{}")
    photographer = get_photographer_identity(inquiry.get("photographer_email") or "")
    try:
        review = coordinate_cancellation_review(
            inquiry_id,
            get_booking=lambda: {"call_time": record.get("call_time"), "location": record.get("meeting_location"), "duration_minutes": inquiry.get("duration_minutes"), "booking_amount": amount, "status": record.get("status"), "photographer_name": (photographer or {}).get("name"), "photographer_email": (photographer or {}).get("email")},
            get_policy=lambda: {"accepted_policy": policy, "accepted_at": record.get("cancellation_policy_accepted_at"), "notice_hours_at_request": notice_hours, "policy_fee": fee, "estimated_refund": float(record.get("cancellation_refund") or 0)},
            get_request=lambda: {"reason": record.get("cancellation_reason"), "note": record.get("cancellation_note"), "requested_at": record.get("cancellation_requested_at")},
            get_history=lambda: [{"milestone": item["label"], "timestamp": item["timestamp"]} for item in timeline if item.get("completed")][-8:],
        )
        if (get_inquiry(inquiry_id) or {}).get("cancellation_status") == "PENDING":
            save_cancellation_agent_review(inquiry_id, "COMPLETE", review)
            update_planning_workflow(inquiry_id, "CANCELLATION_REVIEW", "WAITING_FOR_PHOTOGRAPHER", "Reviewed the cancellation reason, accepted policy, fee estimate, and booking history")
    except Exception as exc:
        print(f"[ShotCraft cancellation review] Inquiry {inquiry_id}: {exc}")
        if (get_inquiry(inquiry_id) or {}).get("cancellation_status") == "PENDING":
            save_cancellation_agent_review(inquiry_id, "UNAVAILABLE", {"activity": ["Policy fee and refund were calculated from the accepted booking terms"], "summary": "Agent review is unavailable. Review the request and policy details before deciding."})
            update_planning_workflow(inquiry_id, "CANCELLATION_REVIEW", "WAITING_FOR_PHOTOGRAPHER", "Cancellation request is ready for photographer review")

@app.post("/api/inquiries/{inquiry_id}/cancellation-request")
def create_cancellation_request(inquiry_id: int, cancellation: CancellationRequest, request: Request, background_tasks: BackgroundTasks) -> dict:
    record=next((item for item in list_inquiries() if item["id"]==inquiry_id),None)
    if not record: raise HTTPException(status_code=404,detail="Inquiry not found.")
    if request.state.user["user_type"]!="client" or record.get("client_email","").lower()!=request.state.user["email"].lower():
        raise HTTPException(status_code=403,detail="Only the client who owns this shoot can request cancellation.")
    inquiry_payload=json.loads(record.get("payload") or "{}")
    booking_amount=max(0.0,float(inquiry_payload.get("budget") or 0))
    notice_hours=None
    if record.get("call_time"):
        try: notice_hours=(datetime.fromisoformat(record["call_time"])-datetime.now()).total_seconds()/3600
        except (TypeError,ValueError): pass
    fee_percent=0 if notice_hours is None or notice_hours>=48 else 25 if notice_hours>=24 else 50
    suggested_fee=round(booking_amount*fee_percent/100,2)
    suggested_refund=round(max(booking_amount-suggested_fee,0),2)
    if not request_cancellation(inquiry_id,cancellation.reason,cancellation.note,suggested_fee,suggested_refund,notice_hours):
        raise HTTPException(status_code=409,detail="This shoot cannot be cancelled or already has a pending request.")
    body=f"Cancellation request\nReason: {cancellation.reason}"
    if cancellation.note and cancellation.note.strip(): body+=f"\nClient note: {cancellation.note.strip()}"
    add_inquiry_message(inquiry_id,"client",request.state.user["name"],body)
    save_cancellation_agent_review(inquiry_id, "RUNNING")
    update_planning_workflow(inquiry_id, "CANCELLATION_REVIEW", "RUNNING", "Client requested cancellation; reviewing the booking and accepted policy")
    background_tasks.add_task(run_cancellation_agent_review, inquiry_id)
    return {"inquiry_id":inquiry_id,"status":"PENDING","suggested_fee":suggested_fee,"suggested_refund":suggested_refund,"fee_percent":fee_percent}

@app.get("/api/inquiries/{inquiry_id}/cancellation/agent-review")
def cancellation_agent_review(inquiry_id: int, request: Request) -> dict:
    record = get_inquiry(inquiry_id)
    if not record:
        raise HTTPException(status_code=404, detail="Inquiry not found.")
    photographer = json.loads(record.get("payload") or "{}").get("photographer_email") or ""
    user = request.state.user
    if user["user_type"] != "photographer" or photographer.lower() != user["email"].lower():
        raise HTTPException(status_code=403, detail="Only the assigned photographer can review this cancellation.")
    result = get_cancellation_agent_review(inquiry_id) or {"status": "UNAVAILABLE", "review": {}}
    decision = (result.get("review") or {}).get("decision") or {}
    if decision.get("message_draft"):
        # Keep the AI's wording intact; flag a bad draft for regeneration.
        draft = decision["message_draft"]
        closings = re.findall(r"(?i)\b(?:best|kind|warm)\s+regards\s*,?|\bsincerely\s*,?", draft)
        if len(closings) > 1 or re.search(r"(?i)\[[^\]]*(?:photographer|company)[^\]]*\]", draft):
            result["draft_issue"] = "This AI draft has an incomplete or duplicate sign-off. Regenerate it before sending."
        elif user["email"].lower() not in draft.lower() or (user.get("name") or "").lower() not in draft.lower():
            result["draft_issue"] = "This AI draft does not include your account name and email. Regenerate it before sending."
        elif re.search(r"(?i)\b(?:we\s+will\s+process\s+the\s+refund|the\s+refund\s+will\s+be\s+processed)\b", draft):
            result["draft_issue"] = "This AI draft claims a refund-processing action ShotCraft cannot verify. Regenerate it before sending."
        elif re.search(r"(?i)\bscheduled\s+for\s+(?:today|tomorrow)\b", draft):
            result["draft_issue"] = "This AI draft uses a relative shoot date. Regenerate it before sending."
    return result

@app.post("/api/inquiries/{inquiry_id}/cancellation/agent-review/regenerate")
def regenerate_cancellation_agent_review(inquiry_id: int, request: Request, background_tasks: BackgroundTasks) -> dict:
    record = get_inquiry(inquiry_id)
    if not record:
        raise HTTPException(status_code=404, detail="Inquiry not found.")
    assigned = json.loads(record.get("payload") or "{}").get("photographer_email") or ""
    user = request.state.user
    if user["user_type"] != "photographer" or assigned.lower() != user["email"].lower():
        raise HTTPException(status_code=403, detail="Only the assigned photographer can regenerate this draft.")
    if record.get("cancellation_status") != "PENDING":
        raise HTTPException(status_code=409, detail="There is no pending cancellation request.")
    if (get_cancellation_agent_review(inquiry_id) or {}).get("status") == "RUNNING":
        raise HTTPException(status_code=409, detail="The AI review is already running.")
    save_cancellation_agent_review(inquiry_id, "RUNNING")
    background_tasks.add_task(run_cancellation_agent_review, inquiry_id)
    return {"status": "RUNNING"}

@app.post("/api/inquiries/{inquiry_id}/cancellation/{decision}")
def review_cancellation(inquiry_id: int, decision: str, payload: CancellationDecision, request: Request) -> dict:
    if request.state.user["user_type"]!="photographer": raise HTTPException(status_code=403,detail="Only a photographer can review cancellation requests.")
    if decision not in {"approve","keep"}: raise HTTPException(status_code=400,detail="Unknown cancellation decision.")
    approved=decision=="approve"
    if not approved and not (payload.message or "").strip():
        raise HTTPException(status_code=422,detail="Add a short explanation before keeping the booking.")
    record=next((item for item in list_inquiries() if item["id"]==inquiry_id),None)
    if not record or record.get("cancellation_status")!="PENDING": raise HTTPException(status_code=409,detail="No pending cancellation request is available.")
    inquiry_payload=json.loads(record.get("payload") or "{}")
    if (inquiry_payload.get("photographer_email") or "").lower() != request.state.user["email"].lower():
        raise HTTPException(status_code=403, detail="Only the assigned photographer can decide this cancellation.")
    booking_amount=max(0.0,float(inquiry_payload.get("budget") or 0))
    if payload.fee_mode=="WAIVED": fee=0.0
    elif payload.fee_mode=="CUSTOM":
        if payload.cancellation_fee is None: raise HTTPException(status_code=422,detail="Enter a custom cancellation fee.")
        fee=float(payload.cancellation_fee)
    else: fee=float(record.get("cancellation_fee") or 0)
    if fee>booking_amount: raise HTTPException(status_code=422,detail="The cancellation fee cannot exceed the booking amount.")
    refund=round(max(booking_amount-fee,0),2)
    if not decide_cancellation(inquiry_id,approved,payload.fee_mode,fee,refund): raise HTTPException(status_code=409,detail="No pending cancellation request is available.")
    update_planning_workflow(inquiry_id, "CANCELLED" if approved else "BOOKING_RETAINED", "COMPLETE", "Photographer approved cancellation and released the calendar booking" if approved else "Photographer declined cancellation and kept the confirmed booking")
    default=(f"Your shoot cancellation has been approved. Cancellation fee: ${fee:.2f}. Estimated refund: ${refund:.2f}." if approved else "Your cancellation request was declined. Your shoot remains booked; message your photographer if you would like to discuss it.")
    add_inquiry_message(inquiry_id,"photographer",request.state.user["name"],(payload.message or '').strip() or default)
    return {"inquiry_id":inquiry_id,"status":"CANCELLED" if approved else "SCHEDULED","cancellation_fee":fee if approved else None,"estimated_refund":refund if approved else None}

@app.post("/api/inquiries/{inquiry_id}/schedule")
def schedule_project(inquiry_id: int, schedule: ScheduleRequest) -> dict[str, object]:
    if not schedule_inquiry(inquiry_id, schedule.call_time, schedule.meeting_location):
        raise HTTPException(status_code=409, detail="The client must confirm the shoot plan before it can be scheduled.")
    return {"id": inquiry_id, "status": "SCHEDULED"}

def _parse_datetime(value: str) -> datetime | None:
    try:
        if not isinstance(value, str) or not value:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None

SCHEDULE_BUFFER_MINUTES = 30

def _slots_overlap(start: datetime, end: datetime, busy: list[dict], buffer_minutes: int = SCHEDULE_BUFFER_MINUTES) -> bool:
    buffer = timedelta(minutes=max(0, buffer_minutes))
    for item in busy:
        busy_start = _parse_datetime(item.get("starts_at", ""))
        busy_end = _parse_datetime(item.get("ends_at", "")) or (busy_start + timedelta(hours=2) if busy_start else None)
        if busy_start and busy_end and start < busy_end + buffer and end > busy_start - buffer:
            return True
    return False

def _parse_window(value: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*[–-]\s*(\d{1,2}):(\d{2})\s*", value or "")
    if not match: return None
    start, end = int(match.group(1)) * 60 + int(match.group(2)), int(match.group(3)) * 60 + int(match.group(4))
    return (start, end) if 0 <= start < end <= 24 * 60 else None

def _fallback_schedule_slots(record: dict, busy: list[dict], preferred_date: datetime | None = None, duration_minutes: int | None = None, windows: list[str] | None = None) -> list[dict]:
    payload = json.loads(record.get("payload") or "{}")
    preferred = preferred_date or _parse_datetime(payload.get("shoot_date", "")) or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    duration = max(30, min(24 * 60, int(duration_minutes or payload.get("duration_minutes") or 120)))
    parsed_windows = [_parse_window(item) for item in (windows or payload.get("availability_windows") or [])]
    parsed_windows = [item for item in parsed_windows if item]
    if not parsed_windows: parsed_windows = [(9 * 60, 18 * 60)]
    location = payload.get("location") or payload.get("city") or "Location to be confirmed"
    slots: list[dict] = []
    for day_offset in range(1 if preferred_date else 14):
        day = preferred + timedelta(days=day_offset)
        for window_start, window_end in parsed_windows:
            for minute in range(window_start, window_end - duration + 1, 30):
                start = day.replace(hour=minute // 60, minute=minute % 60)
                end = start + timedelta(minutes=duration)
                if _slots_overlap(start, end, busy) or any(start < _parse_datetime(slot["ends_at"]) and end > _parse_datetime(slot["starts_at"]) for slot in slots): continue
                slots.append({"starts_at": start.isoformat(timespec="minutes"), "ends_at": end.isoformat(timespec="minutes"), "location": location, "rationale": "Fits the requested timing and avoids the photographer’s confirmed sessions."})
                if len(slots) == 3: return slots
    return slots

def _later_same_day_schedule_slots(record: dict, busy: list[dict], preferred_date: datetime | None, duration_minutes: int | None, windows: list[str] | None) -> list[dict]:
    """Offer duration-matched alternatives only after the client's last window."""
    if not preferred_date:
        return []
    payload = json.loads(record.get("payload") or "{}")
    parsed_windows = [window for value in (windows or []) if (window := _parse_window(value))]
    if not parsed_windows:
        return []
    duration = max(30, min(24 * 60, int(duration_minutes or payload.get("duration_minutes") or 120)))
    first_minute = ((max(end for _, end in parsed_windows) + 29) // 30) * 30
    location = _inquiry_schedule_location(record)
    slots = []
    for minute in range(first_minute, 24 * 60 - duration, 30):
        start = preferred_date.replace(hour=minute // 60, minute=minute % 60)
        end = start + timedelta(minutes=duration)
        if _slots_overlap(start, end, busy) or any(start < _parse_datetime(slot["ends_at"]) and end > _parse_datetime(slot["starts_at"]) for slot in slots):
            continue
        slots.append({"starts_at": start.isoformat(timespec="minutes"), "ends_at": end.isoformat(timespec="minutes"), "location": location, "rationale": "Outside your preferred window, later on the same date.", "outside_preferred_window": True})
        if len(slots) == 3:
            break
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

def _valid_suggestions(suggestions: list[dict], busy: list[dict], preferred_date: datetime | None, location: str, duration_minutes: int | None = None, windows: list[str] | None = None) -> list[dict]:
    valid = []
    expected_duration = max(30, min(24 * 60, int(duration_minutes or 120)))
    parsed_windows = [window for value in (windows or []) if (window := _parse_window(value))]
    for suggestion in suggestions:
        start, end = _parse_datetime(suggestion.get("starts_at", "")), _parse_datetime(suggestion.get("ends_at", ""))
        if not start or not end or end <= start or _slots_overlap(start, end, busy): continue
        if int((end - start).total_seconds() // 60) != expected_duration: continue
        if preferred_date and start.date() != preferred_date.date(): continue
        if parsed_windows and not any(start.hour * 60 + start.minute >= lower and end.date() == start.date() and end.hour * 60 + end.minute <= upper for lower, upper in parsed_windows): continue
        valid.append({"starts_at": start.isoformat(timespec="minutes"), "ends_at": end.isoformat(timespec="minutes"), "location": location, "rationale": "Available on your requested date and clear of the photographer’s existing shoots."})
    return valid[:3]

@app.get("/api/calendar")
def get_calendar(request: Request, client_email: str | None = None, photographer_email: str | None = None) -> dict:
    records = get_inquiries(request, client_email=client_email, photographer_email=photographer_email)
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
    # Complete selections saved by the prior hand-off flow. New selections are
    # confirmed in the selection endpoint itself; this only upgrades existing
    # PENDING_PHOTOGRAPHER records once after the workflow change.
    if request and request.get("status") == "PENDING_PHOTOGRAPHER" and request.get("selected_starts_at"):
        if confirm_client_schedule_selection(
            inquiry_id,
            request["selected_starts_at"],
            request.get("selected_ends_at") or request["selected_starts_at"],
            request.get("selected_location") or "Location to be confirmed",
        ):
            add_inquiry_message(
                inquiry_id,
                "photographer",
                "ShotCraft scheduling",
                f"Your shoot is confirmed for {_format_schedule_datetime_for_display(request['selected_starts_at'])} at {request.get('selected_location') or 'the agreed location'}. We’re looking forward to it!",
            )
            request = get_schedule_request(inquiry_id)
    # A photographer may intentionally offer alternatives outside the client's
    # preferred date or at a different venue. Those saved options are the
    # source of truth and must be shown to the client unchanged.
    if request and request.get("suggestions"):
        inquiry = Inquiry(**json.loads(record["payload"]))
        expected_duration = max(30, min(24 * 60, int(inquiry.duration_minutes or 120)))
        request["suggestions"] = [item for item in request["suggestions"] if
            (_parse_datetime(item.get("ends_at", "")) and _parse_datetime(item.get("starts_at", "")) and
             int((_parse_datetime(item["ends_at"]) - _parse_datetime(item["starts_at"])).total_seconds() // 60) == expected_duration)]
    return request or {"inquiry_id": inquiry_id, "status": None, "suggestions": []}

def _schedule_recommendation_result(inquiry_id: int, record: dict) -> dict:
    inquiry = Inquiry(**json.loads(record["payload"]))
    photographer_email = inquiry.photographer_email or ""
    busy = [item for item in scheduled_times(photographer_email) if int(item.get("inquiry_id", -1)) != inquiry_id]
    change = get_change_request(inquiry_id)
    requested_schedule = (change or {}).get("assessment", {}).get("schedule_change", {}) if change and change.get("status") in {"PENDING", "AWAITING_CLIENT"} else {}
    rescheduling = bool(requested_schedule and record.get("call_time"))
    preferred_date = _parse_datetime(requested_schedule.get("shoot_date") or inquiry.shoot_date or "")
    requested_windows = requested_schedule.get("availability_windows") or inquiry.availability_windows
    if requested_schedule:
        inquiry = inquiry.model_copy(update={"shoot_date": requested_schedule.get("shoot_date") or inquiry.shoot_date, "availability_windows": requested_windows})
    location = _inquiry_schedule_location(record)
    preferred = _fallback_schedule_slots(record, busy, preferred_date, inquiry.duration_minutes, requested_windows)
    later = [] if preferred else _later_same_day_schedule_slots(record, busy, preferred_date, inquiry.duration_minutes, requested_windows)
    safe_options = preferred or later
    if not safe_options:
        raise HTTPException(status_code=409, detail="No duration-matched times are available on the requested date after applying the 30-minute booking buffer. Ask the client for another date.")
    option_prefix = "preferred" if preferred else "later"
    available_scope = "preferred_window" if preferred else "later_same_day"
    identified = [{**slot, "option_id": f"{option_prefix}-{index + 1}"} for index, slot in enumerate(safe_options[:3])]
    activity: list[str] = []
    try:
        coordination = coordinate_schedule_slots(
            inquiry_id,
            get_context=lambda: {
                "inquiry_id": inquiry_id,
                "shoot_date": inquiry.shoot_date,
                "availability_windows": requested_windows,
                "duration_minutes": inquiry.duration_minutes or 120,
                "location": location,
                "buffer_minutes": SCHEDULE_BUFFER_MINUTES,
            },
            get_bookings=lambda: busy,
            find_slots=lambda scope: identified if scope == available_scope else [],
            **({"get_change_history": lambda: {
                "current_booking": {"starts_at": record["call_time"], "location": record.get("meeting_location")},
                "previous_rounds": [{"client_request": item.get("source_message"), "status": item.get("status"), "offered_times": [slot.get("starts_at") for slot in item.get("assessment", {}).get("agent_review", {}).get("suggestions", [])]} for item in (change.get("history") or [])][-5:],
                "client_note": change.get("source_message"),
            }} if rescheduling else {}),
        )
        by_id = {slot["option_id"]: slot for slot in identified}
        selected_ids = coordination["decision"]["selected_option_ids"]
        if not selected_ids or any(option_id not in by_id for option_id in selected_ids):
            raise ValueError("Agent selected an option outside the validated candidate set")
        identified = [by_id[option_id] for option_id in selected_ids]
        activity = coordination["activity"]
        agent_execution = coordination.get("agent_execution", "local-strands")
    except Exception as exc:
        activity = [
            f"Read shoot context for inquiry {inquiry_id}",
            f"Checked {len(busy)} confirmed booking{'s' if len(busy) != 1 else ''}",
            f"Generated {len(identified)} deterministic conflict-free option{'s' if len(identified) != 1 else ''}",
            f"Agent ranking unavailable ({type(exc).__name__}: {exc}); preserved validated order",
        ]
        agent_execution = "local-fallback"
    suggestions = [{key: value for key, value in slot.items() if key != "option_id"} for slot in identified[:3]]
    used_tools = bool(activity and activity[-1] == "Ranked safe options for photographer review")
    summary = coordination["decision"]["summary"] if used_tools else "Calendar-checked options are ready for photographer review."
    return {"suggestions": suggestions, "summary": summary, "agent_activity": activity, "agent_used_tools": used_tools, "agent_execution": agent_execution}

def _recommend_schedule_for_record(inquiry_id: int, record: dict) -> list[dict]:
    """Compatibility wrapper for callers that only need validated suggestions."""
    return _schedule_recommendation_result(inquiry_id, record)["suggestions"]

def _schedule_preview_signature(inquiry_id: int, record: dict) -> str:
    """Identify the inputs that can actually change safe scheduling options."""
    inquiry = json.loads(record.get("payload") or "{}")
    photographer_email = inquiry.get("photographer_email") or ""
    busy = [item for item in scheduled_times(photographer_email) if int(item.get("inquiry_id", -1)) != inquiry_id]
    change = get_change_request(inquiry_id)
    requested = (change or {}).get("assessment", {}).get("schedule_change", {}) if change and change.get("status") in {"PENDING", "AWAITING_CLIENT"} else {}
    inputs = {
        "shoot_date": requested.get("shoot_date") or inquiry.get("shoot_date"),
        "availability_windows": requested.get("availability_windows") or inquiry.get("availability_windows") or [],
        "duration_minutes": inquiry.get("duration_minutes") or 120,
        "location": record.get("meeting_location") or inquiry.get("location"),
        "confirmed_bookings": sorted(
            ({key: item.get(key) for key in ("inquiry_id", "starts_at", "ends_at", "location", "kind")} for item in busy),
            key=lambda item: (str(item.get("starts_at")), int(item.get("inquiry_id") or 0)),
        ),
    }
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()

@app.get("/api/inquiries/{inquiry_id}/schedule-preview")
def preview_schedule_recommendations(inquiry_id: int, request: Request) -> dict:
    record = get_inquiry(inquiry_id)
    if not record: raise HTTPException(status_code=404, detail="Inquiry not found.")
    inquiry = Inquiry(**json.loads(record["payload"]))
    user = request.state.user
    if user["user_type"] != "photographer" or (inquiry.photographer_email or "").lower() != user["email"].lower():
        raise HTTPException(status_code=403, detail="Only the assigned photographer can preview these times.")
    signature = _schedule_preview_signature(inquiry_id, record)
    existing = get_schedule_request(inquiry_id)
    if existing and existing.get("status") == "PENDING_PHOTOGRAPHER_REVIEW" and existing.get("suggestions") and existing.get("preview_signature") == signature:
        review = existing.get("agent_review") or (get_change_request(inquiry_id) or {}).get("assessment", {}).get("agent_review", {})
        return {"suggestions": existing["suggestions"], "summary": review.get("summary", ""), "agent_activity": review.get("activity", []), "agent_used_tools": review.get("agent_used_tools", False), "agent_execution": review.get("agent_execution", "unknown")}
    result = _schedule_recommendation_result(inquiry_id, record)
    save_schedule_suggestions(
        inquiry_id,
        inquiry.photographer_email or "",
        result["suggestions"],
        status="PENDING_PHOTOGRAPHER_REVIEW",
        agent_review={"summary": result["summary"], "activity": result["agent_activity"], "agent_used_tools": result["agent_used_tools"], "agent_execution": result.get("agent_execution", "unknown")},
        preview_signature=signature,
    )
    update_planning_workflow(inquiry_id, "PHOTOGRAPHER_REVIEW", "WAITING_FOR_PHOTOGRAPHER", f"Checked confirmed bookings and prepared {len(result['suggestions'])} safe time option{'s' if len(result['suggestions']) != 1 else ''}")
    return result

@app.post("/api/inquiries/{inquiry_id}/schedule-recommendations")
def create_schedule_recommendations(inquiry_id: int) -> dict:
    record = get_inquiry(inquiry_id)
    if not record: raise HTTPException(status_code=404, detail="Inquiry not found.")
    if record.get("status") not in {"CLIENT_CONFIRMED", "SCHEDULED"}:
        raise HTTPException(status_code=409, detail="Confirm the shoot plan before choosing a shoot time.")
    inquiry = Inquiry(**json.loads(record["payload"]))
    return save_schedule_suggestions(inquiry_id, inquiry.photographer_email or "", _recommend_schedule_for_record(inquiry_id, record))


@app.post("/api/inquiries/{inquiry_id}/schedule-proposals")
def propose_schedule_times(inquiry_id: int, proposal: ScheduleProposal, photographer_email: str) -> dict:
    """Save photographer-authored booking options for a client to choose from."""
    record = next((item for item in list_inquiries() if item["id"] == inquiry_id), None)
    if not record:
        raise HTTPException(status_code=404, detail="Inquiry not found.")
    inquiry = Inquiry(**json.loads(record["payload"]))
    pending_schedule_change = (get_change_request(inquiry_id) or {}).get("status") in {"PENDING", "AWAITING_CLIENT"}
    if not record.get("production_approved") or record.get("status") == "CLIENT_CHANGE_REQUESTED" or (record.get("status") == "SCHEDULED" and not pending_schedule_change):
        raise HTTPException(status_code=409, detail="Share an active shoot plan before proposing times.")
    if not inquiry.photographer_email or inquiry.photographer_email.lower() != photographer_email.lower():
        raise HTTPException(status_code=403, detail="Only the assigned photographer can propose times for this shoot.")

    busy = [item for item in scheduled_times(photographer_email) if int(item.get("inquiry_id", -1)) != inquiry_id]
    suggestions: list[dict] = []
    seen: set[tuple[str, str]] = set()
    expected_duration = max(30, min(24 * 60, int(inquiry.duration_minutes or 120)))
    for slot in proposal.suggestions:
        start, end = _parse_datetime(slot.starts_at), _parse_datetime(slot.ends_at)
        if not start or not end or end <= start:
            raise HTTPException(status_code=422, detail="Each proposed time needs a valid start and end.")
        if end - start > timedelta(days=1):
            raise HTTPException(status_code=422, detail="A proposed shoot can be up to one day long.")
        if int((end - start).total_seconds() // 60) != expected_duration:
            raise HTTPException(status_code=422, detail=f"Each proposed time must be exactly {expected_duration} minutes long.")
        key = (start.isoformat(timespec="minutes"), end.isoformat(timespec="minutes"))
        if key in seen:
            raise HTTPException(status_code=422, detail="Proposed times must be distinct.")
        if _slots_overlap(start, end, busy):
            raise HTTPException(status_code=409, detail="One of these times conflicts with a confirmed or client-selected shoot.")
        seen.add(key)
        suggestions.append({
            "starts_at": key[0],
            "ends_at": key[1],
            "location": slot.location,
            "rationale": slot.rationale or "Proposed by your photographer.",
        })
    saved = save_schedule_suggestions(inquiry_id, photographer_email, suggestions)
    option_summary = "; ".join(
        f"{_format_schedule_datetime_for_display(item['starts_at'])} – "
        f"{datetime.fromisoformat(item['ends_at']).strftime('%-I:%M %p')}"
        for item in suggestions
    )
    add_inquiry_message(
        inquiry_id,
        "photographer",
        "ShotCraft scheduling",
        f"Your photographer proposed revised shoot times: {option_summary}. Open your shoot to review and choose the option that works best for you.",
    )
    update_planning_workflow(inquiry_id, "CLIENT_REVIEW", "WAITING_FOR_CLIENT", f"Photographer shared {len(suggestions)} time option{'s' if len(suggestions) != 1 else ''} with the client")
    return saved

@app.post("/api/inquiries/{inquiry_id}/schedule-selection")
def select_schedule_time(inquiry_id: int, selection: ScheduleSelection, request: Request) -> dict:
    record = get_inquiry(inquiry_id)
    if not record:
        raise HTTPException(status_code=404, detail="Inquiry not found.")
    if request.state.user["user_type"] != "client" or record.get("client_email", "").lower() != request.state.user["email"].lower():
        raise HTTPException(status_code=403, detail="Only the client who owns this shoot can choose a revised time.")
    request = get_schedule_request(inquiry_id)
    if not request: raise HTTPException(status_code=409, detail="Get recommended times before making a selection.")
    matches = any(item["starts_at"] == selection.starts_at and item["ends_at"] == selection.ends_at for item in request["suggestions"])
    if not matches: raise HTTPException(status_code=422, detail="Please select one of the recommended times.")
    busy = [item for item in scheduled_times(request["photographer_email"]) if int(item.get("inquiry_id", -1)) != inquiry_id]
    start, end = _parse_datetime(selection.starts_at), _parse_datetime(selection.ends_at)
    if not start or not end or _slots_overlap(start, end, busy):
        raise HTTPException(status_code=409, detail="This time is no longer available after the required 30-minute booking buffer. Send updated preferences to continue.")
    if not confirm_client_schedule_selection(inquiry_id, selection.starts_at, selection.ends_at, selection.location):
        raise HTTPException(status_code=409, detail="This time is no longer available for selection.")
    is_time_change = (get_change_request(inquiry_id) or {}).get("status") in {"PENDING", "AWAITING_CLIENT"}
    update_planning_workflow(inquiry_id, "CONFIRMED", "COMPLETE", "Revalidated availability and updated the booking to the client's selected time" if is_time_change else "Revalidated availability and confirmed the client's selected time")
    if is_time_change:
        resolve_change_request(inquiry_id)
    add_inquiry_message(
        inquiry_id,
        "photographer",
        "ShotCraft scheduling",
        f"Your shoot is confirmed for {_format_schedule_datetime_for_display(selection.starts_at)} at {selection.location}. We’re looking forward to it!",
    )
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


@app.get("/api/moodboards/jobs/{job_id}")
def moodboard_job_status(job_id: str):
    with _moodboard_jobs_lock:
        job = _moodboard_jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Moodboard job not found.")
        return {
            "status": job["status"],
            "moodboard": job["moodboard"],
            "tiles": job["tiles"],
            "error": job["error"],
        }


@app.post("/api/inquiries/{inquiry_id}/moodboard/retry")
def retry_moodboard(inquiry_id: int) -> dict:
    record = get_inquiry(inquiry_id)
    if not record:
        raise HTTPException(status_code=404, detail="Inquiry not found.")
    saved = json.loads(record.get("moodboard") or "{}")
    if saved.get("status") == "complete":
        raise HTTPException(status_code=409, detail="This moodboard is already complete.")
    with _moodboard_jobs_lock:
        active = saved.get("job_id") in _moodboard_jobs and _moodboard_jobs[saved["job_id"]]["status"] == "generating"
    if active:
        raise HTTPException(status_code=409, detail="Moodboard images are still generating.")
    plan = saved.get("moodboard")
    if plan and plan.get("tiles"):
        moodboard = Moodboard.model_validate(plan)
    else:
        # Automatic follow-up processing writes a loading placeholder before
        # the text agent creates its plan. Recover from the saved brief if that
        # step was interrupted or failed.
        brief_data = json.loads(record.get("creative_brief") or "{}")
        if not brief_data:
            raise HTTPException(status_code=409, detail="The creative brief is not ready yet. Try again shortly.")
        try:
            moodboard = create_moodboard(MoodboardRequest(
                brief=CreativeBrief.model_validate(brief_data), inquiry_id=inquiry_id,
            ))
        except Exception as exc:
            print(f"[ShotCraft moodboard] Could not rebuild plan for inquiry {inquiry_id}: {exc}")
            raise HTTPException(status_code=502, detail="Could not rebuild the moodboard plan. Check the server logs and try again.") from exc
    update_planning_workflow(inquiry_id, "CREATING_MOODBOARD", "RUNNING", "Resumed moodboard generation from the saved creative brief")
    return {"job_id": _start_moodboard_job(inquiry_id, moodboard)}


@app.post("/api/inquiries/{inquiry_id}/moodboard/render", response_model=GeneratedMoodboard)
def render_saved_moodboard(inquiry_id: int) -> GeneratedMoodboard:
    """Render image references only when the photographer explicitly requests them."""
    record = get_inquiry(inquiry_id)
    if not record:
        raise HTTPException(status_code=404, detail="Inquiry not found.")
    saved = json.loads(record.get("moodboard") or "{}")
    plan = saved.get("moodboard") or saved
    if not plan or not plan.get("tiles"):
        raise HTTPException(status_code=409, detail="Create a moodboard plan before rendering images.")
    try:
        moodboard = Moodboard.model_validate(plan)
        generated = generate_moodboard_images(moodboard)
    except Exception as exc:
        print(f"[ShotCraft moodboard] Render failed: {exc}")
        raise HTTPException(
            status_code=502,
            detail="The image provider could not render this moodboard. Check the server logs and try again.",
        ) from exc
    save_moodboard(inquiry_id, {"moodboard": moodboard.model_dump(), "generated": generated.model_dump()})
    return generated


@app.post("/api/moodboards/create-and-generate")
def create_and_generate_moodboard_endpoint(request: MoodboardRequest):
    """Create the AI moodboard plan and render its tiles in one demo-friendly call."""
    # A moodboard is a visual planning aid, so optional questions suggested by the
    # brief agent must not deadlock the workflow after intake has already marked an
    # inquiry ready. Deliverables are the one hard prerequisite because they affect
    # the agreed scope and downstream shoot plan.
    if not request.brief.deliverables:
        raise HTTPException(
            status_code=409,
            detail="Add the requested number of final photos before generating a moodboard.",
        )
    try:
        moodboard = create_moodboard(request)
        inquiry_id = getattr(request, "inquiry_id", None)
        job_id = _start_moodboard_job(getattr(request, "inquiry_id", None), moodboard)
    except Exception as exc:
        root = exc
        while getattr(root, "__cause__", None):
            root = root.__cause__
        # Keep the browser response safe, but preserve the provider's actionable
        # status in the server log for deployment troubleshooting.
        print(f"[ShotCraft moodboard] Generation failed: {exc}")
        if root is not exc:
            print(f"[ShotCraft moodboard] Provider error: {type(root).__name__}: {root}")
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
    inquiry_id = getattr(request, "inquiry_id", None)
    if inquiry_id:
        record_event(inquiry_id, "BRIEF_APPROVED")
    return {"job_id": job_id, "moodboard": moodboard.model_dump()}

def _fallback_production_pack(inquiry: Inquiry, moodboard: dict | None = None) -> ProductionPack:
    """Keep the workflow moving when the planning model is unavailable or malformed."""
    message = inquiry.message or ""
    city = next((name for name in ("Seattle", "New Delhi", "Delhi", "Bangalore") if name.lower() in message.lower()), None)
    location = city or "Location to be confirmed with the client"
    deliverables = f"{inquiry.deliverable_count} final edited images" if inquiry.deliverable_count else "Final edited images to be confirmed"
    wardrobe = inquiry.wardrobe_details or "Client wardrobe to be confirmed"
    title = f"{inquiry.client_name} · Shoot plan"
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
        print(f"[ShotCraft shoot plan] Generation failed: {exc}")
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
        # A manually regenerated pack follows the same visible journey: it is a
        # draft only once it includes rendered moodboard references.
        save_production_pack(target_inquiry_id, pack.model_dump(), draft=True)
        if isinstance(moodboard, dict) and (moodboard.get("generated") or {}).get("tiles"):
            record_event(target_inquiry_id, "DRAFT_PLAN_READY")
    return pack
