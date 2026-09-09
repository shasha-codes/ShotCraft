"""Verify the local AWS identity and make one minimal ShotCraft Bedrock call."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

from strands import Agent
from strands.models.openai import OpenAIModel


MODEL_ID = os.getenv("SHOTCRAFT_INTAKE_MODEL", os.getenv("SHOTCRAFT_MODEL", "openai.gpt-oss-120b-1:0"))
if MODEL_ID == "openai.gpt-oss-120b":
    MODEL_ID = "openai.gpt-oss-120b-1:0"
REGION = os.getenv("AWS_REGION", "us-west-2")
ENDPOINT = os.getenv("SHOTCRAFT_BEDROCK_ENDPOINT", f"https://bedrock-mantle.{REGION}.api.aws/v1")


def main() -> int:
    try:
        api_key = os.getenv("AWS_BEARER_TOKEN_BEDROCK")
        if not api_key:
            print("AWS_BEARER_TOKEN_BEDROCK is not configured; this check targets Strands + Mantle.", file=sys.stderr)
            return 1
        print("Authentication: Strands Agent + Amazon Bedrock Mantle API")
        print(f"Region: {REGION}")
        print(f"Model: {MODEL_ID}")

        mantle_model = MODEL_ID.removesuffix("-1:0")
        agent = Agent(
            model=OpenAIModel(
                model_id=mantle_model,
                client_args={"api_key": api_key, "base_url": ENDPOINT},
            ),
            callback_handler=None,
        )
        text = str(agent("Reply with exactly: Bedrock connected."))
        print(f"Bedrock response: {text}")
        return 0
    except Exception as error:
        print(f"Strands + Mantle request failed: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
