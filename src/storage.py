import boto3
from botocore.config import Config as BotoConfig
from src.config import Config

def _client(endpoint: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=Config.S3_REGION,
        aws_access_key_id=Config.S3_ACCESS_KEY,
        aws_secret_access_key=Config.S3_SECRET_KEY,
        config=BotoConfig(s3={"addressing_style":"path"})
    )

s3_internal = _client(Config.S3_ENDPOINT)
s3_public = _client(Config.S3_PUBLIC_ENDPOINT)