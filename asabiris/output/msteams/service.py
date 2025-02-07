import logging
import configparser
import aiohttp
import asab
from ...errors import ASABIrisError, ErrorCode
from ...output_abc import OutputABC

L = logging.getLogger(__name__)

def check_config(config, section, parameter):
    try:
        value = config.get(section, parameter)
        return value
    except configparser.NoOptionError as e:
        L.error("Configuration parameter '{}' is missing in section '{}': {}".format(parameter, section, e))
        return None

class MSTeamsOutputService(asab.Service, OutputABC):

    def __init__(self, app, service_name="MSTeamsOutputService"):
        super().__init__(app, service_name)

        # Load global configuration as defaults
        self.TeamsWebhookUrl = check_config(asab.Config, "msteams", "webhook_url")

        # If required MS Teams configuration is missing, disable MS Teams service
        if not self.TeamsWebhookUrl:
            L.warning("MS Teams output service is not properly configured. Disabling MS Teams service.")
            self.Client = None
            app.SendMSTeamsOrchestrator = None  # Set to None so that it isn't used elsewhere
            return

        self.ConfigService = app.get_service("TenantConfigExtractionService")

    async def send(self, body, tenant):
        """
        Sends a message to MS Teams with a provided body content.
        """
        webhook_url = self.TeamsWebhookUrl

        # If tenant-specific MS Teams configuration is available, fetch the webhook URL
        if tenant:
            try:
                webhook_url = self.ConfigService.get_msteams_config(tenant)
            except KeyError:
                L.warning("Tenant-specific MS Teams configuration not found for '{}'. Using global config.".format(tenant))

        if webhook_url is None:
            L.error("MS Teams webhook URL is missing.")
            return

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

        # Sending the message to MS Teams using aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=adaptive_card) as resp:
                if resp.status == 200:
                    L.log(asab.LOG_NOTICE, "MS Teams message sent successfully.")
                    return True
                else:
                    error_message = await resp.text()
                    L.warning(
                        "Sending alert to MS Teams was NOT successful. Response status: {}, response: {}".format(
                            resp.status, error_message)
                    )

                    # Mapping specific status codes to error codes
                    if resp.status == 400:  # Bad Request
                        error_code = ErrorCode.INVALID_SERVICE_CONFIGURATION
                    elif resp.status == 404:  # Not Found
                        error_code = ErrorCode.TEMPLATE_NOT_FOUND
                    elif resp.status == 503:  # Service Unavailable
                        error_code = ErrorCode.SERVER_ERROR
                    else:
                        error_code = ErrorCode.SERVER_ERROR  # General server error for other cases

                    raise ASABIrisError(
                        error_code,
                        tech_message="Error encountered sending message to MS Teams. Status: {}, Reason: {}".format(
                            resp.status, error_message),
                        error_i18n_key="Error occurred while sending message to MS Teams. Reason: '{{error_message}}'.",
                        error_dict={
                            "error_message": error_message,
                        }
                    )
