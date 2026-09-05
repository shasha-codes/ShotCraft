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


def generate_moodboard_images(moodboard: Moodboard) -> GeneratedMoodboard:
    """Render low-cost square moodboard tiles with OpenAI image generation."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = OpenAI()
    generated: list[GeneratedTile] = []
    all_text = " ".join([moodboard.title, moodboard.creative_direction] + [t.visual_prompt for t in moodboard.tiles]).lower()
    subject = "adult male subject" if re.search(r"\b(male|man|men|boy|masculine)\b", all_text) else "adult female subject" if re.search(r"\b(female|woman|women|girl|feminine)\b", all_text) else "the same adult subject"

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
            f"{role} The subject identity is locked as {subject}. Preserve the same gender, age, hair, "
            "skin tone, exact wardrobe, city, and indoor/outdoor setting. Never add an unrequested outer layer. Natural believable photography, "
            "realistic fabric and skin texture, intentional composition, cinematic color grade, subtle film grain. "
            "No text, logos, watermark, collage, split screen, duplicate people, groups, CGI, illustration, "
            "cartoon, or alternate clothing. Client brief and tile direction: " + tile.visual_prompt
            + " FINAL HARD CONSTRAINT: use only the client-specified clothing; no jacket, coat, bag, jewelry, hat, or added accessory. Keep generous headroom above the hair and never crop the head."
        )
        result = client.images.generate(model=MODEL_ID, prompt=prompt, size="1024x1024", quality="low", output_format="jpeg")
        image_data = base64.b64decode(result.data[0].b64_json)
        filename = f"{uuid.uuid4().hex}.jpg"
        (OUTPUT_DIR / filename).write_bytes(image_data)
        generated.append(GeneratedTile(title=tile.title, image_url=f"/static/generated/{filename}"))
    return GeneratedMoodboard(title=moodboard.title, model_id=MODEL_ID, tiles=generated)
