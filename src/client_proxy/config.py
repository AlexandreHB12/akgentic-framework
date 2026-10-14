"""Config for a ClientProxy — a HumanProxy reachable over WhatsApp, voice or email."""

from __future__ import annotations

from akgentic.core import BaseConfig


class ClientConfig(BaseConfig):
    """BaseConfig plus the channels this client is reachable through.

    All three are optional and independent — set whichever ones are known,
    at hire time, via TrilloClientTool.hire_client. E.164 format for
    whatsapp_number/phone_number (e.g. "+32470123456"); TrilloClientTool
    prefixes whatsapp_number with "whatsapp:" itself before handing it to
    Twilio.
    """

    whatsapp_number: str | None = None
    phone_number: str | None = None
    email_address: str | None = None
