import logging
import configparser
import asab
import requests
import msal
from ...errors import ASABIrisError, ErrorCode
from ...output_abc import OutputABC

L = logging.getLogger(__name__)

def check_config(config, section, parameter):
    try:
        value = config.get(section, parameter)
        return value
    except configparser.NoOptionError as e:
        L.warning("Configuration parameter '{}' is missing in section '{}': {}".format(parameter, section, e))
        return None

class M365EmailOutputService(asab.Service, OutputABC):
    """
    Service for sending emails using Microsoft 365.
    This service directly calls requests.post to send email via the Microsoft Graph API.
    """
    def __init__(self, app, service_name="M365EmailOutputService"):
        super().__init__(app, service_name)

        # Load configuration from the global asab.Config.
        self.tenant_id = check_config(asab.Config, "m365_email", "tenant_id")
        self.client_id = check_config(asab.Config, "m365_email", "client_id")
        self.client_secret = check_config(asab.Config, "m365_email", "client_secret")
        self.user_email = check_config(asab.Config, "m365_email", "user_email")

        # If any required configuration is missing, disable the service.
        if not all([self.tenant_id, self.client_id, self.client_secret, self.user_email]):
            L.warning("Microsoft 365 Email configuration is missing. Disabling M365 Email service.")
            self.token = None
            return

        # Define the Microsoft Graph API endpoint for sending email.
        self.api_url = "https://graph.microsoft.com/v1.0/me/sendMail"

        # Retrieve the access token.
        self.token = self._get_access_token()

    def _get_access_token(self):
        """
        Retrieves an access token using MSAL's ConfidentialClientApplication.
        """
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority="https://login.microsoftonline.com/{}".format(self.tenant_id),
            client_credential=self.client_secret
        )
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" in result:
            return result["access_token"]
        else:
            raise Exception(f"Failed to obtain access token: {result}")

    async def send_email(self, recipient, subject, body):
        """
        Asynchronously sends an email to the specified recipient by directly calling
        requests.post to the Microsoft Graph API.
        """
        if self.token is None:
            L.error("M365 Email service is not properly configured (missing token).")
            return

        headers = {
            "Authorization": "Bearer {}".format(self.token),
            "Content-Type": "application/json"
        }
        payload = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": body
                },
                "toRecipients": [
                    {"emailAddress": {"address": recipient}}
                ]
            }
        }
        try:
            response = requests.post(self.api_url, headers=headers, json=payload)
            if response.status_code == 202:
                L.info("Microsoft 365 email sent successfully.")
                return True
            else:
                error_message = "Failed to send email: {} {}".format(response.status_code, response.text)
                L.error(error_message)
                raise Exception(error_message)
        except Exception as e:
            L.error("Error sending Microsoft 365 email: {}".format(e))
            raise ASABIrisError(
                ErrorCode.SERVER_ERROR,
                tech_message="Error sending email via Microsoft 365: {}".format(e),
                error_i18n_key="Error occurred while sending email.",
                error_dict={"error_message": str(e)}
            )
