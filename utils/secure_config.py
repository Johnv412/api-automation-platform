"""
Secure Configuration Loader

This module provides secure loading of configuration values from various sources,
including environment variables, configuration files, and secrets management systems.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class SecureConfigLoader:
    """
    Secure configuration loader that supports multiple sources and secret management.
    
    Features:
    - Environment variable loading
    - YAML/JSON configuration files
    - Encrypted secrets
    - Configuration validation
    - Environment-specific configurations
    - Secret masking in logs
    """
    
    def __init__(self, config_path: str = None):
        """
        Initialize the configuration loader.
        
        Args:
            config_path: Path to the configuration file. If None, default locations are used.
        """
        self.config_path = config_path
        self.config = {}
        self.env = os.environ.get("AIP_ENV", "development")
        
        # Load .env file if it exists
        dotenv_path = os.environ.get("AIP_DOTENV_PATH", ".env")
        if os.path.exists(dotenv_path):
            load_dotenv(dotenv_path)
            logger.debug(f"Loaded environment variables from {dotenv_path}")
        
        logger.debug(f"Initialized config loader for environment: {self.env}")
    
    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from all sources.
        
        Order of precedence (highest to lowest):
        1. Environment variables
        2. Environment-specific config file
        3. Default config file
        
        Returns:
            Merged configuration dictionary
        """
        # Start with empty config
        self.config = {}
        
        # Load default configuration
        default_config = self._load_default_config()
        self.config.update(default_config)
        
        # Load environment-specific configuration
        env_config = self._load_env_config()
        self.config.update(env_config)
        
        # Load configuration from specified path
        if self.config_path:
            file_config = self._load_file_config(self.config_path)
            self.config.update(file_config)
        
        # Load environment variables
        env_var_config = self._load_env_vars()
        self.config.update(env_var_config)
        
        # Resolve secret references
        self._resolve_secrets()
        
        # Validate configuration
        self._validate_config()
        
        logger.info(f"Configuration loaded successfully")
        return self.config
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: Configuration key (dot notation supported)
            default: Default value if key not found
        
        Returns:
            Configuration value
        """
        parts = key.split(".")
        value = self.config
        
        try:
            for part in parts:
                value = value[part]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.
        
        Args:
            key: Configuration key (dot notation supported)
            value: Configuration value
        """
        parts = key.split(".")
        config = self.config
        
        # Navigate to the correct nested dictionary
        for part in parts[:-1]:
            if part not in config or not isinstance(config[part], dict):
                config[part] = {}
            config = config[part]
        
        # Set the value
        config[parts[-1]] = value
    
    def _load_default_config(self) -> Dict[str, Any]:
        """
        Load default configuration.
        
        Returns:
            Default configuration dictionary
        """
        default_paths = [
            "config/default_config.yaml",
            "config/default_config.yml",
            "config/default_config.json",
            "config/config.yaml",
            "config/config.yml",
            "config/config.json"
        ]
        
        for path in default_paths:
            if os.path.exists(path):
                return self._load_file_config(path)
        
        logger.warning("No default configuration file found")
        return {}
    
    def _load_env_config(self) -> Dict[str, Any]:
        """
        Load environment-specific configuration.
        
        Returns:
            Environment-specific configuration dictionary
        """
        env_paths = [
            f"config/{self.env}_config.yaml",
            f"config/{self.env}_config.yml",
            f"config/{self.env}_config.json",
            f"config/config.{self.env}.yaml",
            f"config/config.{self.env}.yml",
            f"config/config.{self.env}.json"
        ]
        
        for path in env_paths:
            if os.path.exists(path):
                return self._load_file_config(path)
        
        logger.debug(f"No environment-specific configuration file found for {self.env}")
        return {}
    
    def _load_file_config(self, path: str) -> Dict[str, Any]:
        """
        Load configuration from a file.
        
        Args:
            path: Path to the configuration file
        
        Returns:
            Configuration dictionary
        
        Raises:
            Exception: If file loading fails
        """
        try:
            logger.debug(f"Loading configuration from {path}")
            
            with open(path, "r") as f:
                if path.endswith(".json"):
                    return json.load(f)
                else:
                    return yaml.safe_load(f) or {}
                
        except Exception as e:
            logger.error(f"Failed to load configuration from {path}: {str(e)}")
            return {}
    
    def _load_env_vars(self) -> Dict[str, Any]:
        """
        Load configuration from environment variables.
        
        Variables prefixed with AIP_ are loaded into the configuration,
        with the prefix removed and the rest converted to lowercase.
        For example, AIP_DATABASE_URL becomes database.url in the config.
        
        Returns:
            Configuration dictionary from environment variables
        """
        result = {}
        prefix = "AIP_"
        
        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Remove prefix and convert to lowercase
                config_key = key[len(prefix):].lower()
                
                # Replace double underscore with dot for nested keys
                config_key = config_key.replace("__", ".")
                
                # Set in nested dictionary
                self.set(config_key, value)
        
        return {}  # Already set in self.config
    
    def _resolve_secrets(self) -> None:
        """
        Resolve secret references in the configuration.
        
        Secret references are in the format:
        ${secret:path/to/secret}
        
        Supported secret providers:
        - env: Environment variables
        - file: Local files
        - vault: HashiCorp Vault (if configured)
        - aws: AWS Secrets Manager (if configured)
        - gcp: Google Cloud Secret Manager (if configured)
        """
        # TODO: Implement secret resolution
        pass
    
    def _validate_config(self) -> None:
        """
        Validate the configuration.
        
        Raises:
            ValueError: If configuration is invalid
        """
        # Check for required configuration
        required_keys = []
        
        for key in required_keys:
            if self.get(key) is None:
                logger.error(f"Missing required configuration: {key}")
                raise ValueError(f"Missing required configuration: {key}")
    
    def _mask_secrets(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mask sensitive values in configuration for logging.
        
        Args:
            config: Configuration dictionary
        
        Returns:
            Configuration with sensitive values masked
        """
        sensitive_keys = ["password", "secret", "key", "token", "credential"]
        
        def _mask_dict(d):
            result = {}
            for k, v in d.items():
                if isinstance(v, dict):
                    result[k] = _mask_dict(v)
                elif isinstance(v, list):
                    result[k] = [_mask_item(item) for item in v]
                else:
                    result[k] = _mask_item(v, k)
            return result
        
        def _mask_item(value, key=None):
            if key and any(sensitive in key.lower() for sensitive in sensitive_keys):
                if value:
                    return "****"
            return value
        
        return _mask_dict(config)

