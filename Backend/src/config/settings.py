"""Configuration loader with YAML and AWS Secrets Manager support."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import boto3
import structlog
import yaml
from botocore.exceptions import ClientError

from src.config.models import Settings

logger = structlog.get_logger(__name__)


class ConfigLoader:
    """Configuration loader with YAML and AWS Secrets Manager support."""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration loader.

        Args:
            config_path: Optional path to config.yaml file. If None, looks for
                        config/config.yaml relative to project root.
        """
        if config_path is None:
            # Look for config.yaml in Backend/config/ directory
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "config.yaml"

        self.config_path = config_path
        self._settings: Optional[Settings] = None

    def _load_yaml_config(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file.

        Returns:
            Dictionary containing configuration values.

        Raises:
            FileNotFoundError: If config file doesn't exist.
            yaml.YAMLError: If YAML parsing fails.
        """
        if not self.config_path.exists():
            logger.warning(
                "Config file not found, using environment variables only",
                config_path=str(self.config_path),
            )
            return {}

        logger.info("Loading configuration from YAML file", config_path=str(self.config_path))

        with open(self.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        # Replace environment variable placeholders
        config = self._substitute_env_vars(config)

        return config

    def _substitute_env_vars(self, config: Any) -> Any:
        """
        Recursively substitute environment variable placeholders in config.

        Args:
            config: Configuration value (can be dict, list, or str).

        Returns:
            Configuration with environment variables substituted.
        """
        if isinstance(config, dict):
            return {key: self._substitute_env_vars(value) for key, value in config.items()}
        elif isinstance(config, list):
            return [self._substitute_env_vars(item) for item in config]
        elif isinstance(config, str) and config.startswith("${") and config.endswith("}"):
            # Extract environment variable name
            env_var = config[2:-1]
            # Check if there's a default value: ${VAR:default}
            if ":" in env_var:
                var_name, default_value = env_var.split(":", 1)
                return os.getenv(var_name, default_value)
            else:
                value = os.getenv(env_var)
                if value is None:
                    logger.warning(
                        "Environment variable not set", variable=env_var, config_path=str(self.config_path)
                    )
                return value or config
        else:
            return config

    def _load_aws_secrets(self, secret_name: str, region: str = "us-east-2") -> Dict[str, Any]:
        """
        Load secrets from AWS Secrets Manager.

        Args:
            secret_name: Name of the secret in AWS Secrets Manager.
            region: AWS region.

        Returns:
            Dictionary containing secrets.

        Raises:
            ClientError: If AWS API call fails.
        """
        try:
            logger.info("Loading secrets from AWS Secrets Manager", secret_name=secret_name)

            session = boto3.Session()
            client = session.client("secretsmanager", region_name=region)

            response = client.get_secret_value(SecretId=secret_name)
            secret_string = response["SecretString"]

            # Try to parse as JSON first, fallback to YAML
            try:
                import json

                secrets = json.loads(secret_string)
            except json.JSONDecodeError:
                secrets = yaml.safe_load(secret_string) or {}

            logger.info("Successfully loaded secrets from AWS Secrets Manager")
            return secrets

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "ResourceNotFoundException":
                logger.warning(
                    "Secret not found in AWS Secrets Manager, skipping",
                    secret_name=secret_name,
                )
                return {}
            else:
                logger.error(
                    "Failed to load secrets from AWS Secrets Manager",
                    secret_name=secret_name,
                    error=str(e),
                )
                raise

    def _merge_configs(
        self, yaml_config: Dict[str, Any], secrets: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge YAML config and AWS secrets, with secrets taking precedence.

        Args:
            yaml_config: Configuration from YAML file.
            secrets: Secrets from AWS Secrets Manager.

        Returns:
            Merged configuration dictionary.
        """
        # Deep merge: secrets override YAML config
        merged = yaml_config.copy()

        def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
            """Recursively merge dictionaries."""
            result = base.copy()
            for key, value in override.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result

        return deep_merge(merged, secrets)

    def load(self, use_aws_secrets: Optional[bool] = None) -> Settings:
        """
        Load configuration from YAML file and optionally AWS Secrets Manager.

        Args:
            use_aws_secrets: Whether to load from AWS Secrets Manager.
                            If None, checks app.environment or AWS_SECRETS_ENABLED env var.

        Returns:
            Settings object with loaded configuration.

        Raises:
            ValueError: If required configuration is missing.
        """
        # Load YAML config
        yaml_config = self._load_yaml_config()

        # Determine if we should use AWS Secrets Manager
        if use_aws_secrets is None:
            use_aws_secrets = (
                os.getenv("AWS_SECRETS_ENABLED", "false").lower() == "true"
                or yaml_config.get("aws", {}).get("secrets_manager", {}).get("enabled", False)
            )

        secrets = {}
        if use_aws_secrets:
            secret_name = (
                yaml_config.get("aws", {})
                .get("secrets_manager", {})
                .get("secret_name", "portkey-prompt-parser/secrets")
            )
            aws_region = yaml_config.get("aws", {}).get("region", "us-east-2")

            try:
                secrets = self._load_aws_secrets(secret_name, aws_region)
            except Exception as e:
                logger.error(
                    "Failed to load AWS secrets, continuing with YAML config only",
                    error=str(e),
                )

        # Merge configurations
        merged_config = self._merge_configs(yaml_config, secrets)

        # Create Settings object
        try:
            settings = Settings(**merged_config)
            logger.info("Configuration loaded successfully")
            return settings
        except Exception as e:
            logger.error("Failed to load configuration", error=str(e))
            raise ValueError(f"Configuration validation failed: {e}") from e

    def get_settings(self, use_aws_secrets: Optional[bool] = None) -> Settings:
        """
        Get settings (cached).

        Args:
            use_aws_secrets: Whether to load from AWS Secrets Manager.

        Returns:
            Settings object.
        """
        if self._settings is None:
            self._settings = self.load(use_aws_secrets=use_aws_secrets)
        return self._settings


# Global settings instance
_settings_instance: Optional[Settings] = None
_config_loader: Optional[ConfigLoader] = None


def get_settings(config_path: Optional[Path] = None, use_aws_secrets: Optional[bool] = None) -> Settings:
    """
    Get global settings instance.

    Args:
        config_path: Optional path to config.yaml file.
        use_aws_secrets: Whether to load from AWS Secrets Manager.

    Returns:
        Settings object.
    """
    global _settings_instance, _config_loader

    if _settings_instance is None:
        if _config_loader is None:
            _config_loader = ConfigLoader(config_path)
        _settings_instance = _config_loader.get_settings(use_aws_secrets=use_aws_secrets)

    return _settings_instance


def reload_settings(config_path: Optional[Path] = None, use_aws_secrets: Optional[bool] = None) -> Settings:
    """
    Reload settings from configuration files.

    Args:
        config_path: Optional path to config.yaml file.
        use_aws_secrets: Whether to load from AWS Secrets Manager.

    Returns:
        Settings object.
    """
    global _settings_instance, _config_loader

    _config_loader = ConfigLoader(config_path)
    _settings_instance = _config_loader.load(use_aws_secrets=use_aws_secrets)

    return _settings_instance

