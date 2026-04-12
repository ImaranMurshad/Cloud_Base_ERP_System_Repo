"""
==================================================================
 cloudwatch_utils.py  —  Custom AWS CloudWatch Library for ERP
==================================================================
Purpose : Send structured log events AND custom business metrics
          to AWS CloudWatch from inside your Django views.

Your project already writes logs to /home/ubuntu/erp_logs.log
which CloudWatch Agent reads. This library ALSO sends events
directly to CloudWatch Logs via the API — giving you instant
visibility in the AWS Console without waiting for the agent.

Two classes:
  CloudWatchLogger   → track user actions as log events
  CloudWatchMetrics  → publish business numbers as metric graphs

HOW TO USE in views.py:
    from utils.cloudwatch_utils import CloudWatchLogger, CloudWatchMetrics

    cw  = CloudWatchLogger()
    cwm = CloudWatchMetrics()

    cw.log_login(username='imran')
    cwm.record_invoice_created(total_amount=350.00)
==================================================================
"""

import boto3
import logging
import time
from django.conf import settings

logger = logging.getLogger("core")

# CloudWatch Logs configuration — matches the log group
# your CloudWatch Agent is already configured to use
LOG_GROUP = "/erp/django"
LOG_STREAM = "erp-app-events"

# CloudWatch Metrics namespace — shows as a custom namespace
# in the AWS CloudWatch Metrics console
METRICS_NAMESPACE = "ERP/Application"


# ==================================================================
# CLASS 1 — LOG EVENTS
# ==================================================================


class CloudWatchLogger:
    """
    Custom library to send structured log events directly to
    AWS CloudWatch Logs from your Django views.

    Each method maps to one real action in your ERP app:
      - User logged in / logged out
      - Invoice created
      - Backup exported (and which S3 key it was saved to)
      - Backup imported
      - Any error that needs to be tracked

    All events appear in:
      AWS Console → CloudWatch → Log Groups → /erp/django

    Example:
        cw = CloudWatchLogger()
        cw.log_login('imran')
        cw.log_invoice_created('imran', invoice_id=5, total_amount=299.99)
        cw.log_backup_exported('imran', 'full', s3_key='backups/full_imran_2025-04-11.csv')
    """

    def __init__(self):
        self.client = boto3.client(
            "logs",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )
        self._ensure_log_group_stream()

    def _ensure_log_group_stream(self):
        """
        Create the log group and stream in CloudWatch if they
        do not already exist. Safe to call on every request —
        AWS raises ResourceAlreadyExistsException which we catch.
        """
        for create_fn, kwargs in [
            (self.client.create_log_group, {"logGroupName": LOG_GROUP}),
            (
                self.client.create_log_stream,
                {"logGroupName": LOG_GROUP, "logStreamName": LOG_STREAM},
            ),
        ]:
            try:
                create_fn(**kwargs)
            except self.client.exceptions.ResourceAlreadyExistsException:
                pass  # already exists — fine
            except Exception as e:
                logger.warning(f"[CloudWatch] Setup warning: {e}")

    def _send_event(self, message):
        """
        Internal: push a single log event to CloudWatch Logs.
        Timestamp is in milliseconds (required by the API).
        The app never crashes if CloudWatch is unavailable.
        """
        try:
            self.client.put_log_events(
                logGroupName=LOG_GROUP,
                logStreamName=LOG_STREAM,
                logEvents=[
                    {
                        "timestamp": int(time.time() * 1000),
                        "message": message,
                    }
                ],
            )
        except Exception as e:
            # Only warn — never block the request
            logger.warning(f"[CloudWatch] Failed to send log event: {e}")

    # -----------------------------------------------------------
    # Public logging methods — one per key ERP action
    # -----------------------------------------------------------

    def log_login(self, username):
        """
        Log a successful user login.
        Called from: login_view in views.py

        Example:
            cw.log_login(request.user.username)
        """
        msg = f"[LOGIN] user={username}"
        self._send_event(msg)
        logger.info(msg)

    def log_logout(self, username):
        """
        Log a user logout.
        Called from: logout_view in views.py

        Example:
            cw.log_logout(request.user.username)
        """
        msg = f"[LOGOUT] user={username}"
        self._send_event(msg)
        logger.info(msg)

    def log_invoice_created(self, username, invoice_id, total_amount):
        """
        Log a new invoice creation with its total value.
        Called from: create_invoice in views.py

        Args:
            username     : str   – request.user.username
            invoice_id   : int   – invoice.id after save
            total_amount : float – invoice.total_amount

        Example:
            cw.log_invoice_created('imran', invoice.id, invoice.total_amount)
        """
        msg = (
            f"[INVOICE_CREATED] user={username} "
            f"invoice_id={invoice_id} total=€{total_amount:.2f}"
        )
        self._send_event(msg)
        logger.info(msg)

    def log_backup_exported(self, username, backup_type, s3_key=None):
        """
        Log a backup export. Includes the S3 key if upload succeeded.
        Called from: export_backup in views.py

        Args:
            username    : str       – request.user.username
            backup_type : str       – 'full', 'customer', 'product', 'invoice'
            s3_key      : str|None  – S3 key returned by S3Manager.upload_backup()

        Example:
            cw.log_backup_exported('imran', 'full', s3_key='backups/full_imran_2025-04-11.csv')
        """
        s3_info = f" s3_key={s3_key}" if s3_key else " s3=upload_failed"
        msg = f"[BACKUP_EXPORTED] user={username} type={backup_type}{s3_info}"
        self._send_event(msg)
        logger.info(msg)

    def log_backup_imported(self, username, filename):
        """
        Log a backup import from a CSV file.
        Called from: import_backup in views.py

        Args:
            username : str – request.user.username
            filename : str – uploaded file name

        Example:
            cw.log_backup_imported('imran', file.name)
        """
        msg = f"[BACKUP_IMPORTED] user={username} file={filename}"
        self._send_event(msg)
        logger.info(msg)

    def log_error(self, username, view_name, error_message):
        """
        Log an application error — use in except blocks.

        Args:
            username      : str – request.user.username
            view_name     : str – e.g. 'export_backup'
            error_message : str – str(e) from the exception

        Example:
            except Exception as e:
                cw.log_error(request.user.username, 'export_backup', str(e))
        """
        msg = f"[ERROR] user={username} view={view_name} error={error_message}"
        self._send_event(msg)
        logger.error(msg)


# ==================================================================
# CLASS 2 — CUSTOM METRICS
# ==================================================================


class CloudWatchMetrics:
    """
    Custom library to publish business metrics from your ERP app
    to AWS CloudWatch as time-series data points.

    These appear as graphs under:
      AWS Console → CloudWatch → Metrics → Custom namespaces → ERP/Application

    You can build a CloudWatch Dashboard from these metrics to
    track business activity over time.

    Metrics published:
      InvoicesCreated   (Count)     – how many invoices were created
      RevenueGenerated  (Amount)    – total revenue from invoices
      BackupsExported   (Count)     – how many backups exported to S3
      BackupsImported   (Count)     – how many backup CSVs imported
      ProductsAdded     (Count)     – new products added
      CustomersAdded    (Count)     – new customers added

    Example:
        cwm = CloudWatchMetrics()
        cwm.record_invoice_created(total_amount=350.00)
        cwm.record_backup_exported()
    """

    def __init__(self):
        self.client = boto3.client(
            "cloudwatch",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )

    def _publish(self, metric_name, value, unit="Count"):
        """
        Internal: publish one metric data point to CloudWatch.

        Args:
            metric_name : str   – e.g. 'InvoicesCreated'
            value       : float – the numeric value
            unit        : str   – 'Count', 'None' (for currency amounts)
        """
        try:
            self.client.put_metric_data(
                Namespace=METRICS_NAMESPACE,
                MetricData=[
                    {
                        "MetricName": metric_name,
                        "Value": value,
                        "Unit": unit,
                    }
                ],
            )
            logger.info(f"[CloudWatch Metric] {metric_name} = {value} ({unit})")

        except Exception as e:
            logger.warning(
                f"[CloudWatch Metric] Failed to publish '{metric_name}': {e}"
            )

    def record_invoice_created(self, total_amount):
        """
        Record one invoice created + its revenue value.
        Publishes two metrics: InvoicesCreated and RevenueGenerated.
        Called from: create_invoice in views.py

        Args:
            total_amount : float – invoice.total_amount

        Example:
            cwm = CloudWatchMetrics()
            cwm.record_invoice_created(total_amount=invoice.total_amount)
        """
        self._publish("InvoicesCreated", 1, unit="Count")
        self._publish("RevenueGenerated", total_amount, unit="None")

    def record_backup_exported(self):
        """
        Record one backup export event.
        Called from: export_backup in views.py

        Example:
            cwm.record_backup_exported()
        """
        self._publish("BackupsExported", 1, unit="Count")

    def record_backup_imported(self):
        """
        Record one backup import event.
        Called from: import_backup in views.py

        Example:
            cwm.record_backup_imported()
        """
        self._publish("BackupsImported", 1, unit="Count")

    def record_product_added(self):
        """
        Record one new product added.
        Called from: add_product in views.py

        Example:
            cwm.record_product_added()
        """
        self._publish("ProductsAdded", 1, unit="Count")

    def record_customer_added(self):
        """
        Record one new customer added.
        Called from: add_customer in views.py

        Example:
            cwm.record_customer_added()
        """
        self._publish("CustomersAdded", 1, unit="Count")
