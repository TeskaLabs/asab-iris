import logging
import configparser
import time
import base64
import json
import jwt
import kazoo.exceptions


import asab
import requests
import msal

from ...errors import ASABIrisError, ErrorCode
from ...output_abc import OutputABC

L = logging.getLogger(__name__)


def check_config(config, section, parameter):
	"""
	Helper to fetch configuration with warning on missing.
	Kept for consistency even if not used now.
	"""
	try:
		return config.get(section, parameter)
	except (configparser.NoSectionError, configparser.NoOptionError) as e:
		L.warning(
			"Configuration parameter '%s' missing in section '%s': %s",
			parameter,
			section,
			e,
		)
		return None


class M365EmailOutputService(asab.Service, OutputABC):

	def __init__(self, app, service_name="M365EmailOutputService"):
		super().__init__(app, service_name)

		cfg = asab.Config
		# mode = "app" (client credentials) or "delegated" (auth code)
		mode_raw = cfg.get("m365_email", "mode", fallback="app")
		self.Mode = mode_raw.strip().lower() if mode_raw is not None else "app"
		if self.Mode not in ("app", "delegated"):
			L.warning("Unknown m365_email.mode '%s', falling back to 'app'.", self.Mode)
			self.Mode = "app"

		self.TenantID = cfg.get("m365_email", "tenant_id", fallback=None)
		self.ClientID = cfg.get("m365_email", "client_id", fallback=None)
		self.ClientSecret = cfg.get("m365_email", "client_secret", fallback=None)
		self.UserEmail = cfg.get("m365_email", "user_email", fallback=None)
		self.RedirectUri = cfg.get("m365_email", "redirect_uri", fallback=None)

		raw_url = cfg.get(
			"m365_email",
			"api_url",
			fallback="https://graph.microsoft.com/v1.0/users/{}/sendMail",
		)
		self.APIUrl = raw_url.format(self.UserEmail)
		self.Subject = cfg.get("m365_email", "subject", fallback="ASAB Iris email")

		# Use existing tenant config service for normalization too
		self.ConfigService = app.get_service("TenantConfigExtractionService")

		# Delegated tokens (access + refresh)
		self._delegated_tokens = None

		if not all([self.TenantID, self.ClientID, self.ClientSecret, self.UserEmail]):
			L.info("Incomplete M365 config—disabling email service")
			self.MsalApp = None
			self.AttachmentRenderer = None
			return

		self.MsalApp = msal.ConfidentialClientApplication(
			self.ClientID,
			authority="https://login.microsoftonline.com/{}".format(self.TenantID),
			client_credential=self.ClientSecret,
		)

		self.AttachmentRenderer = app.get_service("AttachmentRenderingService")

	def _scopes_delegated(self):
		"""
		Scopes for delegated mode (authorization code).
		Note: Do NOT include reserved scopes like offline_access here,
		MSAL will reject them for ConfidentialClientApplication.
		"""
		return [
			"https://graph.microsoft.com/Mail.Send",
		]

	def _scopes_app_only(self):
		"""
		Scopes for application (client credentials) mode.
		"""
		return [
			"https://graph.microsoft.com/.default",
		]

	async def initialize(self, app):
		if self.Mode == "delegated":
			await self._try_load_stored_tokens()

	async def _try_load_stored_tokens(self):
		"""
		Load delegated tokens from persistent storage.

		Currently a no-op placeholder that just resets in-memory state.
		TODO: Replace with ZooKeeper / filesystem-backed storage.
		"""
		self._delegated_tokens = None

	async def build_authorization_uri(self) -> str:
		"""
		Build authorization URI for obtaining delegated permissions.

		This is called from the /authorize_ms365 web endpoint.

		Returns:
			Authorization URI string that the user must open in a browser.
		"""
		if self.Mode != "delegated":
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="build_authorization_uri called but m365_email.mode is '{}' not 'delegated'.".format(
					self.Mode),
				error_i18n_key="ms365_wrong_mode",
				error_dict={"mode": self.Mode},
			)

		if self.MsalApp is None:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="MSAL client not initialized",
				error_i18n_key="Authentication misconfigured",
				error_dict={},
			)

		if self.RedirectUri is None:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="Missing 'redirect_uri' in [m365_email] config",
				error_i18n_key="Authentication misconfigured",
				error_dict={},
			)

		auth_url = self.MsalApp.get_authorization_request_url(
			scopes=self._scopes_delegated(),
			redirect_uri=self.RedirectUri,
		)

		return auth_url

	async def exchange_code_for_tokens(self, authorization_code: str, state: str):
		"""
		Exchange authorization code for access and refresh tokens.

		Called from the /authorize_ms365 callback once user logs in.
		"""
		if self.Mode != "delegated":
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="exchange_code_for_tokens called but m365_email.mode is '{}' not 'delegated'.".format(
					self.Mode),
				error_i18n_key="ms365_wrong_mode",
				error_dict={"mode": self.Mode},
			)

		if self.MsalApp is None:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="MSAL client not initialized",
				error_i18n_key="Authentication misconfigured",
				error_dict={},
			)

		if self.RedirectUri is None:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="Missing 'redirect_uri' in [m365_email] config",
				error_i18n_key="Authentication misconfigured",
				error_dict={},
			)

		result = self.MsalApp.acquire_token_by_authorization_code(
			authorization_code,
			scopes=self._scopes_delegated(),
			redirect_uri=self.RedirectUri,
		)

		if "access_token" not in result:
			L.error("Authorization code exchange failed: %r", result)
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="Failed to exchange code for tokens: {}".format(result),
				error_i18n_key="Could not authenticate with Microsoft 365",
				error_dict={"msal_result": result},
			)

		self._store_tokens(result)
		L.info("MS365 delegated tokens stored (expires_in=%s)", result.get("expires_in"))

	async def _check_and_refresh_tokens(self, event_name):
		"""
		Hook for pubsub if you want proactive refresh.
		Currently just forces a delegated refresh if tokens exist and mode is delegated.
		"""
		if self.Mode != "delegated":
			return

		if self._delegated_tokens is None:
			return

		try:
			# Force a refresh, so tokens stay valid
			self._get_delegated_access_token(force_refresh=True)
		except ASABIrisError as e:
			L.warning(
				"Failed to refresh MS365 delegated tokens on event '%s': %s",
				event_name,
				str(e),
			)

	def _store_tokens(self, token_response: dict):
		"""
		Store tokens received from MSAL.

		Args:
			token_response: Token response dict from MSAL.
		"""
		expires_in_raw = token_response.get("expires_in", 0)
		try:
			expires_in = int(expires_in_raw)
		except (TypeError, ValueError):
			expires_in = 0

		now = int(time.time())
		expires_at = now + expires_in

		self._delegated_tokens = {
			"access_token": token_response.get("access_token"),
			"refresh_token": token_response.get("refresh_token"),
			"expires_at": expires_at,
			"scope": token_response.get("scope"),
			"token_type": token_response.get("token_type"),
		}

	# TODO: Persist `self._delegated_tokens` to ZK / filesystem
	# Example (pseudo-code):
	# await self.App.LibraryService.write(
	# 	"/System/MS365/tokens.json",
	# 	json.dumps(self._delegated_tokens).encode("utf-8"),
	# )

	@property
	def is_configured(self):
		return self.MsalApp is not None

	def _delegated_auth_error(self, tech_message):
		"""
		Helper to raise a consistent 'authorization required' error.

		This is where we tell the caller that they MUST call /authorize_ms365
		when in delegated mode and tokens are missing/invalid.
		"""
		return ASABIrisError(
			ErrorCode.INVALID_SERVICE_CONFIGURATION,
			tech_message=tech_message,
			error_i18n_key="ms365_delegated_auth_required",
			error_dict={
				"authorize_url": "/authorize_ms365",
				"reason": "Iris is configured for delegated MS365 email, but there is no valid delegated token.",
				"what_to_do": (
					"Open '/authorize_ms365' in a browser and sign in with the "
					"Microsoft 365 account that should send emails. This "
					"authorizes Iris to send email on your behalf and stores an "
					"access token and refresh token for future use."
				),
			},
		)

	def _get_access_token(self, force_refresh=False):
		"""
		Return an access token in either app or delegated mode.

		mode = "app"       -> client credentials (application permissions)
		mode = "delegated" -> authorization code + refresh token
		"""
		if not self.MsalApp:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="MSAL client not initialized",
				error_i18n_key="Authentication misconfigured",
				error_dict={},
			)

		if self.Mode == "delegated":
			return self._get_delegated_access_token(force_refresh=force_refresh)

		# default: app mode
		return self._get_app_only_access_token(force_refresh=force_refresh)

	def _get_app_only_access_token(self, force_refresh=False):
		"""
		Application permissions flow (client credentials).
		Uses acquire_token_for_client; acquire_token_silent is mostly a no-op
		for this flow but we keep the pattern for completeness.
		"""
		result = None
		if not force_refresh:
			try:
				result = self.MsalApp.acquire_token_silent(
					scopes=self._scopes_app_only(),
					account=None,
				)
			except Exception as e:
				L.debug("Silent token acquisition failed (ignored): %s", e)

		if not result or "access_token" not in result:
			result = self.MsalApp.acquire_token_for_client(
				scopes=self._scopes_app_only(),
			)

		if "access_token" in result:
			return result["access_token"]

		L.error("App-only token acquisition failed: %r", result)
		raise ASABIrisError(
			ErrorCode.INVALID_SERVICE_CONFIGURATION,
			tech_message="Failed to obtain app-only token: {}".format(result),
			error_i18n_key="Could not authenticate (app mode)",
			error_dict={"msal_result": result},
		)

	def _get_delegated_access_token(self, force_refresh=False):
		"""
		Return a delegated access token, refreshing via refresh_token when needed.

		If there are no tokens, or refresh fails, raise ASABIrisError with
		an authorize_url pointing to /authorize_ms365.
		"""
		if self._delegated_tokens is None:
			# No tokens at all -> we expect user/admin to hit /authorize_ms365
			raise self._delegated_auth_error(
				"Delegated tokens not available. Call /authorize_ms365 first."
			)

		now = int(time.time())
		expires_at = self._delegated_tokens.get("expires_at", 0)

		if (not force_refresh) and expires_at > now + 60:
			# Token still valid (with a small safety margin)
			access_token = self._delegated_tokens.get("access_token")
			if access_token:
				return access_token

		# Need to refresh using refresh_token
		refresh_token = self._delegated_tokens.get("refresh_token")
		if not refresh_token:
			raise self._delegated_auth_error(
				"Missing refresh token for MS365 delegated mode."
			)

		L.info("Refreshing MS365 delegated access token using refresh_token.")
		result = self.MsalApp.acquire_token_by_refresh_token(
			refresh_token,
			scopes=self._scopes_delegated(),
		)

		if "access_token" not in result:
			L.error("Refresh token flow failed: %r", result)
			# Again: we tell caller to re-run /authorize_ms365
			raise self._delegated_auth_error(
				"Failed to refresh token: {}".format(result)
			)

		self._store_tokens(result)
		return self._delegated_tokens.get("access_token")

	async def send_email(
			self,
			email_from,
			email_to,
			subject,
			body,
			content_type="HTML",
			email_cc=None,
			email_bcc=None,
			attachments=None,
			tenant=None,  # only "to" respects tenant override
	):
		if not self.is_configured:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="Email service disabled (missing config)",
				error_i18n_key="Email service unavailable",
				error_dict={},
			)

		if email_cc is None:
			email_cc = []
		if email_bcc is None:
			email_bcc = []

		# Defaults from tenant config
		tenant_to = []
		tenant_cc = []
		tenant_bcc = []
		tenant_subject = None
		if tenant is not None and self.ConfigService is not None:
			try:
				tcfg = self.ConfigService.get_email_config(tenant)
				if isinstance(tcfg, dict):
					tenant_to = tcfg.get("to", [])
					tenant_cc = tcfg.get("cc", [])
					tenant_bcc = tcfg.get("bcc", [])
					tenant_subject = tcfg.get("subject")
			except Exception as e:
				L.warning(
					"Tenant email config fetch failed: {}".format(e),
					extra={"tenant": tenant},
				)

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
				error_dict={"tenant": tenant or "global"},
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

		# Get token (app or delegated depending on self.Mode)
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

		# Retry on 401 (token expired, consent revoked, etc.)
		if resp.status_code == 401:
			L.info("Token expired or invalid—retrying with force_refresh.")
			try:
				token = self._get_access_token(force_refresh=True)
			except ASABIrisError as e:
				# Refresh failed → bubble up
				raise e
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

		# 403 Forbidden (e.g. permissions or mailbox issues)
		if resp.status_code == 403:
			L.error("Permission denied: %s", resp.text)
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
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
