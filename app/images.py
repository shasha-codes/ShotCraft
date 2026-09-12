"""OpenAI image generation helpers for ShotCraft moodboards."""

import base64
import os
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

from .models import Moodboard, GeneratedMoodboard, GeneratedTile

load_dotenv()

MODEL_ID = os.getenv("SHOTCRAFT_IMAGE_MODEL", "gpt-image-2.5-flare")
MAX_CONCURRENT_RENDERS = max(1, min(int(os.getenv("SHOTCRAFT_IMAGE_CONCURRENCY", "2")), 4))
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "static" / "generated"


def _was_moderation_blocked(exc: Exception) -> bool:
    """Return true for image-provider safety rejections without coupling to an SDK version."""
    message = str(exc).lower()
    return "moderation_blocked" in message or "safety system" in message


def _is_transient_provider_error(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    message = str(exc).lower()
    return status in {408, 409, 429} or bool(status and status >= 500) or any(
        marker in message for marker in ("timeout", "timed out", "rate limit", "connection error", "temporarily unavailable")
    )


def public_image_error(exc: Exception) -> str:
    """Return an actionable provider error without exposing credentials or request data."""
    root = exc.__cause__ or exc
    message = str(root).lower()
    if "credential" in message or "api_key" in message:
        return "Image provider credentials are unavailable. Restart the app after checking OPENAI_API_KEY."
    if getattr(root, "status_code", None) == 429 or "rate limit" in message:
        return "The image provider is temporarily rate-limited. Wait a moment and retry."
    if _was_moderation_blocked(root):
        return "The image provider could not safely render this direction. Adjust the creative brief and retry."
    if _is_transient_provider_error(root):
        return "The image provider was temporarily unavailable. Retry the moodboard."
    return "The image provider could not complete this moodboard. Retry or check the server logs."


def _safe_editorial_prompt(role: str, subject: str, tile_prompt: str) -> str:
    """Build a conservative retry prompt after an image output is moderated."""
    return (
        f"{role} {subject}. Create a tasteful commercial photography reference featuring adults only. "
        "The subject must be fully clothed in an opaque, modest, non-revealing outfit throughout. "
        "Use a neutral professional fashion pose and calm expression; no sensual posing, lingerie, "
        "swimwear, nudity, transparent fabric, cleavage, fetish styling, or sexualized framing. "
        "Keep the requested location, lighting, color palette, person count, and general wardrobe color. "
        "Natural realistic photography with no text, logo, watermark, collage, or duplicate people. "
        f"Creative direction: {tile_prompt}"
    )


def _moodboard_subject(moodboard: Moodboard) -> str:
    all_text = " ".join([moodboard.title, moodboard.creative_direction] + [t.visual_prompt for t in moodboard.tiles]).lower()
    if re.search(r"\b(no person|product|location only)\b", all_text):
        return "no person: an environment or product only"
    elif re.search(r"\b(group|multiple people|two people|three people)\b", all_text):
        return "the exact client-requested group; do not add or remove people"
    elif re.search(r"\b(male|man|men|boy|masculine)\b", all_text):
        return "exactly one adult male subject"
    elif re.search(r"\b(female|woman|women|girl|feminine)\b", all_text):
        return "exactly one adult female subject"
    elif re.search(r"\b(non-binary|nonbinary)\b", all_text):
        return "exactly one adult non-binary subject"
    return "the exact client-requested subject, with no gender or identity changes"

def _render_tile(tile, subject: str) -> GeneratedTile:
    title = tile.title.lower()
    if "location" in title or "background" in title:
        role = "Environmental location photography only: show the requested setting with no people, models, mannequins, or portraits. Make Seattle unmistakable with recognizable local architecture or skyline cues."
    elif "lighting" in title:
        role = "Show exactly one model in a head-and-shoulders portrait; demonstrate the requested light on the face. Keep the entire head, hair, and both shoulders inside the frame."
    elif "wardrobe" in title or "pose" in title:
        role = "Show exactly one model in a true head-to-toe full-body fashion pose wearing only the specified wardrobe. Pull the camera back far enough to include the entire head, hair, both arms, legs, and both feet with comfortable margins. Do not crop any part of the subject. Do not add coats, jackets, hats, bags, jewelry, or accessories unless explicitly requested."
    else:
        role = "Show exactly one model in a strong editorial hero portrait wearing the specified wardrobe. Keep the entire head and hair inside the frame with comfortable space above it."
    prompt = (
            f"{role} HARD SUBJECT LOCK: {subject}. Preserve the same presentation, person count, age, hair, "
            "skin tone, exact wardrobe, city, and indoor/outdoor setting. Never add an unrequested outer layer. Natural believable photography, "
            "realistic fabric and skin texture, intentional composition, cinematic color grade, subtle film grain. "
            "No text, logos, watermark, collage, split screen, duplicate people, groups, CGI, illustration, "
            "cartoon, or alternate clothing. Client brief and tile direction: " + tile.visual_prompt
            + " FINAL HARD CONSTRAINT: use only the client-specified clothing; no jacket, coat, bag, jewelry, hat, or added accessory. Keep generous headroom above the hair and never crop the head."
    )
    # A provider stall must eventually surface as a failed, retryable job.
    client = OpenAI(timeout=120.0, max_retries=0)
    last_error: Exception | None = None
    attempt_prompt = prompt
    safety_retry_used = False
    transient_retries = 0
    while True:
        try:
            result = client.images.generate(model=MODEL_ID, prompt=attempt_prompt, size="1024x1024", quality="low", output_format="jpeg")
            if not result.data or not result.data[0].b64_json:
                raise RuntimeError("The image provider returned no image data.")
            image_data = base64.b64decode(result.data[0].b64_json)
            filename = f"{uuid.uuid4().hex}.jpg"
            (OUTPUT_DIR / filename).write_bytes(image_data)
            return GeneratedTile(title=tile.title, image_url=f"/static/generated/{filename}")
        except Exception as exc:
            last_error = exc
            if _was_moderation_blocked(exc) and not safety_retry_used:
                safety_retry_used = True
                attempt_prompt = _safe_editorial_prompt(role, subject, tile.visual_prompt)
                continue
            if _is_transient_provider_error(exc) and transient_retries < 2:
                transient_retries += 1
                time.sleep(1.5 * transient_retries)
                continue
            break
    raise RuntimeError(f"Could not generate the '{tile.title}' reference.") from last_error


def generate_moodboard_images(moodboard: Moodboard, on_tile=None) -> GeneratedMoodboard:
    """Render moodboard tiles concurrently, retaining their planned display order."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tiles = moodboard.tiles
    if not tiles:
        return GeneratedMoodboard(title=moodboard.title, model_id=MODEL_ID, tiles=[])
    subject = _moodboard_subject(moodboard)
    rendered: dict[int, GeneratedTile] = {}
    with ThreadPoolExecutor(max_workers=min(MAX_CONCURRENT_RENDERS, len(tiles))) as pool:
        futures = {pool.submit(_render_tile, tile, subject): index for index, tile in enumerate(tiles)}
        for future in as_completed(futures):
            index = futures[future]
            rendered[index] = future.result()
            if on_tile:
                on_tile(index, rendered[index])
    return GeneratedMoodboard(title=moodboard.title, model_id=MODEL_ID, tiles=[rendered[index] for index in range(len(tiles))])
