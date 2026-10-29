import boto3
from botocore.config import Config
from dotenv import dotenv_values

env = dotenv_values(".env")

s3 = boto3.client(
    "s3",
    endpoint_url=env["S3_PUBLIC_ENDPOINT"],
    region_name=env["S3_REGION"],
    aws_access_key_id=env["S3_ACCESS_KEY"],
    aws_secret_access_key=env["S3_SECRET_KEY"],
    config=Config(s3={"addressing_style": "path"}),
)

##

s3.put_bucket_cors(
    Bucket=env["S3_BUCKET"],
    CORSConfiguration={
        "CORSRules": [
            {
                "AllowedOrigins": ["http://localhost:8000", "http://paste.localhost"],
                "AllowedMethods": ["GET", "HEAD", "POST"],
                "AllowedHeaders": ["*"],
                "ExposeHeaders": ["ETag"],
                "MaxAgeSeconds": 3600,
            }
        ]
    },
)

print(s3.get_bucket_cors(Bucket=env["S3_BUCKET"])["CORSRules"])
