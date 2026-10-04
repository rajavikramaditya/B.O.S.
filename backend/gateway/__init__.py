"""B.O.S. Gateway Package v1.0

Single entrance through which every interface reaches the Runtime.
"""

from .runtime_gateway import RuntimeGateway

__all__ = ["RuntimeGateway"]
