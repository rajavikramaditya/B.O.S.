"""B.O.S. Storage Adapter v0.1

Adapter connecting document/asset capabilities to local file system or cloud storage (S3/GCS).
"""

from typing import Any, Dict
from ..base_adapter import BaseAdapter
from ..adapter_contracts import AdapterRequest, AdapterResponse, AdapterStatus


class StorageAdapter(BaseAdapter):
    """Adapter for Storage operations (upload, download, archival)."""

    def __init__(self, name: str = "storage"):
        super().__init__(name=name, channel_type="storage")

    def connect(self) -> bool:
        self.status = AdapterStatus.CONNECTED
        return True

    def disconnect(self) -> bool:
        self.status = AdapterStatus.DISCONNECTED
        return True

    def health_check(self) -> Dict[str, Any]:
        return {"adapter": self.name, "status": self.status, "reachable": True}

    def execute_request(self, request: AdapterRequest) -> AdapterResponse:
        path = request.payload.get("path") or request.payload.get("document_name", "doc.txt")
        action = request.action

        return AdapterResponse(
            success=True,
            status=self.status,
            data={
                "channel": "storage",
                "storage_path": path,
                "action": action,
                "file_id": f"file_{request.request_id}",
            },
        )
