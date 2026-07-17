"""
civictrack-get-upload-url
Triggered by: API Gateway GET /upload-url
Env vars required:
  UPLOAD_BUCKET  - name of the S3 bucket photos get uploaded to
"""
import json
import os
import uuid
import boto3

s3 = boto3.client(
    "s3",
    region_name="ap-south-1"
)
BUCKET = os.environ['UPLOAD_BUCKET']

ALLOWED_EXTENSIONS = {
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
}

CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'GET,OPTIONS',
    'Content-Type': 'application/json',
}


def lambda_handler(event, context):
    try:
        query = event.get('queryStringParameters') or {}
        ext = (query.get('ext') or 'jpg').lower().lstrip('.')
        if ext not in ALLOWED_EXTENSIONS:
            ext = 'jpg'
        content_type = ALLOWED_EXTENSIONS[ext]

        key = f"uploads/{uuid.uuid4()}.{ext}"

        upload_url = s3.generate_presigned_url(
            ClientMethod='put_object',
            Params={
                'Bucket': BUCKET,
                'Key': key,
                'ContentType': content_type,
            },
            ExpiresIn=300,  # 5 minutes to actually perform the upload
        )

        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': json.dumps({
                'uploadUrl': upload_url,
                'key': key,
                'contentType': content_type,
            }),
        }

    except Exception as exc:  # noqa: BLE001
        return {
            'statusCode': 500,
            'headers': CORS_HEADERS,
            'body': json.dumps({'error': str(exc)}),
        }
