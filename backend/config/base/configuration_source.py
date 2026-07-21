"""B.O.S. Configuration Source Enum v0.1

Enumeration of configuration sources: ENV_FILE, SYSTEM_ENV, JSON_FILE, YAML_FILE, MEMORY, INJECTED.
"""

from enum import Enum


class ConfigurationSource(str, Enum):
    ENV_FILE = "ENV_FILE"
    SYSTEM_ENV = "SYSTEM_ENV"
    JSON_FILE = "JSON_FILE"
    YAML_FILE = "YAML_FILE"
    MEMORY = "MEMORY"
    INJECTED = "INJECTED"
