"""
==================================================================
 iam_utils.py  —  Custom AWS IAM Security Library for ERP Project
==================================================================
Purpose : Provide all IAM and security-related helpers so that
          credentials, permission checks, and secret loading are
          handled in one place rather than scattered across the app.

Three classes:
  SecureConfig       → safely load secrets from environment variables
  IAMCredentialCheck → verify AWS credentials are valid (STS call)
  IAMPermissionAudit → check what S3/CloudWatch permissions are active

HOW TO USE in settings.py:
    from utils.iam_utils import SecureConfig
    SECRET_KEY          = SecureConfig.get('SECRET_KEY', default='dev-only-key')
    AWS_ACCESS_KEY_ID   = SecureConfig.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = SecureConfig.get('AWS_SECRET_ACCESS_KEY')

HOW TO USE in views.py (credential check):
    from utils.iam_utils import IAMCredentialCheck
    result = IAMCredentialCheck().verify()
==================================================================
"""

import os
import logging
import boto3
from django.conf import settings

logger = logging.getLogger("core")

# All environment variables the ERP app requires to run on AWS
REQUIRED_ENV_VARS = [
    "DB_HOST",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "SECRET_KEY",
]

# S3 + CloudWatch actions the EC2 role (erp-ec2-role) must have
REQUIRED_AWS_ACTIONS = [
    "s3:PutObject",
    "s3:GetObject",
    "s3:ListBucket",
    "s3:DeleteObject",
    "logs:CreateLogGroup",
    "logs:CreateLogStream",
    "logs:PutLogEvents",
    "cloudwatch:PutMetricData",
]


# ==================================================================
# CLASS 1 — Secure Config Loader
# ==================================================================


class SecureConfig:
    """
    Custom library to load sensitive config values from environment
    variables only — never from hardcoded strings in settings.py.

    This prevents secrets from being committed to Git and ensures
    your EC2 instance and local laptop use different credentials.

    All methods are static — no need to instantiate the class.

    Example:
        from utils.iam_utils import SecureConfig

        SECRET_KEY = SecureConfig.get('SECRET_KEY', default='dev-key')
        DB_PASS    = SecureConfig.get('DB_PASSWORD', required=True)
        aws_cfg    = SecureConfig.get_aws_config()
    """

    @staticmethod
    def get(key, default=None, required=False):
        """
        Read one environment variable safely.

        Args:
            key      : str  – variable name e.g. 'DB_PASSWORD'
            default  : any  – value returned when variable is not set
            required : bool – if True, raises ValueError when missing

        Returns:
            str – the variable value, or default

        Raises:
            ValueError – only if required=True and the variable is missing

        Examples:
            # Returns 'dev-fallback' on laptop, real key on EC2:
            key = SecureConfig.get('SECRET_KEY', default='dev-fallback')

            # Crashes at startup if DB_PASSWORD is not set:
            password = SecureConfig.get('DB_PASSWORD', required=True)
        """
        value = os.environ.get(key, default)

        if required and value is None:
            raise ValueError(
                f"[IAM] Required env var '{key}' is not set. "
                f"On EC2 add it to /etc/environment. "
                f"On your laptop run: export {key}='yourvalue'"
            )

        if value is None:
            logger.warning(f"[IAM] Env var '{key}' is not set and has no default.")

        return value

    @staticmethod
    def check_all_present():
        """
        Check that every required environment variable is set.
        Does not connect to AWS — just checks local env.

        Returns:
            dict:
                'status'  : 'ok' or 'missing'
                'missing' : list of missing variable names (empty if all present)
                'message' : human-readable summary string

        Example:
            result = SecureConfig.check_all_present()
            if result['status'] == 'missing':
                print("Missing:", result['missing'])
        """
        missing = [var for var in REQUIRED_ENV_VARS if not os.environ.get(var)]

        if missing:
            logger.warning(f"[IAM] Missing env vars: {missing}")
            return {
                "status": "missing",
                "missing": missing,
                "message": f"Missing environment variables: {', '.join(missing)}",
            }

        logger.info("[IAM] All required environment variables are present")
        return {
            "status": "ok",
            "missing": [],
            "message": "All required environment variables are present",
        }

    @staticmethod
    def get_aws_config():
        """
        Return a dict of all AWS config values currently set.
        The secret key is masked so this is safe to log or display.

        Returns:
            dict:
                'AWS_ACCESS_KEY_ID'      : 'AKIA...' or None
                'AWS_SECRET_ACCESS_KEY'  : '***masked***' or None
                'AWS_STORAGE_BUCKET_NAME': 'erp-exports-imran' or None
                'AWS_S3_REGION_NAME'     : 'eu-north-1' or None

        Example:
            cfg = SecureConfig.get_aws_config()
            print(cfg)
            # {'AWS_ACCESS_KEY_ID': 'AKIAIOSFODNN7EXAMPLE',
            #  'AWS_SECRET_ACCESS_KEY': '***masked***', ...}
        """
        secret = os.environ.get("AWS_SECRET_ACCESS_KEY")
        return {
            "AWS_ACCESS_KEY_ID": os.environ.get("AWS_ACCESS_KEY_ID"),
            "AWS_SECRET_ACCESS_KEY": "***masked***" if secret else None,
            "AWS_STORAGE_BUCKET_NAME": os.environ.get("AWS_STORAGE_BUCKET_NAME"),
            "AWS_S3_REGION_NAME": os.environ.get("AWS_S3_REGION_NAME", "eu-north-1"),
        }


# ==================================================================
# CLASS 2 — Credential Validator
# ==================================================================


class IAMCredentialCheck:
    """
    Custom library to confirm AWS credentials are valid by calling
    AWS STS (Security Token Service) GetCallerIdentity.

    This tells you:
      - Which IAM identity is active (EC2 role or IAM user)
      - What AWS account the credentials belong to

    On EC2 with the erp-ec2-role attached, no credentials are
    needed — boto3 picks them up automatically from the instance
    metadata. On your laptop it uses the env var credentials.

    Example:
        from utils.iam_utils import IAMCredentialCheck
        result = IAMCredentialCheck().verify()

        # Returns:
        # { 'status': 'ok',
        #   'identity': 'arn:aws:sts::123456789:assumed-role/erp-ec2-role/...',
        #   'account': '123456789012',
        #   'message': 'AWS credentials are valid' }
    """

    def __init__(self):
        self.client = boto3.client(  # type: ignore
            "sts",
            aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
            aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
            region_name=getattr(settings, "AWS_S3_REGION_NAME", "eu-north-1"),
        )

    def verify(self):
        """
        Call STS GetCallerIdentity to confirm credentials are valid.

        Returns:
            dict:
                'status'   : 'ok' or 'error'
                'identity' : ARN string of the active IAM role/user
                'account'  : AWS account ID (12-digit string)
                'message'  : human-readable result

        Example (on EC2 with erp-ec2-role):
            {
              'status':   'ok',
              'identity': 'arn:aws:sts::123456789012:assumed-role/erp-ec2-role/i-0abc...',
              'account':  '123456789012',
              'message':  'AWS credentials are valid'
            }
        """
        try:
            response = self.client.get_caller_identity()
            arn = response.get("Arn", "unknown")
            account = response.get("Account", "unknown")

            logger.info(f"[IAM] Credential check OK — identity: {arn}")
            return {
                "status": "ok",
                "identity": arn,
                "account": account,
                "message": "AWS credentials are valid",
            }

        except Exception as e:
            logger.error(f"[IAM] Credential check FAILED: {e}")
            return {
                "status": "error",
                "identity": None,
                "account": None,
                "message": str(e),
            }


# ==================================================================
# CLASS 3 — Permission Audit
# ==================================================================


class IAMPermissionAudit:
    """
    Custom library to check which AWS permissions are available
    to the current identity (EC2 role or IAM user).

    Uses IAM Policy Simulation to test whether each required
    action (S3, CloudWatch, Logs) is allowed or denied.

    Most useful on your laptop with an IAM admin user.
    On EC2 the erp-ec2-role may not have SimulatePrincipalPolicy
    permission itself, so results may show 'error' for that call
    while the real permissions still work fine.

    Example:
        from utils.iam_utils import IAMPermissionAudit
        results = IAMPermissionAudit().check_all()
        for action, status in results.items():
            print(f"{action}: {status}")

        # s3:PutObject:           allowed
        # logs:PutLogEvents:      allowed
        # cloudwatch:PutMetricData: allowed
    """

    def check_all(self):
        """
        Simulate each required IAM action and return the result.

        Returns:
            dict mapping action name → 'allowed', 'denied', or 'error'

            Example:
            {
              's3:PutObject':           'allowed',
              's3:GetObject':           'allowed',
              'logs:PutLogEvents':      'allowed',
              'cloudwatch:PutMetricData': 'allowed',
              ...
            }
        """
        import boto3
        from django.conf import settings

        results = {action: "unknown" for action in REQUIRED_AWS_ACTIONS}

        try:
            iam = boto3.client(
                "iam",
                aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
                aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
                region_name=getattr(settings, "AWS_S3_REGION_NAME", "eu-north-1"),
            )
            sts = boto3.client(
                "sts",
                aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
                aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
                region_name=getattr(settings, "AWS_S3_REGION_NAME", "eu-north-1"),
            )

            caller_arn = sts.get_caller_identity()["Arn"]
            bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "*")

            simulation = iam.simulate_principal_policy(
                PolicySourceArn=caller_arn,
                ActionNames=REQUIRED_AWS_ACTIONS,
                ResourceArns=[f"arn:aws:s3:::{bucket}/*", "*"],
            )

            for eval_result in simulation.get("EvaluationResults", []):
                action = eval_result["EvalActionName"]
                decision = eval_result["EvalDecision"]
                results[action] = "allowed" if decision == "allowed" else "denied"
                logger.info(f"[IAM] Permission check: {action} → {results[action]}")

        except Exception as e:
            logger.warning(f"[IAM] Permission simulation failed: {e}")
            results = {action: "error" for action in REQUIRED_AWS_ACTIONS}

        return results
