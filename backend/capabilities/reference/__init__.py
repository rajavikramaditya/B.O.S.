"""B.O.S. Reference Capabilities Package v0.1

Reference implementations proving the Capability Framework architecture.
"""

from .generate_text_capability import GenerateTextCapability
from .store_document_capability import StoreDocumentCapability
from .send_message_capability import SendMessageCapability

__all__ = [
    "GenerateTextCapability",
    "StoreDocumentCapability",
    "SendMessageCapability",
]
