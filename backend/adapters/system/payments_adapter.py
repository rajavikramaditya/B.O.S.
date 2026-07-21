"""B.O.S. Payments Adapter v0.1

Adapter connecting platform billing capabilities to payment gateways (e.g. Stripe, Razorpay).
"""

from typing import Any, Dict
from ..base_adapter import BaseAdapter
from ..adapter_contracts import AdapterRequest, AdapterResponse, AdapterStatus


class PaymentsAdapter(BaseAdapter):
    """Adapter for Payments and billing processing."""

    def __init__(self, name: str = "payments"):
        super().__init__(name=name, channel_type="payments")

    def connect(self) -> bool:
        self.status = AdapterStatus.CONNECTED
        return True

    def disconnect(self) -> bool:
        self.status = AdapterStatus.DISCONNECTED
        return True

    def health_check(self) -> Dict[str, Any]:
        return {"adapter": self.name, "status": self.status, "reachable": True}

    def execute_request(self, request: AdapterRequest) -> AdapterResponse:
        amount = request.payload.get("amount", 0.0)
        currency = request.payload.get("currency", "INR")

        return AdapterResponse(
            success=True,
            status=self.status,
            data={
                "channel": "payments",
                "amount": amount,
                "currency": currency,
                "transaction_id": f"txn_{request.request_id}",
            },
        )
