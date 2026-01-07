import logging
import asab
import aiohttp

from ...errors import ASABIrisError, ErrorCode

L = logging.getLogger(__name__)

asab.Config.add_defaults({
	"push": {
		"url": "https://ntfy.sh",
		"default_topic": "",
		"timeout": "10"
	}
})


class PushOutputService(asab.Service):
	def __init__(self, app, service_name="PushOutputService"):
		super().__init__(app, service_name)
		self.Url = asab.Config.get("push", "url", fallback="https://ntfy.sh").strip()
		self.DefaultTopic = asab.Config.get("push", "default_topic", fallback="").strip()
		self.Timeout = int(asab.Config.get("push", "timeout", fallback="10"))

		# Optional: tenant config service if you later want per-tenant topics/servers
		self.ConfigService = app.get_service("TenantConfigExtractionService")

	def get_push_config(self, tenant):
		"""
		Return tenant-specific push config.

		Must return:
			(url, topic, timeout, params_defaults)

		Raise KeyError if tenant has no push config.
		"""
		cfg = self.get_tenant_config(tenant)  # <-- use whatever you already use internally
		push_cfg = cfg.get("push")
		if push_cfg is None:
			raise KeyError(tenant)

		url = push_cfg.get("url")
		topic = push_cfg.get("topic")
		timeout = push_cfg.get("timeout")
		params_defaults = push_cfg.get("params_defaults") or {}

		return url, topic, timeout, params_defaults

	def _resolve_push_config(self, push_data, tenant=None):
		# Global defaults
		url = (self.Url or "").strip()
		timeout = self.Timeout
		params_defaults = {}

		tenant_topic = None

		# Tenant overrides
		if tenant and self.ConfigService is not None:
			try:
				t_url, t_topic, t_timeout, t_params_defaults = self.ConfigService.get_push_config(tenant)

				if t_url:
					url = str(t_url).strip()
				if t_timeout is not None:
					timeout = int(t_timeout)
				if t_params_defaults:
					params_defaults = dict(t_params_defaults)

				tenant_topic = (str(t_topic).strip() if t_topic else None)

			except KeyError:
				L.warning("Tenant-specific push configuration not found for '%s'. Using global config.", tenant)

		# Topic precedence (choose one policy)
		# Policy A (Slack-like): tenant -> request -> global default
		req_topic = (push_data.get("topic") or "").strip()
		def_topic = (self.DefaultTopic or "").strip()
		topic = tenant_topic or req_topic or def_topic

		# Merge params defaults: tenant defaults overridden by request params
		req_params = push_data.get("body", {}).get("params", {}) or {}
		params = dict(params_defaults)
		params.update(req_params)

		return url, topic, timeout, params

	async def send(self, push_data, tenant=None):
		message = push_data.get("rendered_message")
		if not message:
			raise ASABIrisError(
				ErrorCode.INVALID_FORMAT,
				tech_message="Rendered message body is empty.",
				error_i18n_key="Rendered message body is empty."
			)

		url, topic, timeout, params = self._resolve_push_config(push_data, tenant=tenant)

		base = (url or "").strip().rstrip("/")
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
