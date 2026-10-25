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

bucket = env["S3_BUCKET"]
s3.put_object(Bucket=bucket, Key="hello.txt", Body=b"hi")
print(s3.get_object(Bucket=bucket, Key="hello.txt")["Body"].read())
s3.delete_object(Bucket=bucket, Key="hello.txt")
print([o["Key"] for o in s3.list_objects_v2(Bucket=bucket).get("Contents", [])])