"""HumanProxy variant whose config carries the channels a client is reachable through."""

from __future__ import annotations

from akgentic.agent import HumanProxy
from akgentic.core import Akgent, BaseState

from .config import ClientConfig


class ClientProxy(HumanProxy, Akgent[ClientConfig, BaseState]):
    """A HumanProxy discoverable by role, reachable over WhatsApp, voice or email.

    Behaves exactly like HumanProxy — chat still works normally. This only
    widens its config so TrilloClientTool can resolve
    ``config.whatsapp_number`` / ``config.phone_number`` / ``config.email_address``
    after looking the agent up by role through the orchestrator's
    agent-profile registry (the same registry hire_members reads), instead
    of any calling agent needing to know those directly.
    """

    def update_contact_info(
        self,
        whatsapp_number: str | None = None,
        phone_number: str | None = None,
        email_address: str | None = None,
    ) -> str:
        """Update whichever contact channels are given, leaving the rest unchanged.

        A plain method, not a receiveMsg_ handler — called remotely via
        proxy_ask/proxy_tell (mirrors Akgent.update_state()), so pykka runs
        it inside this actor's own thread. Mutating self.config directly
        from outside this method (e.g. through a proxy's returned config
        object) would race this actor's own thread instead.
        """
        changed: list[str] = []
        if whatsapp_number:
            self.config.whatsapp_number = whatsapp_number
            changed.append("WhatsApp number")
        if phone_number:
            self.config.phone_number = phone_number
            changed.append("phone number")
        if email_address:
            self.config.email_address = email_address
            changed.append("email address")
        if not changed:
            return "No contact channel given — nothing changed."
        return f"Updated: {', '.join(changed)}."
