import os

import boto3
from dotenv import load_dotenv
from strands.models.openai import OpenAIModel

load_dotenv(override=True)

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_PROFILE = os.getenv("AWS_PROFILE", "default")
MODEL_ID = os.getenv("MODEL_ID", "deepseek.v3.2")

MANTLE_API_KEY = os.getenv("MANTLE_API_KEY")
MANTLE_BASE_URL = f"https://bedrock-mantle.{AWS_REGION}.api.aws/v1"


def get_boto_session() -> boto3.Session:
    if os.getenv("AWS_ACCESS_KEY_ID"):
        return boto3.Session(
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=AWS_REGION,
        )
    return boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)


def create_mantle_model(temperature: float = 0.1) -> OpenAIModel:
    """Single factory for all agents — change Mantle config in one place."""
    return OpenAIModel(
        client_args={
            "base_url": MANTLE_BASE_URL,
            "api_key": MANTLE_API_KEY,
            "default_headers": {"openai-project": "default"},
        },
        model_id=MODEL_ID,
        params={"temperature": temperature},
    )
