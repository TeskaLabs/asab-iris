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

	async def send_email(self, from_recipient, recipient, subject, body, content_type="HTML"):
		if not self.is_configured:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="Email service disabled (missing config)",
				error_i18n_key="Email service unavailable",
				error_dict={}
			)

		# 1) Determine which mailbox to send from
		#    If caller passed from_recipient, use that; otherwise use the configured UserEmail.
		actual_from = from_recipient or self.UserEmail
		api_url = "https://graph.microsoft.com/v1.0/users/{}/sendMail".format(actual_from)

		# 2) Build the payload exactly the same as before:
		payload = {
			"message": {
				"subject": subject or self.Subject,
				"body": {"contentType": content_type, "content": body},
				"toRecipients": [
					{"emailAddress": {"address": recipient}}
				],
			}
		}

		def _post(token):
			headers = {
				"Authorization": "Bearer {}".format(token),
				"Content-Type": "application/json",
			}
			return requests.post(api_url, headers=headers, json=payload, timeout=10)

		# 3) Acquire/refresh token and send exactly as before:
		token = self._get_access_token()
		try:
			resp = _post(token)
		except requests.exceptions.Timeout as e:
			L.error("Timeout sending email: %s", e)
			raise ASABIrisError(
				ErrorCode.SERVER_ERROR,
				tech_message="Timeout when calling Graph API",
				error_i18n_key="Email service timeout",
				error_dict={"error_message": str(e)},
			)
		except requests.exceptions.RequestException as e:
			L.error("Network error sending email: %s", e)
			raise ASABIrisError(
				ErrorCode.SERVER_ERROR,
				tech_message="Network error during Graph API call",
				error_i18n_key="Email service network error",
				error_dict={"error_message": str(e)},
			)

		if resp.status_code == 401:
			L.info("Token expired—refreshing and retrying")
			token = self._get_access_token(force_refresh=True)
			resp = _post(token)

		if resp.status_code in (200, 202):
			L.info("Microsoft 365 email sent successfully.")
			return True

		# … the rest of your error‐handling unchanged …
		if resp.status_code == 400:
			L.error("Bad request: %s", resp.text)
			raise ASABIrisError(
				ErrorCode.INVALID_REQUEST,
				tech_message="Graph API returned 400: {}".format(resp.text),
				error_i18n_key="Invalid email payload",
				error_dict={"status": resp.status_code, "body": resp.text},
			)

		if resp.status_code == 403:
			L.error("Permission denied: %s", resp.text)
			raise ASABIrisError(
				ErrorCode.AUTHENTICATION_FAILED,
				tech_message="Graph API returned 403: {}".format(resp.text),
				error_i18n_key="Insufficient permissions",
				error_dict={"status": resp.status_code, "body": resp.text},
			)

		if resp.status_code == 429:
			retry_after = resp.headers.get("Retry-After", "unknown")
			L.warning("Rate limited (Retry-After: %s)", retry_after)
			raise ASABIrisError(
				ErrorCode.SERVER_ERROR,
				tech_message="Rate limited by Graph API, retry after {}".format(retry_after),
				error_i18n_key="Email rate limited",
				error_dict={"status": resp.status_code, "retry_after": retry_after},
			)

		if 500 <= resp.status_code < 600:
			L.error("Server error: %s %s", resp.status_code, resp.text)
			raise ASABIrisError(
				ErrorCode.SERVER_ERROR,
				tech_message="Graph API server error {}: {}".format(resp.status_code, resp.text),
				error_i18n_key="Email service error",
				error_dict={"status": resp.status_code, "body": resp.text},
			)

		L.error("Unexpected status %s: %s", resp.status_code, resp.text)
		raise ASABIrisError(
			ErrorCode.SERVER_ERROR,
			tech_message="Unexpected Graph response {}: {}".format(resp.status_code, resp.text),
			error_i18n_key="Email service unexpected error",
			error_dict={"status": resp.status_code, "body": resp.text},
		)
