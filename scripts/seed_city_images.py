"""Create a small, attributed Pexels image catalog for project-card backgrounds.

Run manually when the curated city catalog needs refreshing:
    python scripts/seed_city_images.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "static" / "city-images.json"
TOP_CITIES = [
    ("new-york", "New York, NY", ["new york", "nyc", "manhattan"], "New York City skyline"),
    ("los-angeles", "Los Angeles, CA", ["los angeles", "la"], "Los Angeles city skyline"),
    ("chicago", "Chicago, IL", ["chicago"], "Chicago skyline waterfront"),
    ("houston", "Houston, TX", ["houston"], "Houston city skyline"),
    ("phoenix", "Phoenix, AZ", ["phoenix"], "Phoenix Arizona city skyline"),
    ("philadelphia", "Philadelphia, PA", ["philadelphia", "philly"], "Philadelphia skyline"),
    ("san-antonio", "San Antonio, TX", ["san antonio"], "San Antonio Texas riverwalk"),
    ("san-diego", "San Diego, CA", ["san diego"], "San Diego California waterfront skyline"),
    ("dallas", "Dallas, TX", ["dallas"], "Dallas Texas skyline"),
    ("jacksonville", "Jacksonville, FL", ["jacksonville"], "Jacksonville Florida skyline"),
    ("austin", "Austin, TX", ["austin"], "Austin Texas skyline"),
    ("fort-worth", "Fort Worth, TX", ["fort worth"], "Fort Worth Texas skyline"),
    ("san-jose", "San Jose, CA", ["san jose"], "San Jose California city"),
    ("columbus", "Columbus, OH", ["columbus"], "Columbus Ohio skyline"),
    ("charlotte", "Charlotte, NC", ["charlotte"], "Charlotte North Carolina skyline"),
    ("indianapolis", "Indianapolis, IN", ["indianapolis"], "Indianapolis skyline"),
    ("san-francisco", "San Francisco, CA", ["san francisco", "sf"], "San Francisco skyline waterfront"),
    ("seattle", "Seattle, WA", ["seattle"], "Seattle waterfront skyline"),
    ("denver", "Denver, CO", ["denver"], "Denver Colorado skyline"),
    ("washington-dc", "Washington, DC", ["washington dc", "washington, dc", "district of columbia"], "Washington DC monuments skyline"),
]


def search_photos(api_key: str, query: str) -> list[dict]:
    params = urlencode({"query": query, "orientation": "landscape", "per_page": 3})
    request = Request(
        f"https://api.pexels.com/v1/search?{params}",
        headers={"Authorization": api_key, "User-Agent": "ShotCraft city catalog seed"},
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response).get("photos", [])


def main() -> None:
    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        raise SystemExit("PEXELS_API_KEY is missing from .env")

    catalog: dict[str, dict] = {}
    for key, label, aliases, query in TOP_CITIES:
        photos = search_photos(api_key, query)
        if len(photos) < 2:
            print(f"Skipping {label}: Pexels returned fewer than two landscape photos.")
            continue
        catalog[key] = {
            "label": label,
            "aliases": aliases,
            "gallery": [photo["src"]["landscape"] for photo in photos],
            "attribution": [
                {
                    "photographer": photo["photographer"],
                    "photographer_url": photo["photographer_url"],
                    "photo_url": photo["url"],
                    "provider": "Pexels",
                }
                for photo in photos
            ],
        }
        print(f"Added {label}.")

    OUTPUT.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(catalog)} cities to {OUTPUT.relative_to(ROOT)}.")


if __name__ == "__main__":
    main()
