import os

import boto3
from dotenv import load_dotenv
from strands.models.openai import OpenAIModel

load_dotenv(override=True)

# On Streamlit Cloud, secrets are available via streamlit.secrets — sync to os.environ
try:
    import streamlit as st
    for _k, _v in st.secrets.items():
        if isinstance(_v, str):
            os.environ.setdefault(_k, _v)
except Exception:
    pass

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_PROFILE = os.getenv("AWS_PROFILE", "default")
MODEL_ID = os.getenv("MODEL_ID", "deepseek.v3.2")
FALLBACK_MODEL_IDS = [
    os.getenv("FALLBACK_MODEL_ID_1", "amazon.nova-lite-v1:0"),
    os.getenv("FALLBACK_MODEL_ID_2", "xai.grok-4.3"),
]

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


def create_mantle_model(temperature: float = 0.1, model_id: str | None = None) -> OpenAIModel:
    """Single factory for all agents — change Mantle config in one place.

    Pass model_id to override the default (used by fallback logic in runner.py).
    """
    return OpenAIModel(
        client_args={
            "base_url": MANTLE_BASE_URL,
            "api_key": MANTLE_API_KEY,
            "default_headers": {"openai-project": "default"},
            "timeout": 110,  # slightly under _AGENT_TIMEOUT_SECONDS so HTTP fails before thread deadline
        },
        model_id=model_id or MODEL_ID,
        params={"temperature": temperature},
    )
