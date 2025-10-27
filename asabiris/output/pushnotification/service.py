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

	async def send(self, push_data, tenant=None):
		"""
		push_data contains:
			- topic (optional; fallback to default_topic)
			- body.params may include title/priority/tags/click
			- rendered_message (required; from orchestrator)
		"""
		message = push_data.get("rendered_message")
		if not message:
			raise ASABIrisError(
				ErrorCode.INVALID_FORMAT,
				tech_message="Rendered message body is empty.",
				error_i18n_key="Rendered message body is empty."
			)

		topic = push_data.get("topic", self.DefaultTopic)
		if not topic:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="No topic provided (tenant/api/config).",
				error_i18n_key="Missing topic in push request."
			)

		url = "{}/{}".format(self.Url, topic)
		params = push_data.get("body", {}).get("params", {}) or {}

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

		timeout = aiohttp.ClientTimeout(total=self.Timeout)

		try:
			async with aiohttp.ClientSession(timeout=timeout) as session:
				async with session.post(url, headers=headers, data=message.encode("utf-8")) as resp:
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
