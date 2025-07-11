import logging
import configparser
import asab
import requests
import msal
import base64
from ...errors import ASABIrisError, ErrorCode
from ...output_abc import OutputABC

L = logging.getLogger(__name__)


def check_config(config, section, parameter):
	try:
		return config.get(section, parameter)
	except (configparser.NoSectionError, configparser.NoOptionError) as e:
		L.warning("Configuration parameter '%s' missing in section '%s': %s", parameter, section, e)
		return None


class M365EmailOutputService(asab.Service, OutputABC):
	"""
	Service for sending emails via Microsoft 365 Graph API.

	Config ([m365_email]):
	tenant_id     - Azure AD tenant ID (required)
	client_id     - Application (client) ID (required)
	client_secret - Client secret (required)
	user_email    - Sending user address (required)
	api_url       - Optional URL template, defaults to
		"https://graph.microsoft.com/v1.0/users/{}/sendMail"
	subject       - Default email subject
	"""

	def __init__(self, app, service_name="M365EmailOutputService"):
		super().__init__(app, service_name)

		cfg = asab.Config
		self.TenantID = cfg.get("m365_email", "tenant_id", fallback=None)
		self.ClientID = cfg.get("m365_email", "client_id", fallback=None)
		self.ClientSecret = cfg.get("m365_email", "client_secret", fallback=None)
		self.UserEmail = cfg.get("m365_email", "user_email", fallback=None)
		raw_url = cfg.get(
			"m365_email",
			"api_url",
			fallback="https://graph.microsoft.com/v1.0/users/{}/sendMail"
		)
		self.APIUrl = raw_url.format(self.UserEmail)
		self.Subject = cfg.get("m365_email", "subject", fallback="ASAB Iris email")

		if not all([self.TenantID, self.ClientID, self.ClientSecret, self.UserEmail]):
			L.info("Incomplete M365 config—disabling email service")
			self.MsalApp = None
			return

		self.MsalApp = msal.ConfidentialClientApplication(
			self.ClientID,
			authority="https://login.microsoftonline.com/{}".format(self.TenantID),
			client_credential=self.ClientSecret,
		)

		# get the attachment renderer
		self.AttachmentRenderer = app.get_service("AttachmentRenderingService")

	@property
	def is_configured(self):
		return self.MsalApp is not None

	def _get_access_token(self, force_refresh=False):
		if not self.MsalApp:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="MSAL client not initialized",
				error_i18n_key="Authentication misconfigured",
				error_dict={}
			)

		result = None
		if not force_refresh:
			result = self.MsalApp.acquire_token_silent(
				scopes=["https://graph.microsoft.com/.default"],
				account=None
			)
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

	async def send_email(
		self,
		email_from,
		email_to,
		subject,
		body,
		content_type="HTML",
		attachments=None,
	):
		"""
		Send an email via Graph API. Attachments should be raw specs, rendered below.
		"""
		if not self.is_configured:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="Email service disabled (missing config)",
				error_i18n_key="Email service unavailable",
				error_dict={}
			)

		# Determine sender
		actual_from = email_from or self.UserEmail
		# API URL with correct sender
		api_url = self.APIUrl.replace(self.UserEmail, actual_from)

		# Build message payload
		message = {
			"subject": subject or self.Subject,
			"body": {"contentType": content_type, "content": body},
			"toRecipients": [
				{"emailAddress": {"address": addr}} for addr in (email_to if isinstance(email_to, list) else [email_to])
			],
		}

		# Attachments
		if attachments:
			file_atts = []
			# attachments is already an async generator of Attachment
			async for att in attachments:
				att.Content.seek(0)
				raw = att.Content.read()
				enc = base64.b64encode(raw).decode('ascii')
				file_atts.append({
					"@odata.type": "#microsoft.graph.fileAttachment",
					"name": att.FileName,
					"contentType": att.ContentType,
					"contentBytes": enc,
				})
			message["attachments"] = file_atts

		# Final payload and POST
		payload = {"message": message}

		def _post(token):
			headers = {
				"Authorization": "Bearer {}".format(token),
				"Content-Type": "application/json",
			}
			return requests.post(api_url, headers=headers, json=payload, timeout=10)

		token = self._get_access_token()
		resp = None
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
