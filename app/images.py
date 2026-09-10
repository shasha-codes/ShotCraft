"""OpenAI image generation helpers for ShotCraft moodboards."""

import base64
import os
import re
import uuid
from pathlib import Path

from openai import OpenAI

from .models import Moodboard, GeneratedMoodboard, GeneratedTile


MODEL_ID = os.getenv("SHOTCRAFT_IMAGE_MODEL", "gpt-image-1.5")
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "static" / "generated"


def _was_moderation_blocked(exc: Exception) -> bool:
    """Return true for image-provider safety rejections without coupling to an SDK version."""
    message = str(exc).lower()
    return "moderation_blocked" in message or "safety system" in message


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


def generate_moodboard_images(moodboard: Moodboard) -> GeneratedMoodboard:
    """Render low-cost square moodboard tiles with OpenAI image generation."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = OpenAI()
    generated: list[GeneratedTile] = []
    all_text = " ".join([moodboard.title, moodboard.creative_direction] + [t.visual_prompt for t in moodboard.tiles]).lower()
    if re.search(r"\b(no person|product|location only)\b", all_text):
        subject = "no person: an environment or product only"
    elif re.search(r"\b(group|multiple people|two people|three people)\b", all_text):
        subject = "the exact client-requested group; do not add or remove people"
    elif re.search(r"\b(male|man|men|boy|masculine)\b", all_text):
        subject = "exactly one adult male subject"
    elif re.search(r"\b(female|woman|women|girl|feminine)\b", all_text):
        subject = "exactly one adult female subject"
    elif re.search(r"\b(non-binary|nonbinary)\b", all_text):
        subject = "exactly one adult non-binary subject"
    else:
        subject = "the exact client-requested subject, with no gender or identity changes"

    for tile in moodboard.tiles:
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
        last_error: Exception | None = None
        result = None
        prompts = [prompt]
        for attempt in range(3):
            attempt_prompt = prompts[-1]
            try:
                result = client.images.generate(model=MODEL_ID, prompt=attempt_prompt, size="1024x1024", quality="low", output_format="jpeg")
                if not result.data or not result.data[0].b64_json:
                    raise RuntimeError("The image provider returned no image data.")
                break
            except Exception as exc:
                last_error = exc
                if _was_moderation_blocked(exc):
                    # Retrying an identical moderated prompt cannot improve the result.
                    # Use a deliberately conservative prompt for subsequent attempts.
                    safe_prompt = _safe_editorial_prompt(role, subject, tile.visual_prompt)
                    prompts.append(safe_prompt + f" Safe variation {attempt + 1}.")
                else:
                    prompts.append(attempt_prompt)
        if result is None or not result.data or not result.data[0].b64_json:
            raise RuntimeError(f"Could not generate the '{tile.title}' reference after three attempts.") from last_error
        image_data = base64.b64decode(result.data[0].b64_json)
        filename = f"{uuid.uuid4().hex}.jpg"
        (OUTPUT_DIR / filename).write_bytes(image_data)
        generated.append(GeneratedTile(title=tile.title, image_url=f"/static/generated/{filename}"))
    return GeneratedMoodboard(title=moodboard.title, model_id=MODEL_ID, tiles=generated)
