import logging
import asab
import msal
import aiohttp
import asyncio
import base64
from aiohttp import ClientTimeout

from ...errors import ASABIrisError, ErrorCode
from ...output_abc import OutputABC

L = logging.getLogger(__name__)


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
		from_recipient,
		recipient,
		subject,
		body,
		content_type="HTML",
		attachments=None,
	):
		if not self.is_configured:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="Email service disabled (missing config)",
				error_i18n_key="Email service unavailable",
				error_dict={}
			)

		actual_from = from_recipient or self.UserEmail
		api_url = self.APIUrl.replace(self.UserEmail, actual_from)

		# build message
		message = {
			"subject": subject or self.Subject,
			"body": {"contentType": content_type, "content": body},
			"toRecipients": [{"emailAddress": {"address": recipient}}],
		}

		# render and encode attachments if provided
		if attachments:
			file_atts = []
			async for att in self.AttachmentRenderer.render_attachment(attachments):
				# read content and base64 encode
				stream = att.Content
				# ensure stream at start
				stream.seek(0)
				data = stream.read()
				encoded = base64.b64encode(data).decode('ascii')
				file_atts.append({
					"@odata.type": "#microsoft.graph.fileAttachment",
					"name": att.FileName,
					"contentType": att.ContentType,
					"contentBytes": encoded,
				})
			message["attachments"] = file_atts

		payload = {"message": message}
		timeout = ClientTimeout(total=10)

		async def _post(token):
			headers = {
				"Authorization": "Bearer {}".format(token),
				"Content-Type": "application/json",
			}
			async with aiohttp.ClientSession(timeout=timeout) as session:
				return await session.post(api_url, json=payload, headers=headers)

		token = self._get_access_token()
		try:
			resp = await _post(token)
		except asyncio.TimeoutError as e:
			L.error("Timeout sending email: %s", e)
			raise ASABIrisError(
				ErrorCode.SERVER_ERROR,
				tech_message="Timeout when calling Graph API",
				error_i18n_key="Email service timeout",
				error_dict={"error_message": str(e)},
			)

		if resp.status == 401:
			L.info("Token expired—refreshing and retrying")
			token = self._get_access_token(force_refresh=True)
			resp = await _post(token)

		text = await resp.text()
		if resp.status in (200, 202):
			L.info("Microsoft 365 email sent successfully.")
			return True

		if resp.status == 400:
			L.error("Bad request: %s", text)
			raise ASABIrisError(
				ErrorCode.INVALID_REQUEST,
				tech_message="Graph API returned 400: {}".format(text),
				error_i18n_key="Invalid email payload",
				error_dict={"status": resp.status, "body": text},
			)

		if resp.status == 403:
			L.error("Permission denied: %s", text)
			raise ASABIrisError(
				ErrorCode.AUTHENTICATION_FAILED,
				tech_message="Graph API returned 403: {}".format(text),
				error_i18n_key="Insufficient permissions",
				error_dict={"status": resp.status, "body": text},
			)

		if resp.status == 429:
			retry_after = resp.headers.get("Retry-After", "unknown")
			L.warning("Rate limited (Retry-After: %s)", retry_after)
			raise ASABIrisError(
				ErrorCode.SERVER_ERROR,
				tech_message="Rate limited by Graph API, retry after {}".format(retry_after),
				error_i18n_key="Email rate limited",
				error_dict={"status": resp.status, "retry_after": retry_after},
			)

		if 500 <= resp.status < 600:
			L.error("Server error: %s %s", resp.status, text)
			raise ASABIrisError(
				ErrorCode.SERVER_ERROR,
				tech_message="Graph API server error {}: {}".format(resp.status, text),
				error_i18n_key="Email service error",
				error_dict={"status": resp.status, "body": text},
			)

		L.error("Unexpected status %s: %s", resp.status, text)
		raise ASABIrisError(
			ErrorCode.SERVER_ERROR,
			tech_message="Unexpected Graph response {}: {}".format(resp.status, text),
			error_i18n_key="Email service unexpected error",
			error_dict={"status": resp.status, "body": text},
		)
