import os

import boto3
from strands.models.openai import OpenAIModel


def load_model() -> OpenAIModel:
    """Load ShotCraft's Mantle-compatible Bedrock model using a bearer API key."""
    api_key = os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
    secret_arn = os.environ.get("SHOTCRAFT_BEDROCK_SECRET_ARN")
    if not api_key and secret_arn:
        response = boto3.client("secretsmanager").get_secret_value(SecretId=secret_arn)
        api_key = response.get("SecretString")
    if not api_key:
        raise RuntimeError("A Bedrock API key is required through AWS_BEARER_TOKEN_BEDROCK or SHOTCRAFT_BEDROCK_SECRET_ARN")
    endpoint = os.environ.get(
        "SHOTCRAFT_BEDROCK_ENDPOINT",
        "https://bedrock-mantle.us-west-2.api.aws/v1",
    )
    model_id = os.environ.get(
        "SHOTCRAFT_OPENAI_MODEL",
        os.environ.get("SHOTCRAFT_MODEL", "openai.gpt-oss-120b"),
    ).removesuffix("-1:0")
    return OpenAIModel(
        model_id=model_id,
        client_args={"api_key": api_key, "base_url": endpoint},
    )
