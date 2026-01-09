import logging
import asab
import aiohttp

from ...errors import ASABIrisError, ErrorCode

L = logging.getLogger(__name__)


class PushOutputService(asab.Service):
	def __init__(self, app, service_name="PushOutputService"):
		super().__init__(app, service_name)
		self.Url = (asab.Config.get("push", "url", fallback="") or "").strip()
		self.DefaultTopic = asab.Config.get("push", "default_topic", fallback="").strip()
		self.Timeout = int(asab.Config.get("push", "timeout", fallback="10"))

		# Optional: tenant config service if you later want per-tenant topics/servers
		self.ConfigService = app.get_service("TenantConfigExtractionService")

	def _resolve_topic(self, push_data, tenant=None):
		# Slack-like precedence: tenant -> request -> global default
		tenant_topic = None

		if tenant and self.ConfigService is not None:
			try:
				tenant_topic = self.ConfigService.get_push_topic(tenant)
				if tenant_topic is not None:
					tenant_topic = str(tenant_topic).strip()
			except KeyError:
				L.warning("Tenant-specific push topic not found for '%s'. Using request/global topic.", tenant)

		req_topic = (push_data.get("topic") or "").strip()
		def_topic = (self.DefaultTopic or "").strip()

		return tenant_topic or req_topic or def_topic

	async def send(self, push_data, tenant=None):
		message = push_data.get("rendered_message")
		if not message:
			raise ASABIrisError(
				ErrorCode.INVALID_FORMAT,
				tech_message="Rendered message body is empty.",
				error_i18n_key="Rendered message body is empty."
			)

		topic = self._resolve_topic(push_data, tenant=tenant)
		base = (self.Url or "").strip().rstrip("/")
		timeout = self.Timeout
		params = push_data.get("body", {}).get("params", {}) or {}

		if not base:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="Push URL is not configured (tenant/api/config).",
				error_i18n_key="Missing push URL configuration."
			)

		if not topic:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="No topic provided (tenant/api/config).",
				error_i18n_key="Missing topic in push request."
			)

		# Must be a *name*, not a URL or a path
		if "://" in topic or "/" in topic:
			raise ASABIrisError(
				ErrorCode.INVALID_FORMAT,
				tech_message="Invalid topic '{}'; provide only the topic name (no slashes/scheme).".format(topic),
				error_i18n_key="Invalid topic",
				error_dict={"topic": topic}
			)

		final_url = "{}/{}".format(base, topic)
		L.warning("ntfy push URL = {}".format(final_url))

		headers = {}
		title = params.get("title")
		if title:
			headers["Title"] = str(title)

		priority = params.get("priority")
		if priority:
			headers["Priority"] = str(priority)

		tags = params.get("tags")
		if tags:
			headers["Tags"] = str(tags)

		click = params.get("click")
		if click:
			headers["Click"] = str(click)

		timeout = aiohttp.ClientTimeout(total=int(timeout))

		try:
			async with aiohttp.ClientSession(timeout=timeout) as session:
				async with session.post(final_url, headers=headers, data=message.encode("utf-8")) as resp:
					text = await resp.text()
					if resp.status != 200:
						raise ASABIrisError(
							ErrorCode.SERVER_ERROR,
							tech_message="Push failed: {} {}".format(resp.status, text),
							error_i18n_key="Push notification failed.",
							error_dict={"error_message": text}
						)
		except aiohttp.ClientError as err:
			L.error("Network error while sending push: {}".format(err))
			raise ASABIrisError(
				ErrorCode.SERVER_ERROR,
				tech_message="Network error while sending push.",
				error_i18n_key="Error occurred while sending push. Reason: '{{error_message}}'.",
				error_dict={"error_message": str(err)}
			)

		return True
