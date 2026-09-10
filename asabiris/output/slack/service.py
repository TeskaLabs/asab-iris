import time
import logging
import configparser

import aiohttp
import asab

try:
	import slack_sdk
	import slack_sdk.errors
	from slack_sdk.web.async_client import AsyncWebClient
except ModuleNotFoundError:
	slack_sdk = None

from ...errors import ASABIrisError, ErrorCode
from ...output_abc import OutputABC
from ...audit import AuditLogger
from ..retry import DeliveryError, RetryPolicy, http_error, http_request, retry_after_seconds

if slack_sdk is not None:
	SlackApiError = slack_sdk.errors.SlackApiError
else:
	SlackApiError = Exception


L = logging.getLogger(__name__)


def check_config(config, section, parameter):
	try:
		value = config.get(section, parameter)
		return value
	except configparser.NoOptionError as e:
		L.warning(
			"Required configuration option is missing; set it in the service configuration section.",
			struct_data={
				"config_section": section,
				"config_option": parameter,
				"error_type": e.__class__.__name__,
			},
		)
		return None


class SlackOutputService(asab.Service, OutputABC):

	def __init__(self, app, service_name="SlackOutputService"):
		super().__init__(app, service_name)
		self.ConfigService = app.get_service("TenantConfigExtractionService")

		# Load global configuration as defaults
		self.ConfigToken = check_config(asab.Config, "slack", "token")
		self.ConfigChannel = check_config(asab.Config, "slack", "channel")

		self.Cache = {}

		if slack_sdk is None:
			L.warning(
				"Slack output is disabled because slack_sdk is not installed; install slack_sdk to enable Slack notifications.",
			)
			return

		app.PubSub.subscribe("Application.tick/1800!", self._on_tick)


	def _on_tick(self, event):
		# clear cache every 1800 seconds
		to_delete = []
		for key, value in self.Cache.items():
			if time.time() - value[2] > 3600:
				to_delete.append(key)
		for key in to_delete:
			self.Cache.pop(key, None)


	async def _resolve(self, retry, channel=None):
		try:
			effective_tenant = asab.contextvars.Tenant.get()
		except LookupError:
			effective_tenant = None

		# determine which token/channel to use
		if effective_tenant and self.ConfigService is not None:
			try:
				token, default_channel = self.ConfigService.get_slack_config(effective_tenant)
			except KeyError:
				L.warning(
					"Tenant-specific Slack configuration not found; using global [slack] token and channel.",
					struct_data={"tenant": effective_tenant},
				)
				token, default_channel = self.ConfigToken, self.ConfigChannel
		else:
			token, default_channel = self.ConfigToken, self.ConfigChannel

		if channel is None:
			channel = default_channel
		if channel is None:
			raise ValueError("Cannot send message to Slack. Reason: Missing Slack channel")

		cache_hit = self.Cache.get((token, channel), None)
		if cache_hit is not None:
			return cache_hit[0], cache_hit[1], channel

		client = AsyncWebClient(token=token, retry_handlers=[])
		channel_id = await self.get_channel_id(client, channel, retry)

		self.Cache[(token, channel)] = (client, channel_id, time.time())

		return client, channel_id, channel


	async def _call(self, retry, operation, step, *, read_only=False):
		async def attempt():
			try:
				return await operation()
			except SlackApiError as exc:
				response = exc.response
				# The SDK exposes ClientResponse when decoding an acknowledgement fails.
				if isinstance(response, aiohttp.ClientResponse):
					if response.status != 200:
						raise http_error(response.status, response.headers, read_only=read_only) from exc
					raise DeliveryError("Invalid Slack acknowledgement.", "uncertain") from exc
				headers = {key.lower(): value for key, value in response.headers.items()}
				if response.status_code != 200:
					raise http_error(response.status_code, response.headers, read_only=read_only) from exc
				error = response.get("error", "unknown_error")
				if error == "ratelimited" or (read_only and error == "service_unavailable"):
					classification = "temporary"
				elif error in ("service_unavailable", "internal_error", "fatal_error", "unknown_error"):
					classification = "uncertain"
				else:
					classification = "permanent"
				code = ErrorCode.AUTHENTICATION_FAILED if error in (
					"invalid_auth", "not_authed", "account_inactive", "token_revoked",
				) else ErrorCode.SLACK_API_ERROR
				raise DeliveryError(
					"Slack rejected the operation.", classification, code=code,
					retry_after=retry_after_seconds(headers.get("retry-after")),
					details={"provider_code": error},
				) from exc
		return await retry.run(attempt, step=step)

	async def send_message(self, blocks, fallback_message, channel=None) -> None:
		if slack_sdk is None:
			raise ASABIrisError(ErrorCode.INVALID_SERVICE_CONFIGURATION, tech_message="Slack SDK is unavailable.")
		retry = RetryPolicy("slack")
		client, channel_id, channel = await self._resolve(retry, channel)
		await self._call(retry, lambda: client.chat_postMessage(
			channel=channel_id, text=fallback_message, blocks=blocks,
		), "message")
		AuditLogger.log(asab.LOG_NOTICE, "Slack message sent", struct_data={"channel": channel, "channel_id": channel_id})

	async def send_files(self, body: str, atts_gen, channel=None):
		if slack_sdk is None:
			raise ASABIrisError(ErrorCode.INVALID_SERVICE_CONFIGURATION, tech_message="Slack SDK is unavailable.")
		# Materialize the streams once. Each upload stage has its own retry boundary.
		attachments = []
		async for attachment in atts_gen:
			attachment.Content.seek(0)
			attachments.append((attachment.FileName, attachment.Content.read(), attachment.Position))
		retry = RetryPolicy("slack")
		client, channel_id, channel = await self._resolve(retry, channel)
		async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
			for index, (filename, content, position) in enumerate(attachments):
				step = "file-{}".format(index + 1)
				upload = await self._call(retry, lambda: client.files_getUploadURLExternal(
					filename=filename, length=len(content),
				), step + "-url")
				await retry.run(lambda: http_request(
					session, "POST", upload["upload_url"], data=content,
				), step=step + "-bytes")
				await self._call(retry, lambda: client.files_completeUploadExternal(
					files=[{"id": upload["file_id"], "title": filename}], channel_id=channel_id,
					initial_comment=body.format() if position == 0 else None,
				), step + "-complete")
		AuditLogger.log(asab.LOG_NOTICE, "Slack files sent", struct_data={"channel_id": channel_id})

	async def get_channel_id(self, client, channel_name, retry):
		if channel_name.startswith("id "):
			return channel_name.split("id ")[1]
		cursor = None
		while True:
			response = await self._call(retry, lambda: client.conversations_list(
				types=["public_channel", "private_channel"], cursor=cursor,
			), "channel-lookup", read_only=True)
			for channel in response["channels"]:
				if channel.get("name") == channel_name:
					return channel["id"]
			cursor = response.get("response_metadata", {}).get("next_cursor")
			if not cursor:
				break
		raise ASABIrisError(
			ErrorCode.SLACK_CHANNEL_NOT_FOUND,
			tech_message="Slack channel '{}' not found.".format(channel_name),
			error_i18n_key="Slack channel '{{channel}}' not found.", error_dict={"channel": channel_name},
		)
