"""
==================================================================
 rds_utils.py  —  Custom AWS RDS Library for ERP Project
==================================================================
Purpose : Provide clean, reusable helpers for everything
          related to the RDS PostgreSQL database in your project.

Your project already has RDS wired in settings.py via os.environ.
This library adds:
  1. get_rds_settings()  – builds the DATABASES dict cleanly
  2. RDSHealthCheck      – verify the DB connection is alive
  3. RDSStats            – query live counts/totals from the DB

HOW TO USE in settings.py:
    from utils.rds_utils import get_rds_settings
    DATABASES = { 'default': get_rds_settings() }

HOW TO USE in views.py (health check):
    from utils.rds_utils import RDSHealthCheck, RDSStats
    status = RDSHealthCheck().ping()
    stats  = RDSStats().get_summary(user=request.user)
==================================================================
"""

import os
import logging

logger = logging.getLogger('core')


# ==================================================================
# FUNCTION 1 — Build the Django DATABASES config from env vars
# ==================================================================

def get_rds_settings():
    """
    Read environment variables and return a ready-to-use Django
    DATABASES['default'] config dictionary.

    - On EC2 with env vars set  → connects to RDS PostgreSQL
    - On your laptop (no DB_HOST) → falls back to local SQLite
      so development still works without a real RDS connection

    Returns:
        dict – Django-compatible database settings

    Usage in settings.py:
        from utils.rds_utils import get_rds_settings
        DATABASES = { 'default': get_rds_settings() }
    """
    db_host = os.environ.get('DB_HOST', '')

    if db_host:
        logger.info(f"[RDS] Connecting to PostgreSQL at {db_host}")
        return {
            'ENGINE':   'django.db.backends.postgresql',
            'NAME':     os.environ.get('DB_NAME', 'erp_db'),
            'USER':     os.environ.get('DB_USER', 'erpuser'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST':     db_host,
            'PORT':     os.environ.get('DB_PORT', '5432'),
            'OPTIONS': {
                'connect_timeout': 10,
            },
        }
    else:
        logger.info("[RDS] DB_HOST not set — using local SQLite fallback")
        from pathlib import Path
        BASE_DIR = Path(__file__).resolve().parent.parent
        return {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME':   BASE_DIR / 'db.sqlite3',
        }


# ==================================================================
# CLASS 1 — Health Check
# ==================================================================

class RDSHealthCheck:
    """
    Custom library to verify the RDS database is reachable
    and responding to queries.

    Useful in:
      - A /health/ URL endpoint
      - Your EC2 startup script
      - The admin dashboard

    Example:
        from utils.rds_utils import RDSHealthCheck
        result = RDSHealthCheck().ping()

        # Returns:
        # { 'status': 'ok',    'message': 'Database connection successful',
        #   'host': 'erp-db.xxx.eu-north-1.rds.amazonaws.com' }
        #
        # or on failure:
        # { 'status': 'error', 'message': 'could not connect to server: ...',
        #   'host': '...' }
    """

    def ping(self):
        """
        Run SELECT 1 to confirm the database is alive.

        Returns:
            dict:
                'status'  : 'ok' or 'error'
                'host'    : RDS endpoint or 'localhost (SQLite)'
                'message' : human-readable result string
        """
        from django.db import connection, OperationalError

        host = os.environ.get('DB_HOST', 'localhost (SQLite)')

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            logger.info("[RDS] Health check passed")
            return {
                'status':  'ok',
                'host':    host,
                'message': 'Database connection successful',
            }

        except OperationalError as e:
            logger.error(f"[RDS] Health check FAILED: {e}")
            return {
                'status':  'error',
                'host':    host,
                'message': str(e),
            }


# ==================================================================
# CLASS 2 — Live Statistics
# ==================================================================

class RDSStats:
    """
    Custom library to query live statistics from the RDS database.

    Returns counts and revenue totals for the dashboard or reports.
    Filters by user so each person only sees their own data.

    Example:
        from utils.rds_utils import RDSStats
        stats = RDSStats().get_summary(user=request.user)

        # Returns:
        # {
        #   'total_products'  : 12,
        #   'total_customers' : 8,
        #   'total_invoices'  : 31,
        #   'total_revenue'   : 4250.00,
        # }

    You can use these values in your dashboard view instead of
    writing the same queries in views.py every time.
    """

    def get_summary(self, user=None):
        """
        Query counts and total revenue from all ERP tables.

        Args:
            user : Django User object or None
                   – If provided: returns stats for this user only
                   – If None: returns totals across all users

        Returns:
            dict:
                'total_products'  : int
                'total_customers' : int
                'total_invoices'  : int
                'total_revenue'   : float  (rounded to 2 decimal places)

            Returns all zeros if any database error occurs.

        Example (in views.py dashboard):
            from utils.rds_utils import RDSStats
            stats = RDSStats().get_summary(user=request.user)
            return render(request, 'core/dashboard.html', stats)
        """
        from core.models import Product, Customer, Invoice
        from django.db.models import Sum

        try:
            filters = {'user': user} if user else {}

            total_products  = Product.objects.filter(**filters).count()
            total_customers = Customer.objects.filter(**filters).count()
            total_invoices  = Invoice.objects.filter(**filters).count()
            revenue_result  = Invoice.objects.filter(**filters).aggregate(
                                  total=Sum('total_amount')
                              )
            total_revenue   = round(revenue_result['total'] or 0.0, 2)

            logger.info(
                f"[RDS] Stats for user='{getattr(user, 'username', 'all')}': "
                f"products={total_products}, customers={total_customers}, "
                f"invoices={total_invoices}, revenue={total_revenue}"
            )

            return {
                'total_products':  total_products,
                'total_customers': total_customers,
                'total_invoices':  total_invoices,
                'total_revenue':   total_revenue,
            }

        except Exception as e:
            logger.error(f"[RDS] get_summary failed: {e}")
            return {
                'total_products':  0,
                'total_customers': 0,
                'total_invoices':  0,
                'total_revenue':   0.0,
            }
