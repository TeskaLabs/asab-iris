import logging
import configparser
import asab
import msal
import requests
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
    Service for sending emails using Microsoft 365 Graph API.

    Configuration (in [m365_email] section of asab.Config):
      tenant_id     - Azure AD tenant ID (required)
      client_id     - Application (client) ID (required)
      client_secret - Client secret for the app (required)
      user_email    - Email address of the sending user (required)
      api_url       - (optional) Full API URL template for sending mail.
                      May include a '{}' placeholder for the user email.
                      Defaults to "https://graph.microsoft.com/v1.0/users/{}/sendMail"
    """
    def __init__(self, app, service_name="M365EmailOutputService"):
        super().__init__(app, service_name)

        # Load configuration
        self.TenantID = check_config(asab.Config, "m365_email", "tenant_id")
        self.ClientID = check_config(asab.Config, "m365_email", "client_id")
        self.ClientSecret = check_config(asab.Config, "m365_email", "client_secret")
        self.UserEmail = check_config(asab.Config, "m365_email", "user_email")
        self.RawAPIUrl = check_config(asab.Config, "m365_email", "api_url")

        # If any required configuration is missing, disable the service.
        if not all([self.TenantID, self.ClientID, self.ClientSecret, self.UserEmail]):
            L.warning("Microsoft 365 Email configuration is incomplete. Disabling M365 Email service.")
            self.Token = None
            return

        self.APIUrl = self.RawAPIUrl.format(self.UserEmail)

        # Retrieve the access token using client credentials flow.
        self.Token = self._get_access_token()

    @property
    def is_configured(self) -> bool:
        """True if all 4 required config values were found and non-empty."""
        return bool(self.TenantID and self.ClientID and self.ClientSecret and self.UserEmail)

    def _get_access_token(self):
        """
        Retrieves an access token using MSAL's ConfidentialClientApplication (client credentials flow).
        """
        app = msal.ConfidentialClientApplication(
            self.ClientID,
            authority="https://login.microsoftonline.com/{}".format(self.TenantID),
            client_credential=self.ClientSecret
        )

        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" in result:
            return result["access_token"]
        else:
            raise Exception("Failed to obtain access token: {}".format(result))

    async def send_email(self, from_recipient, recipient, subject, body):
        """
        Asynchronously sends an email to the specified recipient by directly calling
        requests.post to the Microsoft Graph API.
        """
        if self.Token is None:
            L.error("M365 Email service is not properly configured (missing token).")
            return

        if from_recipient is None:
            recipient = self.UserEmail

        headers = {
            "Authorization": "Bearer {}".format(self.Token),
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
            response = requests.post(self.APIUrl, headers=headers, json=payload)
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
