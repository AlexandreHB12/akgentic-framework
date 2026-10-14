"""TrilloClientTool — hire a reachable Client, and contact them, via Twilio.

The recipient isn't a phone number or email address the calling agent has
to know at message time — it's another Akgent in the team (the "Client"
role, a ClientProxy — see agent.py), discovered by role through the
orchestrator's agent-profile registry, the same registry hire_members
reads.

The generic hire_members tool only takes a role name — there is no way to
pass per-hire configuration through it. hire_client exists because the
Client's WhatsApp number, phone number and email address are exactly that:
known only at hire time, from whatever the caller (a human, via chat)
actually said. It mirrors akgentic.tool.team.team's own hire logic
(resolve the card, check can_be_hired, get_config_copy, createActor,
on_hire) with one addition — the copied config's channel fields are set
from whichever arguments were given before the actor is created.

Two DIFFERENT credential sets are involved, because messaging/voice and
email are different Twilio products:
- TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN — the core Twilio REST API, used
  for both send_whatsapp_message and make_call.
- TWILIO_WHATSAPP_FROM overrides the WhatsApp sender; it defaults to
  Twilio's own public Sandbox number (+14155238886) — not a secret; the
  recipient must have already texted the sandbox's "join <code>" phrase to
  opt in, a one-time step this tool has no part in.
- TWILIO_WHATSAPP_CONTENT_SID switches send_whatsapp_message from free-form
  Body text to a pre-approved Content API template (Twilio/Meta require a
  template for any business-initiated message outside the Sandbox or a
  24-hour customer-reply window — a free-form Body is otherwise rejected
  with "ContentSid Required"). When set, send_whatsapp_message sends that
  template instead of the given message text; template_variables fills in
  the template's placeholders, if it has any.
- TWILIO_VOICE_FROM is the Twilio phone number make_call dials from — the
  WhatsApp Sandbox number cannot place voice calls, so there is no
  sensible default; it must be a real Twilio voice-capable number.
- TWILIO_SMS_FROM is the Twilio phone number send_sms texts from; it falls
  back to TWILIO_VOICE_FROM if unset, since one Twilio number is usually
  enabled for both. Plain SMS (unlike WhatsApp) has no session-window or
  template requirement — it always sends free-form text — so this is the
  simplest channel to get working.
- SENDGRID_API_KEY / SENDGRID_FROM_EMAIL — Twilio SendGrid, a separate
  product with its own API key, used only by send_email.

Never put any of these credentials in a catalog entry.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from xml.sax.saxutils import escape

import httpx
from akgentic.core import Akgent, Orchestrator
from akgentic.tool.core import TOOL_CALL, BaseToolParam, Channels, ToolCard, _resolve
from akgentic.tool.errors import RetriableError
from akgentic.tool.team.observer import TeamManagementToolObserver

from .agent import ClientProxy

_TWILIO_SANDBOX_FROM = "+14155238886" # This seems to be the same always.
_TWILIO_MESSAGES_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
_TWILIO_CALLS_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json"
_SENDGRID_MAIL_URL = "https://api.sendgrid.com/v3/mail/send"


def _is_unset(value: str | None) -> bool:
    """True for None, empty, or an all-zero placeholder (e.g. "+00000000000")."""
    if not value:
        return True
    digits = value.lstrip("+")
    return not digits or digits == "0" * len(digits)


class HireClient(BaseToolParam):
    """Parameters for the hire-the-client capability."""

    expose: set[Channels] = {TOOL_CALL}


class SendWhatsAppMessage(BaseToolParam):
    """Parameters for the send-WhatsApp-message capability."""

    expose: set[Channels] = {TOOL_CALL}


class SendEmail(BaseToolParam):
    """Parameters for the send-email capability."""

    expose: set[Channels] = {TOOL_CALL}


class MakeCall(BaseToolParam):
    """Parameters for the make-a-call capability."""

    expose: set[Channels] = {TOOL_CALL}


class SendSms(BaseToolParam):
    """Parameters for the send-SMS capability."""

    expose: set[Channels] = {TOOL_CALL}


class UpdateContactInfo(BaseToolParam):
    """Parameters for the update-contact-info capability."""

    expose: set[Channels] = {TOOL_CALL}


class TrilloClientTool(ToolCard):
    """Hire the team's reachable "Client" role, and contact them, via Twilio.

    target_role names the AgentCard (a ClientProxy) this tool hires and
    contacts — set it to match whichever role your team gave that agent.
    """

    target_role: str = "Client"
    hire_client: HireClient | bool = True
    send_whatsapp_message: SendWhatsAppMessage | bool = True
    send_email: SendEmail | bool = True
    make_call: MakeCall | bool = True
    send_sms: SendSms | bool = True
    update_contact_info: UpdateContactInfo | bool = True

    def observer(self, observer: TeamManagementToolObserver) -> TrilloClientTool:
        if observer.orchestrator is None:
            raise ValueError("TrilloClientTool requires access to the orchestrator.")
        super().observer(observer)
        return self

    def get_tools(self) -> list[Callable]:
        tools: list[Callable] = []
        hire_params = _resolve(self.hire_client, HireClient)
        if hire_params and TOOL_CALL in hire_params.expose:
            tools.append(self._hire_client_factory(hire_params))
        whatsapp_params = _resolve(self.send_whatsapp_message, SendWhatsAppMessage)
        if whatsapp_params and TOOL_CALL in whatsapp_params.expose:
            tools.append(self._send_whatsapp_factory(whatsapp_params))
        email_params = _resolve(self.send_email, SendEmail)
        if email_params and TOOL_CALL in email_params.expose:
            tools.append(self._send_email_factory(email_params))
        call_params = _resolve(self.make_call, MakeCall)
        if call_params and TOOL_CALL in call_params.expose:
            tools.append(self._make_call_factory(call_params))
        sms_params = _resolve(self.send_sms, SendSms)
        if sms_params and TOOL_CALL in sms_params.expose:
            tools.append(self._send_sms_factory(sms_params))
        update_params = _resolve(self.update_contact_info, UpdateContactInfo)
        if update_params and TOOL_CALL in update_params.expose:
            tools.append(self._update_contact_factory(update_params))
        return tools

    def _get_live_config(self, observer: TeamManagementToolObserver):
        """Return the currently-hired Client's actual config, or None if not hired.

        get_agent_profile(role) resolves the static catalog template — the
        same one hire_client copies from before setting channel fields on
        the copy — so it never reflects what was actually set at hire time.
        The only way to read the live values is to find the hired actor's
        address via get_team() and proxy_ask *that address* for its config.
        """
        orchestrator_proxy = observer.proxy_ask(observer.orchestrator, Orchestrator)
        member = next(
            (m for m in orchestrator_proxy.get_team() if m.role == self.target_role), None
        )
        if member is None:
            return None
        return observer.proxy_ask(member, Akgent).config

    def _hire_client_factory(self, params: HireClient) -> Callable:
        target_role = self.target_role
        observer: TeamManagementToolObserver = self._observer  # type: ignore[assignment]

        def hire_client(
            name: str,
            whatsapp_number: str | None = None,
            phone_number: str | None = None,
            email_address: str | None = None,
        ) -> str:
            """Bring the team's reachable Client into the team.

            Unlike hire_members, this names the hired agent after the actual
            person and sets whichever contact channels are given — use this
            instead of hire_members whenever a client is being brought in by
            name (e.g. "invite client Matt into the conversation") or with
            any contact detail (e.g. "bring the client into the team, Matt,
            at +3294393233 on WhatsApp and matt@example.com by email"). The
            hired agent is displayed as "@<role> - <name>" (e.g.
            "@Client - Matt"), never a generic id.

            Args:
                name: The person's name, as given in the request (e.g. "Matt").
                whatsapp_number: The Client's WhatsApp number, E.164 format
                    (e.g. "+3294393233"), if given.
                phone_number: The Client's phone number for voice calls,
                    E.164 format, if given (may be the same as whatsapp_number).
                email_address: The Client's email address, if given.

            Calling this again once the Client is already hired does not
            create a second one — it reports the existing agent instead, so
            it is always safe to call whenever a client needs to be
            reached, without first checking whether they were hired already.

            Returns:
                A confirmation string naming the hired (or already-hired)
                agent and which channels are now configured.

            Raises:
                RetriableError: If no agent is registered under target_role,
                    or that role's card is not marked can_be_hired.
            """
            orchestrator_proxy = observer.proxy_ask(observer.orchestrator, Orchestrator)
            existing = next(
                (m for m in orchestrator_proxy.get_team() if m.role == target_role), None
            )
            if existing is not None:
                return (
                    f"{target_role} is already hired as {existing.name} — reusing that "
                    f"agent (contact channels are only set at hire time, not updated here)."
                )

            card = orchestrator_proxy.get_agent_profile(target_role)
            if card is None:
                raise RetriableError(
                    f"Hire error - cannot find agent card for role '{target_role}'."
                )
            if not card.can_be_hired:
                raise RetriableError(f"Hire error - role '{target_role}' cannot be hired.")

            actor_class = card.get_agent_class()
            if isinstance(actor_class, str):
                raise RetriableError(
                    f"Hire error - agent class for role '{target_role}' is a string, not a type."
                )

            config = card.get_config_copy()
            if whatsapp_number:
                config.whatsapp_number = whatsapp_number  # type: ignore[attr-defined]
            if phone_number:
                config.phone_number = phone_number  # type: ignore[attr-defined]
            if email_address:
                config.email_address = email_address  # type: ignore[attr-defined]
            child_name = f"@{target_role} - {name}"
            config.name = child_name
            config.role = target_role

            address = observer.createActor(actor_class, config=config)
            observer.on_hire(address)

            channels = [
                label
                for label, value in (
                    ("WhatsApp", whatsapp_number),
                    ("phone", phone_number),
                    ("email", email_address),
                )
                if value
            ]
            if channels:
                return f"Hired {target_role} as {child_name}, reachable via {', '.join(channels)}."
            return f"Hired {target_role} as {child_name} (no contact channel set yet)."

        hire_client.__doc__ = params.format_docstring(hire_client.__doc__)
        return hire_client

    def _send_whatsapp_factory(self, params: SendWhatsAppMessage) -> Callable:
        target_role = self.target_role
        observer: TeamManagementToolObserver = self._observer  # type: ignore[assignment]

        def send_whatsapp_message(
            message: str, template_variables: dict[str, str] | None = None
        ) -> str:
            """Send a WhatsApp message to the team's Client.

            The Client must already be hired with a whatsapp_number (see
            hire_client) — this looks them up by role rather than taking a
            phone number.

            If TWILIO_WHATSAPP_CONTENT_SID is set, this sends that
            pre-approved template instead of free-form text — required for
            any business-initiated WhatsApp message outside the Sandbox or
            a 24-hour customer-reply window ("ContentSid Required" is
            Twilio's error otherwise). In that mode, `message` is ignored
            and template_variables fills the template's placeholders
            (omit it if the template has none — the numbered keys, e.g.
            "1", "2", must match the template's own placeholder numbers,
            found in the Twilio Console's Content Editor).

            Args:
                message: The text to send. Ignored if a Content template is
                    configured (TWILIO_WHATSAPP_CONTENT_SID is set).
                template_variables: Values for the configured template's
                    numbered placeholders (e.g. {"1": "Matt"}), if it has
                    any. Ignored when no template is configured.

            Returns:
                A confirmation string once Twilio accepts the message.

            Raises:
                RetriableError: If the Client hasn't been hired yet, has no
                    whatsapp_number, Twilio credentials are missing, or
                    Twilio rejects the request.
            """
            config = self._get_live_config(observer)
            if config is None:
                raise RetriableError(
                    f"No agent registered under role '{target_role}' — call hire_client first."
                )
            to_number = getattr(config, "whatsapp_number", None)
            if _is_unset(to_number):
                raise RetriableError(
                    f"Agent '{target_role}' has no whatsapp_number configured — "
                    f"call hire_client with a whatsapp_number first."
                )

            account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
            auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
            if not account_sid or not auth_token:
                raise RetriableError("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN are not set.")
            from_number = os.environ.get("TWILIO_WHATSAPP_FROM", _TWILIO_SANDBOX_FROM)
            content_sid = os.environ.get("TWILIO_WHATSAPP_CONTENT_SID")

            data = {
                "From": f"whatsapp:{from_number}",
                "To": f"whatsapp:{to_number}",
            }
            if content_sid:
                data["ContentSid"] = content_sid
                if template_variables:
                    data["ContentVariables"] = json.dumps(template_variables)
            else:
                data["Body"] = message

            response = httpx.post(
                _TWILIO_MESSAGES_URL.format(sid=account_sid),
                auth=(account_sid, auth_token),
                data=data,
                timeout=15.0,
            )
            if response.is_error:
                raise RetriableError(f"Twilio rejected the message: {response.text}")
            return f"WhatsApp message sent to {target_role} ({to_number})."

        send_whatsapp_message.__doc__ = params.format_docstring(send_whatsapp_message.__doc__)
        return send_whatsapp_message

    def _send_email_factory(self, params: SendEmail) -> Callable:
        target_role = self.target_role
        observer: TeamManagementToolObserver = self._observer  # type: ignore[assignment]

        def send_email(subject: str, message: str) -> str:
            """Send an email to the team's Client, via Twilio SendGrid.

            The Client must already be hired with an email_address (see
            hire_client). Requires SENDGRID_API_KEY / SENDGRID_FROM_EMAIL —
            a separate Twilio SendGrid credential, distinct from the
            TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN used for WhatsApp/calls.

            Args:
                subject: The email subject line.
                message: The plain-text email body.

            Returns:
                A confirmation string once SendGrid accepts the email.

            Raises:
                RetriableError: If the Client hasn't been hired yet, has no
                    email_address, SendGrid credentials are missing, or
                    SendGrid rejects the request.
            """
            config = self._get_live_config(observer)
            if config is None:
                raise RetriableError(
                    f"No agent registered under role '{target_role}' — call hire_client first."
                )
            to_email = getattr(config, "email_address", None)
            if _is_unset(to_email):
                raise RetriableError(
                    f"Agent '{target_role}' has no email_address configured — "
                    f"call hire_client with an email_address first."
                )

            api_key = os.environ.get("SENDGRID_API_KEY")
            from_email = os.environ.get("SENDGRID_FROM_EMAIL")
            if not api_key or not from_email:
                raise RetriableError("SENDGRID_API_KEY / SENDGRID_FROM_EMAIL are not set.")

            response = httpx.post(
                _SENDGRID_MAIL_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "personalizations": [{"to": [{"email": to_email}]}],
                    "from": {"email": from_email},
                    "subject": subject,
                    "content": [{"type": "text/plain", "value": message}],
                },
                timeout=15.0,
            )
            if response.is_error:
                raise RetriableError(f"SendGrid rejected the email: {response.text}")
            return f"Email sent to {target_role} ({to_email})."

        send_email.__doc__ = params.format_docstring(send_email.__doc__)
        return send_email

    def _make_call_factory(self, params: MakeCall) -> Callable:
        target_role = self.target_role
        observer: TeamManagementToolObserver = self._observer  # type: ignore[assignment]

        def make_call(message: str) -> str:
            """Call the team's Client and read them a message aloud, via Twilio Voice.

            The Client must already be hired with a phone_number (see
            hire_client). Requires TWILIO_VOICE_FROM — a real Twilio
            voice-capable number; the WhatsApp Sandbox number cannot place
            calls, so there is no default to fall back to.

            Args:
                message: The text Twilio's voice synthesizer reads aloud
                    when the call connects.

            Returns:
                A confirmation string once Twilio accepts the call request.

            Raises:
                RetriableError: If the Client hasn't been hired yet, has no
                    phone_number, Twilio credentials (including
                    TWILIO_VOICE_FROM) are missing, or Twilio rejects the
                    request.
            """
            config = self._get_live_config(observer)
            if config is None:
                raise RetriableError(
                    f"No agent registered under role '{target_role}' — call hire_client first."
                )
            to_number = getattr(config, "phone_number", None)
            if _is_unset(to_number):
                raise RetriableError(
                    f"Agent '{target_role}' has no phone_number configured — "
                    f"call hire_client with a phone_number first."
                )

            account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
            auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
            if not account_sid or not auth_token:
                raise RetriableError("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN are not set.")
            from_number = os.environ.get("TWILIO_VOICE_FROM")
            if not from_number:
                raise RetriableError(
                    "TWILIO_VOICE_FROM is not set — the WhatsApp Sandbox number cannot "
                    "place voice calls, a real Twilio voice-capable number is required."
                )

            twiml = f"<Response><Say>{escape(message)}</Say></Response>"
            response = httpx.post(
                _TWILIO_CALLS_URL.format(sid=account_sid),
                auth=(account_sid, auth_token),
                data={
                    "From": from_number,
                    "To": to_number,
                    "Twiml": twiml,
                },
                timeout=15.0,
            )
            if response.is_error:
                raise RetriableError(f"Twilio rejected the call: {response.text}")
            return f"Call placed to {target_role} ({to_number})."

        make_call.__doc__ = params.format_docstring(make_call.__doc__)
        return make_call

    def _send_sms_factory(self, params: SendSms) -> Callable:
        target_role = self.target_role
        observer: TeamManagementToolObserver = self._observer  # type: ignore[assignment]

        def send_sms(message: str) -> str:
            """Send a plain SMS text message to the team's Client, via Twilio.

            The Client must already be hired with a phone_number (see
            hire_client) — the same number make_call uses. Unlike WhatsApp,
            plain SMS has no session-window or approved-template
            requirement — it always sends free-form text.

            Args:
                message: The text to send.

            Returns:
                A confirmation string once Twilio accepts the message.

            Raises:
                RetriableError: If the Client hasn't been hired yet, has no
                    phone_number, Twilio credentials are missing, or Twilio
                    rejects the request.
            """
            config = self._get_live_config(observer)
            if config is None:
                raise RetriableError(
                    f"No agent registered under role '{target_role}' — call hire_client first."
                )
            to_number = getattr(config, "phone_number", None)
            if _is_unset(to_number):
                raise RetriableError(
                    f"Agent '{target_role}' has no phone_number configured — "
                    f"call hire_client with a phone_number first."
                )

            account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
            auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
            if not account_sid or not auth_token:
                raise RetriableError("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN are not set.")
            from_number = os.environ.get("TWILIO_SMS_FROM") or os.environ.get("TWILIO_VOICE_FROM")
            if not from_number:
                raise RetriableError(
                    "TWILIO_SMS_FROM (or TWILIO_VOICE_FROM) is not set — a real Twilio "
                    "SMS-capable number is required."
                )

            response = httpx.post(
                _TWILIO_MESSAGES_URL.format(sid=account_sid),
                auth=(account_sid, auth_token),
                data={
                    "From": from_number,
                    "To": to_number,
                    "Body": message,
                },
                timeout=15.0,
            )
            if response.is_error:
                raise RetriableError(f"Twilio rejected the SMS: {response.text}")
            return f"SMS sent to {target_role} ({to_number})."

        send_sms.__doc__ = params.format_docstring(send_sms.__doc__)
        return send_sms

    def _update_contact_factory(self, params: UpdateContactInfo) -> Callable:
        target_role = self.target_role
        observer: TeamManagementToolObserver = self._observer  # type: ignore[assignment]

        def update_contact_info(
            whatsapp_number: str | None = None,
            phone_number: str | None = None,
            email_address: str | None = None,
        ) -> str:
            """Update the already-hired Client's contact channels.

            Unlike hire_client, this changes an EXISTING Client's contact
            details rather than setting them at hire time — use this when
            asked to change, update or correct a channel after the Client
            is already part of the team. Only the channels given are
            changed; omit any you don't want to touch.

            Args:
                whatsapp_number: The Client's new WhatsApp number, E.164
                    format, if changing it.
                phone_number: The Client's new phone number (used for both
                    voice calls and SMS), E.164 format, if changing it.
                email_address: The Client's new email address, if changing it.

            Returns:
                A confirmation string naming which channels were updated.

            Raises:
                RetriableError: If the Client hasn't been hired yet.
            """
            orchestrator_proxy = observer.proxy_ask(observer.orchestrator, Orchestrator)
            member = next(
                (m for m in orchestrator_proxy.get_team() if m.role == target_role), None
            )
            if member is None:
                raise RetriableError(
                    f"No agent registered under role '{target_role}' — call hire_client first."
                )
            return observer.proxy_ask(member, ClientProxy).update_contact_info(
                whatsapp_number=whatsapp_number,
                phone_number=phone_number,
                email_address=email_address,
            )

        update_contact_info.__doc__ = params.format_docstring(update_contact_info.__doc__)
        return update_contact_info
