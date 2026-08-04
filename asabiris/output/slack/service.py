import time
import logging
import configparser

import asab

try:
	import slack_sdk
	import slack_sdk.errors
except ModuleNotFoundError:
	slack_sdk = None

from ...errors import ASABIrisError, ErrorCode
from ...output_abc import OutputABC
from ...audit import AuditLogger

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


	def _resolve(self, channel=None):
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

		cache_hit = self.Cache.get((token, channel), None)
		if cache_hit is not None:
			return cache_hit[0], cache_hit[1]

		client = slack_sdk.WebClient(token=token)
		channel_id = self.get_channel_id(client, channel)

		self.Cache[(token, channel)] = (client, channel_id, time.time())

		return client, channel_id


	async def send_message(self, blocks, fallback_message, channel=None) -> None:
		"""
		Sends a message to a Slack channel.
		"""
		if slack_sdk is None:
			L.warning(
				"Slack output is disabled because slack_sdk is not installed; install slack_sdk to enable Slack notifications.",
			)
			return

		client, channel_id = self._resolve(channel)

		if channel is None:
			raise ValueError("Cannot send message to Slack. Reason: Missing Slack channel")
		if client is None:
			raise ValueError("Cannot send message to Slack.")

		# Audit log of outgoing payload at NOTICE level
		L.log(
			asab.LOG_NOTICE,
			"Sending Slack message.",
			struct_data={
				"channel": channel,
				"text": fallback_message,
				"blocks": blocks,
			}
		)
		try:
			client.chat_postMessage(
				channel=channel_id,
				text=fallback_message,
				blocks=blocks
			)
		except SlackApiError as e:
			L.warning(
				"Failed to send Slack message; verify bot token, channel name, and Slack API permissions.",
				struct_data={"channel": channel, "error_message": str(e)},
			)
			raise ASABIrisError(
				ErrorCode.SLACK_API_ERROR,
				tech_message="Slack API error occurred: {}".format(str(e)),
				error_i18n_key="Error occurred while sending message to Slack. Reason: '{{error_message}}'.",
				error_dict={"error_message": str(e)}
			)

		L.log(
			asab.LOG_NOTICE,
			"Slack message sent successfully.",
			struct_data={"channel": channel}
		)
		AuditLogger.log(asab.LOG_NOTICE, "Slack message sent", struct_data={"channel": channel, "channel_id": channel_id})


	async def send_files(self, body: str, atts_gen, channel=None):
		"""
		Sends a message to a Slack channel with attachments.
		"""
		if slack_sdk is None:
			L.warning(
				"Slack output is disabled because slack_sdk is not installed; install slack_sdk to enable Slack notifications.",
			)
			return

		client, channel_id = self._resolve(channel)

		try:
			async for attachment in atts_gen:
				# robust size calculation
				try:
					size = len(attachment.Content)
				except TypeError:
					size = len(attachment.Content.getbuffer()) if hasattr(attachment.Content, "getbuffer") else -1

				# Audit-log each attachment at NOTICE level
				L.log(
					asab.LOG_NOTICE,
					"Uploading file attachment to Slack.",
					struct_data={
						"filename": attachment.FileName,
						"position": attachment.Position,
						"size": size,
						"channel": channel,
					}
				)
				client.files_upload_v2(
					channel=channel_id,
					file=attachment.Content,
					filename=attachment.FileName,
					initial_comment=body.format() if attachment.Position == 0 else None
				)
		except SlackApiError as e:
			L.warning(
				"Failed to upload files to Slack; verify bot token, channel access, and file size limits.",
				struct_data={"channel": channel, "error_message": str(e)},
			)
			raise ASABIrisError(
				ErrorCode.SLACK_API_ERROR,
				tech_message="Slack API error occurred: {}".format(e),
				error_i18n_key="Error occurred while uploading files to Slack. Reason: '{{error_message}}'.",
				error_dict={"error_message": str(e)}
			)

		L.log(
			asab.LOG_NOTICE,
			"Slack files sent successfully.",
			struct_data={"channel": channel}
		)
		AuditLogger.log(asab.LOG_NOTICE, "Slack files sent", struct_data={"channel": channel, "channel_id": channel_id})


	def get_channel_id(self, client, channel_name, types=None):
		"""
		Fetches Slack channel ID from Slack API.
		"""
		if types is None:
			types = ["public_channel", "private_channel"]

		if channel_name.startswith("id "):
			return channel_name.split("id ")[1]

		for response in client.conversations_list(types=types):
			for channel in response['channels']:
				if channel.get('name') == channel_name:
					return channel['id']

		# Business-level error: channel not found
		raise ASABIrisError(
			ErrorCode.SLACK_CHANNEL_NOT_FOUND,
			tech_message="Slack channel '{}' not found.".format(channel_name),
			error_i18n_key="Slack channel '{{channel}}' not found.",
			error_dict={"channel": channel_name},
		)
