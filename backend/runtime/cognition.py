"""B.O.S. Runtime Cognition v1.0

The Runtime's single doorway to AI reasoning. It calls the `generate_text`
capability (never a provider), and exposes the capability catalog the AI may plan with.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

PLANNER_VISIBLE = "planner_visible"
ACTION_RISK = "action_risk"
ACTION_PARAMS = "action_params"
SELF_SERVICE = "self_service"
RISK_LEVELS = ("read", "safe", "external", "sensitive")
AI_UNAVAILABLE = "ai_unavailable"
AI_FAILED = "ai_failed"


class RuntimeCognition:
    """Structured AI calls made on behalf of Runtime stages."""

    @staticmethod
    def think(
        system: str,
        messages: List[Dict[str, str]],
        json_schema: Optional[Dict[str, Any]] = None,
        correlation_id: str = "",
        effort: str = "medium",
        max_tokens: int = 6000,
    ) -> Tuple[Optional[Dict[str, Any]], str, Optional[str]]:
        """Returns (data_or_None, text, error)."""
        from capabilities.base.capability_context import CapabilityContext
        from capabilities.resolver import CapabilityResolver

        ctx = CapabilityContext(module_id="runtime")
        if correlation_id:
            ctx.correlation_id = correlation_id
        result = CapabilityResolver.execute(
            "generate_text",
            "generate",
            {
                "system": system,
                "messages": messages,
                "json_schema": json_schema,
                "effort": effort,
                "max_tokens": max_tokens,
            },
            ctx,
        )
        payload = result.data or {}
        if not result.success:
            if not payload.get("provider"):
                return None, "", f"{AI_UNAVAILABLE}: no AI provider is connected."
            return None, "", f"{AI_FAILED}: {result.error or payload.get('error') or 'unknown error'}"
        return payload.get("data"), str(payload.get("text") or ""), None

    @staticmethod
    def capability_catalog() -> List[Dict[str, Any]]:
        """Capabilities the planner may use, with each action's risk and parameters."""
        from capabilities.registry import RuntimeCapabilityRegistry

        catalog = []
        for entry in RuntimeCapabilityRegistry.list_enabled():
            config = (entry.get("metadata") or {}).get("configuration") or {}
            if not config.get(PLANNER_VISIBLE):
                continue
            risks = config.get(ACTION_RISK) or {}
            params = config.get(ACTION_PARAMS) or {}
            catalog.append(
                {
                    "capability": entry["name"],
                    "description": (entry.get("metadata") or {}).get("description", ""),
                    "actions": [
                        {"action": a, "risk": risks.get(a, "external"), "params": params.get(a, {})}
                        for a in entry.get("supported_actions", [])
                        if a in risks
                    ],
                }
            )
        return catalog

    @staticmethod
    def action_risk(capability: str, action: str) -> Optional[str]:
        """Risk declared by the capability; None when the capability/action is not plannable."""
        from capabilities.registry import RuntimeCapabilityRegistry

        cap = RuntimeCapabilityRegistry.get(capability)
        if cap is None or not cap.supports_action(action):
            return None
        config = cap.metadata.configuration or {}
        if not config.get(PLANNER_VISIBLE):
            return None
        risk = (config.get(ACTION_RISK) or {}).get(action)
        return risk if risk in RISK_LEVELS else None

    @staticmethod
    def self_service_param(capability: str, action: str) -> Optional[str]:
        """Parameter a customer may only set to their own contact id; None if not self-service."""
        from capabilities.registry import RuntimeCapabilityRegistry

        cap = RuntimeCapabilityRegistry.get(capability)
        if cap is None:
            return None
        value = ((cap.metadata.configuration or {}).get(SELF_SERVICE) or {}).get(action)
        return str(value) if value else None

    @staticmethod
    def parse_params(raw: Any) -> Dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if not raw:
            return {}
        try:
            parsed = json.loads(str(raw))
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            return {}
