"""CloudWatch logging integration."""

import json
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError
from structlog import get_logger

from src.config.settings import get_settings

logger = get_logger(__name__)


class CloudWatchLogger:
    """CloudWatch logging handler."""

    def __init__(self):
        """Initialize CloudWatch logger."""
        settings = get_settings()
        cloudwatch_config = settings.observability.cloudwatch

        self.enabled = cloudwatch_config.enabled
        self.log_group = cloudwatch_config.log_group
        self.region = cloudwatch_config.region

        if self.enabled:
            try:
                self.client = boto3.client("logs", region_name=self.region)
                logger.info(
                    "CloudWatch logger initialized",
                    log_group=self.log_group,
                    region=self.region,
                )
            except Exception as e:
                logger.error("Failed to initialize CloudWatch client", error=str(e))
                self.enabled = False
        else:
            self.client = None
            logger.info("CloudWatch logging disabled")

    def _ensure_log_group(self) -> bool:
        """
        Ensure log group exists.

        Returns:
            True if log group exists or was created
        """
        if not self.enabled:
            return False

        try:
            # Try to describe log group
            self.client.describe_log_groups(logGroupNamePrefix=self.log_group)

            # Check if exact match exists
            response = self.client.describe_log_groups(logGroupNamePrefix=self.log_group)
            for group in response.get("logGroups", []):
                if group["logGroupName"] == self.log_group:
                    return True

            # Create log group if it doesn't exist
            self.client.create_log_group(logGroupName=self.log_group)
            logger.info("Created CloudWatch log group", log_group=self.log_group)
            return True

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "ResourceAlreadyExistsException":
                return True
            else:
                logger.error("Error ensuring log group", error=str(e))
                return False

    def send_log(self, level: str, message: str, **kwargs):
        """
        Send log to CloudWatch.

        Args:
            level: Log level (INFO, ERROR, etc.)
            message: Log message
            **kwargs: Additional log fields
        """
        if not self.enabled:
            return

        try:
            # Ensure log group exists
            self._ensure_log_group()

            # Create log stream name (use date-based naming)
            from datetime import datetime

            date_str = datetime.utcnow().strftime("%Y-%m-%d")
            log_stream = f"{date_str}/app"

            # Prepare log event
            log_data = {
                "level": level,
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                **kwargs,
            }

            log_event = {
                "timestamp": int(datetime.utcnow().timestamp() * 1000),
                "message": json.dumps(log_data),
            }

            # Try to create log stream (ignore if exists)
            try:
                self.client.create_log_stream(
                    logGroupName=self.log_group, logStreamName=log_stream
                )
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") != "ResourceAlreadyExistsException":
                    raise

            # Put log event
            self.client.put_log_events(
                logGroupName=self.log_group,
                logStreamName=log_stream,
                logEvents=[log_event],
            )

        except Exception as e:
            # Don't fail application if CloudWatch fails
            logger.warning("Failed to send log to CloudWatch", error=str(e))


# Global CloudWatch logger instance
_cloudwatch_logger: Optional[CloudWatchLogger] = None


def get_cloudwatch_logger() -> CloudWatchLogger:
    """
    Get global CloudWatch logger instance.

    Returns:
        CloudWatchLogger instance
    """
    global _cloudwatch_logger
    if _cloudwatch_logger is None:
        _cloudwatch_logger = CloudWatchLogger()
    return _cloudwatch_logger

