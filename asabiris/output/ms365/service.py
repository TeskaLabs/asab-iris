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
	"""
	Helper to fetch configuration with warning on missing.
	"""
	try:
		return config.get(section, parameter)
	except (configparser.NoSectionError, configparser.NoOptionError) as e:
		L.warning("Configuration parameter '%s' missing in section '%s': %s", parameter, section, e)
		return None


class M365EmailOutputService(asab.Service, OutputABC):

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

		# Use existing tenant config service for normalization too
		self.ConfigService = app.get_service("TenantConfigExtractionService")

		if not all([self.TenantID, self.ClientID, self.ClientSecret, self.UserEmail]):
			L.info("Incomplete M365 config—disabling email service")
			self.MsalApp = None
			return

		self.MsalApp = msal.ConfidentialClientApplication(
			self.ClientID,
			authority="https://login.microsoftonline.com/{}".format(self.TenantID),
			client_credential=self.ClientSecret,
		)

		self.AttachmentRenderer = app.get_service("AttachmentRenderingService")


	async def initialize(self, app):
		await self._try_load_stored_tokens()


	async def build_authorization_uri(self) -> str:
		"""
		Build authorization URI for obtaining delegated permissions.

		Returns:
			Authorization URI string.
		"""
		authorization_url = asab.Config.get("m365", "authorization_url")
		client_id = asab.Config.get("m365", "client_id")
		scope = "Mail.Send"  # or something similar
		redirect_uri = ...  # This exact endpoint (public url)
		params = {
			"client_id": client_id,
			"response_type": "code",
			"redirect_uri": redirect_uri,
			"response_mode": "query",
			"scope": scope,
			"state": "12345",  # TODO: generate a long random string, store it in memory
		}
		auth_url = authorization_url + "?" + aiohttp.web.Request.urlencode(params)
		return auth_url


	async def exchange_code_for_tokens(self, authorization_code: str, state: str):
		"""
		Exchange authorization code for access and refresh tokens.

		Args:
			authorization_code: The authorization code received from the authorization endpoint.
			state: The state parameter to validate.
		"""
		# TODO: Check that the state matches the stored state value
		token_url = asab.Config.get("m365", "token_url")
		client_id = asab.Config.get("m365", "client_id")
		client_secret = asab.Config.get("m365", "client_secret")
		scope = "Mail.Send"  # or something similar
		redirect_uri = ...  # This exact endpoint (public url)
		data = {
			"client_id": client_id,
			"scope": scope,
			"code": authorization_code,
			"redirect_uri": redirect_uri,
			"grant_type": "authorization_code",
			"client_secret": client_secret,
		}
		# Call the token endpoint
		async with aiohttp.ClientSession() as session:
			async with session.post(token_url, data=data) as resp:
				if resp.status != 200:
					raise aiohttp.web.HTTPBadRequest(
						text="Failed to obtain tokens from MS365. Status: {}".format(resp.status))
				token_response = await resp.json()

		# Store the tokens securely
		# ! The refresh token should be persisted in filesystem or ZK
		# so that it can be restored when the service is restarted.
		self._store_tokens(token_response)
		# Now you can use the access token to call graph API to send mails


	async def _check_and_refresh_tokens(self, event_name):
		"""
		To be used in pubsub. Make sure that the refresh token does not expire.

		Args:
			event_name:

		Returns:

		"""
		raise NotImplementedError()


	def _store_tokens(self, token_response: dict):
		"""
		Store tokens received from MSAL.
		Args:
			token_response:

		Returns:

		"""
		raise NotImplementedError()


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
		email_cc=[],
		email_bcc=[],
		attachments=None,
		tenant=None,  # only "to" respects tenant override
	):
		if not self.is_configured:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="Email service disabled (missing config)",
				error_i18n_key="Email service unavailable",
				error_dict={}
			)

		# Defaults
		tenant_to = []
		tenant_cc = []
		tenant_bcc = []
		tenant_subject = None
		if tenant is not None and self.ConfigService is not None:
			try:
				tcfg = self.ConfigService.get_email_config(tenant)
				print(tcfg)
				if isinstance(tcfg, dict):
					tenant_to = tcfg.get("to", [])
					tenant_cc = tcfg.get("cc", [])
					tenant_bcc = tcfg.get("bcc", [])
					tenant_subject = tcfg.get("subject")
				tenant_to = tcfg.get("to", []) if isinstance(tcfg, dict) else []
			except Exception as e:
				L.warning("Tenant email config fetch failed: {}".format(e), struct_data={"tenant": tenant})

		# Body may be list or single string; do a light wrap (no comma splitting)
		if email_to is None:
			body_to = []
		elif isinstance(email_to, list):
			body_to = [str(x).strip() for x in email_to if str(x).strip()]
		else:
			s = str(email_to).strip()
			body_to = [s] if s else []

		if len(tenant_to) > 0:
			to_list = tenant_to
		else:
			to_list = body_to

		if len(to_list) == 0:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="No recipient emails available (tenant/body/global).",
				error_i18n_key="No recipients configured for '{{tenant}}'.",
				error_dict={"tenant": tenant or "global"}
			)

		actual_from = email_from or self.UserEmail
		api_url = self.APIUrl.replace(self.UserEmail, actual_from)
		subject = tenant_subject or subject or self.Subject
		cc_list = tenant_cc or email_cc or []
		bcc_list = tenant_bcc or email_bcc or []
		message = {
			"subject": subject,
			"body": {"contentType": content_type, "content": body},
			"toRecipients": [{"emailAddress": {"address": addr}} for addr in to_list],
			"ccRecipients": [{"emailAddress": {"address": addr}} for addr in cc_list],
			"bccRecipients": [{"emailAddress": {"address": addr}} for addr in bcc_list],
		}

		if attachments:
			file_atts = []
			async for att in attachments:
				att.Content.seek(0)
				raw = att.Content.read()
				enc = base64.b64encode(raw).decode("ascii")
				file_atts.append({
					"@odata.type": "#microsoft.graph.fileAttachment",
					"name": att.FileName,
					"contentType": att.ContentType,
					"contentBytes": enc,
				})
			message["attachments"] = file_atts

		payload = {"message": message}

		def _post(token):
			headers = {
				"Authorization": "Bearer {}".format(token),
				"Content-Type": "application/json",
			}
			return requests.post(api_url, headers=headers, json=payload, timeout=10)

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

		# Retry on 401
		if resp.status_code == 401:
			L.info("Token expired—retrying")
			token = self._get_access_token(force_refresh=True)
			resp = _post(token)

		# Success cases
		if resp.status_code in (200, 202, 204):
			return True

		# 400 Bad request
		if resp.status_code == 400:
			L.error("Bad request: %s", resp.text)
			raise ASABIrisError(
				ErrorCode.INVALID_REQUEST,
				tech_message="Graph API returned 400: {}".format(resp.text),
				error_i18n_key="Invalid email payload",
				error_dict={"status": resp.status_code, "body": resp.text},
			)

		# 403 Forbidden
		if resp.status_code == 403:
			L.error("Permission denied: %s", resp.text)
			raise ASABIrisError(
				ErrorCode.AUTHENTICATION_FAILED,
				tech_message="Graph API returned 403: {}".format(resp.text),
				error_i18n_key="Insufficient permissions",
				error_dict={"status": resp.status_code, "body": resp.text},
			)

		# 429 Too many requests
		if resp.status_code == 429:
			retry_after = resp.headers.get("Retry-After", "unknown")
			L.warning("Rate limited (Retry-After: %s)", retry_after)
			raise ASABIrisError(
				ErrorCode.SERVER_ERROR,
				tech_message="Rate limited, retry after {}".format(retry_after),
				error_i18n_key="Email rate limited",
				error_dict={"status": resp.status_code, "retry_after": retry_after},
			)

		# 5xx and unexpected
		L.error("Unexpected status %s: %s", resp.status_code, resp.text)
		raise ASABIrisError(
			ErrorCode.SERVER_ERROR,
			tech_message="Graph API error {}: {}".format(resp.status_code, resp.text),
			error_i18n_key="Email service error",
			error_dict={"status": resp.status_code, "body": resp.text},
		)
