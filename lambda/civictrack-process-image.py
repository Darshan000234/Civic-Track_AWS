"""
civictrack-process-image
Triggered by: S3 ObjectCreated events on the uploads/ prefix
Requires the pymysql Lambda layer.

Env vars required:
  DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
"""
import json
import os

import boto3
import pymysql

rekognition = boto3.client('rekognition')

DB_HOST = os.environ['DB_HOST']
DB_USER = os.environ['DB_USER']
DB_PASSWORD = os.environ['DB_PASSWORD']
DB_NAME = os.environ['DB_NAME']

# Keyword groups used to map Rekognition's generic labels onto our
# three civic-issue categories. Add more keywords here as you observe
# what Rekognition actually returns for your real photos.
CATEGORY_KEYWORDS = {
    'Pothole': ['pothole', 'asphalt', 'crack', 'pavement', 'tarmac',
                'hole', 'gravel', 'sinkhole'],
    'Garbage Collection': ['garbage', 'trash', 'waste', 'litter', 'rubbish',
                            'junk', 'dump', 'debris', 'landfill'],
    'Street Light': ['street light', 'lamp', 'light fixture', 'pole',
                      'lamppost', 'lighting', 'streetlight', 'lantern'],
    'Traffic': ['traffic light', 'traffic sign', 'stop sign', 'car',
                'vehicle', 'road sign', 'intersection', 'signal',
                'traffic jam', 'highway', 'congestion', 'road'],
}


def categorize(labels):
    """labels: list of {'Name': str, 'Confidence': float, ...}"""
    scores = {cat: 0.0 for cat in CATEGORY_KEYWORDS}

    for label in labels:
        name = label['Name'].lower()
        confidence = label['Confidence']
        for category, keywords in CATEGORY_KEYWORDS.items():
            if any(keyword in name for keyword in keywords):
                scores[category] += confidence

    best_category = max(scores, key=scores.get)
    if scores[best_category] == 0:
        return 'Uncategorized', 0.0

    return best_category, round(scores[best_category], 2)


def get_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        connect_timeout=5,
    )


def lambda_handler(event, context):
    record = event['Records'][0]
    bucket = record['s3']['bucket']['name']
    # S3 event keys are URL-encoded (spaces become '+', etc.)
    key = record['s3']['object']['key'].replace('+', ' ')

    response = rekognition.detect_labels(
        Image={'S3Object': {'Bucket': bucket, 'Name': key}},
        MaxLabels=20,
        MinConfidence=60,
    )
    labels = response['Labels']
    category, score = categorize(labels)

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO reports (image_key, category, confidence_score, raw_labels)
                VALUES (%s, %s, %s, %s)
                """,
                (key, category, score, json.dumps([l['Name'] for l in labels])),
            )
        conn.commit()
    finally:
        conn.close()

    print(f"Processed {key} -> {category} (score {score})")

    return {
        'statusCode': 200,
        'body': json.dumps({'key': key, 'category': category, 'score': score}),
    }
