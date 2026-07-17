"""
civictrack-count-aggregator
Triggered by: EventBridge schedule, rate(5 minutes)
Requires the pymysql Lambda layer.

Env vars required:
  DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
  OUTPUT_BUCKET   - bucket to write counts.json into
  OUTPUT_KEY      - defaults to public/counts.json
"""
import json
import os
from datetime import datetime, timezone

import boto3
import pymysql

s3 = boto3.client(
    "s3",
    region_name="ap-south-1"
)

DB_HOST = os.environ['DB_HOST']
DB_USER = os.environ['DB_USER']
DB_PASSWORD = os.environ['DB_PASSWORD']
DB_NAME = os.environ['DB_NAME']
OUTPUT_BUCKET = os.environ['OUTPUT_BUCKET']
OUTPUT_KEY = os.environ.get('OUTPUT_KEY', 'public/counts.json')

DEFAULT_CATEGORIES = ['Pothole', 'Garbage', 'Street Light', 'Uncategorized']


def lambda_handler(event, context):
    conn = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        connect_timeout=5,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT category, COUNT(*) FROM reports GROUP BY category")
            rows = cursor.fetchall()
    finally:
        conn.close()

    counts = {category: 0 for category in DEFAULT_CATEGORIES}
    for category, count in rows:
        counts[category] = count

    payload = {
        'counts': counts,
        'total': sum(counts.values()),
        'updatedAt': datetime.now(timezone.utc).isoformat(),
    }

    s3.put_object(
        Bucket=OUTPUT_BUCKET,
        Key=OUTPUT_KEY,
        Body=json.dumps(payload),
        ContentType='application/json',
        CacheControl='no-cache',
    )

    print(f"Wrote counts to s3://{OUTPUT_BUCKET}/{OUTPUT_KEY}: {payload}")

    return {'statusCode': 200, 'body': json.dumps(payload)}
