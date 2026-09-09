"""Generate concise AI concept names for legacy ShotCraft inquiries.

Only records without an existing ``analysis.concept_name`` are updated. Their
workflow status and all existing analysis fields are retained.
"""

import json

from app.agent import analyze_inquiry
from app.models import Inquiry
from app.storage import list_inquiries, update_analysis


def main() -> None:
    updated = 0
    skipped = 0
    for record in list_inquiries():
        analysis = json.loads(record.get("analysis") or "{}")
        if analysis.get("concept_name"):
            skipped += 1
            continue

        try:
            inquiry = Inquiry(**json.loads(record["payload"]))
            concept_name = analyze_inquiry(inquiry).concept_name.strip()
            if not concept_name:
                raise ValueError("The agent returned an empty concept name.")
            analysis["concept_name"] = concept_name
            update_analysis(int(record["id"]), record["status"], analysis)
            updated += 1
        except Exception as error:
            print(f"Skipped inquiry {record['id']}: {error}")

    print(f"Concept-name backfill complete: {updated} updated, {skipped} already named.")


if __name__ == "__main__":
    main()
