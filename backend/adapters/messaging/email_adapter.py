"""B.O.S. Email Messaging Adapter v1.0

Delivers email over SMTP (works with Gmail, Outlook, Zoho, SES, any SMTP server).
Credentials: {host, port, username, password, from_address, use_tls?}
"""

import smtplib
import ssl
from email.message import EmailMessage
from typing import Any, Dict, Optional

from .channel_adapter import ChannelAdapter, CredentialsResolver


class EmailAdapter(ChannelAdapter):
    required_fields = ("host", "username", "password", "from_address")

    def __init__(self, name: str = "email", credentials: Optional[CredentialsResolver] = None):
        super().__init__(name=name, credentials=credentials)

    def deliver(self, creds: Dict[str, Any], recipient: str, text: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        msg = EmailMessage()
        msg["From"] = creds["from_address"]
        msg["To"] = recipient
        msg["Subject"] = str(payload.get("subject") or "A message for you")
        msg.set_content(text)

        port = int(creds.get("port") or 587)
        context = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(creds["host"], port, context=context, timeout=30) as smtp:
                smtp.login(creds["username"], creds["password"])
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(creds["host"], port, timeout=30) as smtp:
                if str(creds.get("use_tls", "true")).lower() != "false":
                    smtp.starttls(context=context)
                smtp.login(creds["username"], creds["password"])
                smtp.send_message(msg)
        return {"provider_ref": msg.get("Message-ID", "") or "smtp"}
