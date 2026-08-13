import os
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_PROFILE = os.getenv("AWS_PROFILE", "default")
S3_BUCKET = os.getenv("S3_BUCKET")
MODEL_ID = os.getenv("MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")
