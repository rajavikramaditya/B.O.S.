"""B.O.S. Configuration Loader v0.1

Loads configuration from .env, OS environment variables, JSON, and YAML sources into normalized BaseConfiguration objects.
"""

import json
import os
from typing import Any, Dict, Type
import yaml
from .base.base_configuration import BaseConfiguration
from .base.configuration_metadata import ConfigurationMetadata
from .base.configuration_scope import ConfigurationScope
from .base.configuration_source import ConfigurationSource
from .registry import RuntimeConfigurationRegistry


class GenericConfiguration(BaseConfiguration):
    """Concrete BaseConfiguration implementation for loaded environment options."""

    def validate(self) -> bool:
        return True


class ConfigurationLoader:
    """Loader reading .env, JSON, YAML, and OS env into normalized configuration objects."""

    @classmethod
    def load_env_file(
        cls,
        filepath: str,
        name: str = "global_env",
        scope: ConfigurationScope = ConfigurationScope.GLOBAL,
    ) -> BaseConfiguration:
        values: Dict[str, Any] = {}
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        values[k.strip()] = v.strip().strip("'\"")

        meta = ConfigurationMetadata(
            name=name,
            scope=scope,
            source=ConfigurationSource.ENV_FILE,
        )
        config = GenericConfiguration(meta, values)
        RuntimeConfigurationRegistry.register(config)
        return config

    @classmethod
    def load_json(
        cls,
        content: str,
        name: str,
        scope: ConfigurationScope = ConfigurationScope.GLOBAL,
    ) -> BaseConfiguration:
        data = json.loads(content)
        meta = ConfigurationMetadata(
            name=name,
            scope=scope,
            source=ConfigurationSource.JSON_FILE,
        )
        config = GenericConfiguration(meta, data)
        RuntimeConfigurationRegistry.register(config)
        return config

    @classmethod
    def load_yaml(
        cls,
        content: str,
        name: str,
        scope: ConfigurationScope = ConfigurationScope.GLOBAL,
    ) -> BaseConfiguration:
        data = yaml.safe_load(content) or {}
        meta = ConfigurationMetadata(
            name=name,
            scope=scope,
            source=ConfigurationSource.YAML_FILE,
        )
        config = GenericConfiguration(meta, data)
        RuntimeConfigurationRegistry.register(config)
        return config
