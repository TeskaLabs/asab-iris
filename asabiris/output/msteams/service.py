import logging
import configparser
import urllib.parse

import aiohttp
import asab

from ...errors import ASABIrisError, ErrorCode
from ...output_abc import OutputABC
from ...audit import AuditLogger
from ..retry import DeliveryError, RetryPolicy, http_request

L = logging.getLogger(__name__)


def check_config(config, section, parameter):
    try:
        value = config.get(section, parameter)
        return value
    except configparser.NoOptionError as e:
        L.warning(
            "Required configuration option is missing; set it in the service configuration section.",
            struct_data={
                "config_section": section,
                "config_option": parameter,
                "error_type": e.__class__.__name__,
            },
        )
        return None


class MSTeamsOutputService(asab.Service, OutputABC):

    def __init__(self, app, service_name="MSTeamsOutputService"):
        super().__init__(app, service_name)

        # Load global configuration as defaults
        self.TeamsWebhookUrl = check_config(asab.Config, "msteams", "webhook_url")

        # If required MS Teams configuration is missing, disable MS Teams service
        if not self.TeamsWebhookUrl:
            L.warning(
                "Microsoft Teams output is disabled because webhook_url is missing in [msteams]; configure webhook_url to enable delivery.",
            )
            self.Client = None
            return

        self.ConfigService = app.get_service("TenantConfigExtractionService")

    async def send(self, body):
        """
        Sends a message to MS Teams with a provided body content.
        """
        webhook_url = self.TeamsWebhookUrl

        try:
            effective_tenant = asab.contextvars.Tenant.get()
        except LookupError:
            effective_tenant = None

        # If tenant-specific MS Teams configuration is available, fetch the webhook URL
        if effective_tenant and self.ConfigService is not None:
            try:
                webhook_url = self.ConfigService.get_msteams_config(effective_tenant)
            except KeyError:
                L.warning(
                    "Tenant-specific Microsoft Teams configuration not found; using global [msteams] webhook_url.",
                    struct_data={"tenant": effective_tenant},
                )

        if webhook_url is None:
            L.error(
                "Microsoft Teams webhook URL is missing; configure webhook_url in [msteams] or tenant configuration.",
                struct_data={"tenant": effective_tenant},
            )
            raise ASABIrisError(ErrorCode.INVALID_SERVICE_CONFIGURATION, tech_message="Teams webhook URL is missing.")

        adaptive_card = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.2",
                        "body": [
                            {
                                "type": "ColumnSet",
                                "columns": [
                                    {
                                        "type": "Column",
                                        "width": "stretch",
                                        "items": [
                                            {
                                                "type": "TextBlock",
                                                "text": body,
                                                "wrap": True
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                }
            ]
        }

        retry = RetryPolicy("msteams")
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async def send_card():
                body = await http_request(session, "POST", webhook_url, json=adaptive_card, success=(200, 202))
                # Legacy connectors can report throttling inside a successful HTTP response.
                if "Microsoft Teams endpoint returned HTTP error 429" in body:
                    raise DeliveryError(
                        "Teams connector throttled the request.", "temporary",
                        details={"provider_code": "429"},
                    )
                if body.strip() not in ("", "1"):
                    raise DeliveryError(
                        "Unrecognized Teams acknowledgement; delivery is uncertain.", "uncertain",
                        details={"provider_code": "unrecognized_acknowledgement"},
                    )
            await retry.run(send_card)
        AuditLogger.log(
            asab.LOG_NOTICE, "Microsoft Teams message sent",
            struct_data={"webhook_host": urllib.parse.urlsplit(webhook_url).hostname, "tenant": effective_tenant},
        )
        return True
