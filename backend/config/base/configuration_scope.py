"""B.O.S. Configuration Scope Enum v0.1

Enumeration of configuration scopes: Global, Tenant, Module, Provider, Runtime.
"""

from enum import Enum


class ConfigurationScope(str, Enum):
    GLOBAL = "GLOBAL"
    TENANT = "TENANT"
    MODULE = "MODULE"
    PROVIDER = "PROVIDER"
    RUNTIME = "RUNTIME"
