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
		return config.get(section, parameter)
	except configparser.NoOptionError as e:
		L.warning("Configuration parameter '{}' missing in section '{}': {}".format(
			parameter, section, e))
		return None


asab.Config.add_defaults({
	'm365_email': {
		"subject": "ASAB Iris email",
	}
})


class M365EmailOutputService(asab.Service, OutputABC):
	"""
	Service for sending emails via Microsoft 365 Graph API.

	Config ([m365_email]):
	tenant_id     - Azure AD tenant ID (required)
	client_id     - Application (client) ID (required)
	client_secret - Client secret (required)
	user_email    - Sending user address (required)
	api_url       - Optional URL template: defaults to
					"https://graph.microsoft.com/v1.0/users/{}/sendMail"
	subject       - Default email subject
	"""

	def __init__(self, app, service_name="M365EmailOutputService"):
		super().__init__(app, service_name)

		cfg = asab.Config
		self.TenantID = check_config(cfg, "m365_email", "tenant_id")
		self.ClientID = check_config(cfg, "m365_email", "client_id")
		self.ClientSecret = check_config(cfg, "m365_email", "client_secret")
		self.UserEmail = check_config(cfg, "m365_email", "user_email")
		raw = check_config(cfg, "m365_email", "api_url") or "https://graph.microsoft.com/v1.0/users/{}/sendMail"
		self.APIUrl = raw.format(self.UserEmail)
		self.Subject = check_config(cfg, "m365_email", "subject")

		if not all([self.TenantID, self.ClientID, self.ClientSecret, self.UserEmail]):
			L.warning("Incomplete M365 config—disabling email service")
			self.MsalApp = None
			return

		# MSAL app for token acquisition
		self.MsalApp = msal.ConfidentialClientApplication(
			self.ClientID,
			authority="https://login.microsoftonline.com/{}".format(self.TenantID),
			client_credential=self.ClientSecret
		)

	@property
	def is_configured(self):
		return self.MsalApp is not None

	def _get_access_token(self, force_refresh=False):
		"""
		Get a valid access token, using cache unless force_refresh=True.
		"""
		if not self.MsalApp:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="MSAL client not initialized",
				error_i18n_key="Authentication misconfigured",
				error_dict={}
			)

		if not force_refresh:
			result = self.MsalApp.acquire_token_silent(
				scopes=["https://graph.microsoft.com/.default"], account=None
			)
		else:
			result = None

		if not result or "access_token" not in result:
			result = self.MsalApp.acquire_token_for_client(
				scopes=["https://graph.microsoft.com/.default"]
			)

		if "access_token" in result:
			return result["access_token"]

		L.error("Token acquisition failed: %r", result)
		raise ASABIrisError(
			ErrorCode.AUTHENTICATION_FAILED,
			tech_message="Failed to obtain token: {}".format(result),
			error_i18n_key="Could not authenticate",
			error_dict={"msal_result": result}
		)

	async def send_email(self, from_recipient, recipient, subject, body):
		if not self.is_configured:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="Email service disabled (missing config)",
				error_i18n_key="Email service unavailable",
				error_dict={}
			)

		payload = {
			"message": {
				"subject": subject or self.Subject,
				"body": {"contentType": "HTML", "content": body},
				"toRecipients": [
					{"emailAddress": {"address": recipient}}
				]
			}
		}

		def _post(token):
			headers = {
				"Authorization": "Bearer {}".format(token),
				"Content-Type": "application/json"
			}
			return requests.post(self.APIUrl, headers=headers, json=payload)

		# First attempt
		token = self._get_access_token()
		resp = _post(token)

		# Retry on expired token
		if resp.status_code == 401:
			L.info("Token expired—refreshing and retrying")
			token = self._get_access_token(force_refresh=True)
			resp = _post(token)

		if resp.status_code in (200, 202):
			L.info("Microsoft 365 email sent successfully.")
			return True

		# Any other error
		L.error("SendMail failed: %s %s", resp.status_code, resp.text)
		raise ASABIrisError(
			ErrorCode.SERVER_ERROR,
			tech_message="Graph API error {}: {}".format(
				resp.status_code, resp.text),
			error_i18n_key="Error sending email",
			error_dict={"status": resp.status_code, "body": resp.text}
		)
