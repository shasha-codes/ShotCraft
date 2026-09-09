"""Minimal ShotCraft Strands setup check."""

import os
from dotenv import load_dotenv
from strands import Agent
from strands.models.openai import OpenAIModel

load_dotenv()


def main() -> None:
    api_key = os.getenv("AWS_BEARER_TOKEN_BEDROCK")
    if not api_key:
        raise RuntimeError("AWS_BEARER_TOKEN_BEDROCK is required for the Mantle smoke test")
    region = os.getenv("AWS_REGION", "us-west-2")
    endpoint = os.getenv("SHOTCRAFT_BEDROCK_ENDPOINT", f"https://bedrock-mantle.{region}.api.aws/v1")
    agent = Agent(
        model=OpenAIModel(
            model_id=os.getenv("SHOTCRAFT_MODEL", "openai.gpt-oss-120b").removesuffix("-1:0"),
            client_args={"api_key": api_key, "base_url": endpoint},
        ),
        callback_handler=None,
    )
    response = agent("In one sentence, describe a soft editorial portrait shoot.")
    print(response)


if __name__ == "__main__":
    main()
