"""
s3_client.py — MinIO/S3 Client Integration

Wrapper around boto3 for interfacing with our local MinIO instance (or real S3 in prod).
Handles bucket creation, file upload, and presigned URL generation.
"""

import logging
import os
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class S3Client:
    def __init__(self):
        # Read from environment variables, defaulting to local MinIO setup
        self.endpoint_url = os.environ.get('S3_ENDPOINT_URL', 'http://localhost:9000')
        self.access_key = os.environ.get('S3_ACCESS_KEY', 'minioadmin')
        self.secret_key = os.environ.get('S3_SECRET_KEY', 'minioadmin')
        self.reports_bucket = os.environ.get('S3_REPORTS_BUCKET', 'vitalmind-reports')
        
        # In MinIO local setup, we need address_style='path' for bucket URLs like /bucket/key
        self.client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}),
            region_name='us-east-1' # Generic region for boto3 compatibility
        )
        
        # Ensure the reports bucket exists on startup
        self._ensure_bucket_exists(self.reports_bucket)

    def _ensure_bucket_exists(self, bucket_name: str):
        """Creates the bucket if it doesn't already exist."""
        try:
            self.client.head_bucket(Bucket=bucket_name)
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == '404':
                try:
                    logger.info("S3Client: Creating bucket '%s'", bucket_name)
                    self.client.create_bucket(Bucket=bucket_name)
                except Exception as create_exc:
                    logger.error("S3Client: Failed to create bucket '%s': %s", bucket_name, create_exc)
            else:
                logger.error("S3Client: Error checking bucket '%s': %s", bucket_name, e)

    def upload_file_bytes(self, file_bytes: bytes, filename: str, content_type: str = 'application/pdf') -> Optional[str]:
        """
        Uploads raw bytes to the reports bucket.
        Returns the object key if successful.
        """
        try:
            self.client.put_object(
                Bucket=self.reports_bucket,
                Key=filename,
                Body=file_bytes,
                ContentType=content_type
            )
            logger.info("S3Client: Uploaded %s to bucket %s", filename, self.reports_bucket)
            return filename
        except Exception as e:
            logger.error("S3Client: Upload failed for %s: %s", filename, e)
            return None

    def get_presigned_url(self, object_key: str, expiration_seconds: int = 3600) -> Optional[str]:
        """
        Generates a temporary read-only URL for the frontend to display the file.
        """
        try:
            url = self.client.generate_presigned_url(
                ClientMethod='get_object',
                Params={
                    'Bucket': self.reports_bucket,
                    'Key': object_key
                },
                ExpiresIn=expiration_seconds
            )
            # If backend is running in docker but frontend is host, rewrite 'minio' to 'localhost' if necessary
            # For our local setup, it's usually 9000 anyway
            if 'minio:9000' in url:
                url = url.replace('minio:9000', 'localhost:9000')
            return url
        except Exception as e:
            logger.error("S3Client: Failed to generate presigned URL for %s: %s", object_key, e)
            return None

    def get_file_bytes(self, object_key: str) -> Optional[bytes]:
        """
        Downloads the file object as raw bytes. Used by the Agent to read the file.
        """
        try:
            response = self.client.get_object(Bucket=self.reports_bucket, Key=object_key)
            return response['Body'].read()
        except Exception as e:
            logger.error("S3Client: Failed to get object bytes for %s: %s", object_key, e)
            return None

# Singleton instance
s3_client = S3Client()
