"""
============================================================
 s3_utils.py  —  Custom AWS S3 Library for ERP Project
============================================================
Purpose : Replace the raw boto3 calls scattered in views.py
          with a clean, reusable library.

Your project uses S3 to store CSV exports:
  - Customer backups   → s3://erp-exports-imran/backups/
  - Product backups    → s3://erp-exports-imran/backups/
  - Invoice backups    → s3://erp-exports-imran/backups/
  - Full backups       → s3://erp-exports-imran/backups/
  - Invoice exports    → s3://erp-exports-imran/invoices/

HOW TO USE in views.py:
    from utils.s3_utils import S3Manager
    s3 = S3Manager()
    url = s3.upload_backup(request.user.username, backup_type, response.content)
============================================================
"""

import boto3
import logging
from datetime import date
from django.conf import settings

logger = logging.getLogger('core')


class S3Manager:
    """
    Custom S3 library for the ERP Django application.

    Wraps all boto3 S3 calls so views.py stays clean and
    every S3 interaction goes through one tested place.

    Methods:
        upload_backup(username, backup_type, csv_bytes)  → s3_key or None
        upload_invoice_export(username, csv_bytes)        → s3_key or None
        list_backups(username)                            → list of dicts
        get_download_url(s3_key, expiry=300)              → url string or None
        delete_file(s3_key)                               → True / False
    """

    def __init__(self):
        # Uses env vars already set in your settings.py
        self.client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )
        self.bucket = settings.AWS_STORAGE_BUCKET_NAME

    # -------------------------------------------------------
    # PRIVATE: core upload helper used by all public methods
    # -------------------------------------------------------
    def _upload(self, key, content, content_type='text/csv'):
        """
        Upload raw bytes to S3 under the given key.

        Args:
            key          : str   – full S3 path e.g. 'backups/full_imran_2025-04-11.csv'
            content      : bytes – file content (CSV bytes from Django HttpResponse)
            content_type : str   – MIME type, default 'text/csv'

        Returns:
            str   – the S3 key if upload succeeded
            None  – if any error occurred (error is logged, app does NOT crash)
        """
        if isinstance(content, str):
            content = content.encode('utf-8')

        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
            logger.info(f"[S3] Upload OK → s3://{self.bucket}/{key}")
            return key

        except Exception as e:
            logger.error(f"[S3] Upload FAILED for key '{key}': {e}")
            return None

    # -------------------------------------------------------
    # PUBLIC: upload a backup CSV (customers/products/invoices/full)
    # -------------------------------------------------------
    def upload_backup(self, username, backup_type, csv_bytes):
        """
        Upload a backup CSV to the 'backups/' folder in S3.

        Called from the export_backup view in views.py after the
        CSV is built but before it is returned to the browser.

        Args:
            username    : str   – request.user.username  (e.g. 'imran')
            backup_type : str   – one of 'customer', 'product', 'invoice', 'full'
            csv_bytes   : bytes – response.content from the Django HttpResponse

        Returns:
            str   – S3 key e.g. 'backups/full_imran_2025-04-11.csv'
            None  – if upload fails

        Example:
            s3 = S3Manager()
            key = s3.upload_backup(request.user.username, 'full', response.content)
        """
        filename = f"{backup_type}_{username}_{date.today()}.csv"
        key = f"backups/{filename}"
        return self._upload(key, csv_bytes)

    # -------------------------------------------------------
    # PUBLIC: upload an invoice export CSV
    # -------------------------------------------------------
    def upload_invoice_export(self, username, csv_bytes):
        """
        Upload an invoice export CSV to the 'invoices/' folder in S3.

        Called from the export_invoices view in views.py.

        Args:
            username  : str   – request.user.username
            csv_bytes : bytes – response.content from the Django HttpResponse

        Returns:
            str   – S3 key e.g. 'invoices/invoices_imran_2025-04-11.csv'
            None  – if upload fails

        Example:
            s3 = S3Manager()
            key = s3.upload_invoice_export(request.user.username, response.content)
        """
        filename = f"invoices_{username}_{date.today()}.csv"
        key = f"invoices/{filename}"
        return self._upload(key, csv_bytes)

    # -------------------------------------------------------
    # PUBLIC: list all backup files for a user
    # -------------------------------------------------------
    def list_backups(self, username=None):
        """
        List all files in the 'backups/' folder.

        Optionally filters by username so each user only
        sees their own backup files.

        Args:
            username : str or None – if given, only files containing
                                     this username are returned

        Returns:
            list of dicts:
                [
                  {
                    'key':           'backups/full_imran_2025-04-11.csv',
                    'filename':      'full_imran_2025-04-11.csv',
                    'size_kb':       4,
                    'last_modified': datetime object,
                  },
                  ...
                ]
            Returns [] on any error.

        Example:
            s3 = S3Manager()
            files = s3.list_backups(username=request.user.username)
        """
        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket,
                Prefix='backups/'
            )
            files = []
            for obj in response.get('Contents', []):
                key = obj['Key']
                if key == 'backups/':   # skip the folder entry itself
                    continue
                if username and username not in key:
                    continue            # filter by user
                files.append({
                    'key':           key,
                    'filename':      key.split('/')[-1],
                    'size_kb':       round(obj['Size'] / 1024, 1),
                    'last_modified': obj['LastModified'],
                })
            logger.info(f"[S3] Listed {len(files)} backups for user '{username}'")
            return files

        except Exception as e:
            logger.error(f"[S3] list_backups failed: {e}")
            return []

    # -------------------------------------------------------
    # PUBLIC: generate a temporary download link
    # -------------------------------------------------------
    def get_download_url(self, s3_key, expiry=300):
        """
        Generate a pre-signed URL so a user can download a file
        directly from S3 without exposing your bucket credentials.

        Args:
            s3_key : str – full S3 key  e.g. 'backups/full_imran_2025-04-11.csv'
            expiry : int – seconds until the URL expires (default = 5 minutes)

        Returns:
            str  – a temporary HTTPS download URL
            None – if URL generation fails

        Example:
            s3 = S3Manager()
            url = s3.get_download_url('backups/full_imran_2025-04-11.csv')
            return redirect(url)
        """
        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': s3_key},
                ExpiresIn=expiry,
            )
            logger.info(f"[S3] Pre-signed URL created for '{s3_key}' (expires in {expiry}s)")
            return url

        except Exception as e:
            logger.error(f"[S3] get_download_url failed for '{s3_key}': {e}")
            return None

    # -------------------------------------------------------
    # PUBLIC: delete a file from S3
    # -------------------------------------------------------
    def delete_file(self, s3_key):
        """
        Permanently delete a file from the S3 bucket.

        Args:
            s3_key : str – full S3 key e.g. 'backups/full_imran_2025-04-11.csv'

        Returns:
            True  – deleted successfully
            False – error occurred (logged)

        Example:
            s3 = S3Manager()
            s3.delete_file('backups/full_imran_2025-04-11.csv')
        """
        try:
            self.client.delete_object(Bucket=self.bucket, Key=s3_key)
            logger.info(f"[S3] Deleted: '{s3_key}'")
            return True

        except Exception as e:
            logger.error(f"[S3] delete_file failed for '{s3_key}': {e}")
            return False
