import os

import boto3
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_PROFILE = os.getenv("AWS_PROFILE", "default")
S3_BUCKET = os.getenv("S3_BUCKET")
MODEL_ID = os.getenv("MODEL_ID", "deepseek.v3.2")

MANTLE_API_KEY = os.getenv("MANTLE_API_KEY")
MANTLE_BASE_URL = f"https://bedrock-mantle.{AWS_REGION}.api.aws/v1"

BOTO_SESSION = boto3.Session(
    profile_name=AWS_PROFILE,
    region_name=AWS_REGION,
)
