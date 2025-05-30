import logging
import configparser
import slack_sdk.errors

from slack_sdk import WebClient
from ...errors import ASABIrisError, ErrorCode

import asab

from ...output_abc import OutputABC


L = logging.getLogger(__name__)


def check_config(config, section, parameter):
	try:
		value = config.get(section, parameter)
		return value
	except configparser.NoOptionError as e:
		L.warning("Configuration parameter '{}' is missing in section '{}': {}".format(parameter, section, e))
		return None


class SlackOutputService(asab.Service, OutputABC):
	def __init__(self, app, service_name="SlackOutputService"):
		super().__init__(app, service_name)

		# Load global configuration as defaults
		self.SlackWebhookUrl = check_config(asab.Config, "slack", "token")
		self.Channel = check_config(asab.Config, "slack", "channel")
		# Keep tenant-config service always available
		self.ConfigService = app.get_service("TenantConfigExtractionService")

		# If required Slack configuration is missing, disable Slack service
		if not self.SlackWebhookUrl or not self.Channel:
			L.warning("Slack output service is not properly configured. Disabling Slack service.")
			self.Client = None
			return

		self.Client = WebClient(token=self.SlackWebhookUrl)


	async def send_message(self, blocks, fallback_message, tenant=None) -> None:
		"""
		Sends a message to a Slack channel.
		"""
		if self.Client is None:
			L.warning("SlackOutputService is not initialized properly. Message will not be sent.")
			return

		# determine which token/channel to use
		token, channel = (self.SlackWebhookUrl, self.Channel)
		if tenant and self.ConfigService is not None:
			try:
				token, channel = self.ConfigService.get_slack_config(tenant)
			except KeyError:
				L.warning(
					"Tenant-specific Slack configuration not found for '%s'. Using global config.",
					tenant
				)

		if channel is None:
			raise ValueError("Cannot send message to Slack. Reason: Missing Slack channel")
		if token is None:
			raise ValueError("Cannot send message to Slack. Reason: Missing Webhook URL or token")

		# Audit log of outgoing payload at NOTICE level
		L.log(
			asab.LOG_NOTICE,
			"SlackOutputService.send_message → channel=%s, text=%r, blocks=%r",
			struct_data={
				"channel": channel,
				"text": fallback_message,
				"blocks": blocks,
			}
		)

		try:
			client = WebClient(token=token)
			channel_id = self.get_channel_id(client, channel)
			client.chat_postMessage(
				channel=channel_id,
				text=fallback_message,
				blocks=blocks
			)
		except slack_sdk.errors.SlackApiError as e:
			L.warning("Failed to send message to Slack: %s", e)
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


	async def send_files(self, body: str, atts_gen, tenant=None):
		"""
		Sends a message to a Slack channel with attachments.
		"""
		if self.Client is None:
			L.warning("SlackOutputService is not initialized properly. File will not be sent.")
			return

		token, channel = (self.SlackWebhookUrl, self.Channel)
		if tenant:
			try:
				token, channel = self.ConfigService.get_slack_config(tenant)
			except KeyError:
				L.warning("Tenant-specific Slack configuration not found for '{}'. Using global config.".format(tenant))

		if channel is None:
			raise ValueError("Cannot send message to Slack. Reason: Missing Slack channel")
		if token is None:
			raise ValueError("Cannot send message to Slack. Reason: Missing Webhook URL or token")

		client = WebClient(token=token)
		channel_id = self.get_channel_id(client, channel)

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
					"Uploading to Slack → filename=%s, position=%d, size=%d bytes",
					struct_data={
						"filename": attachment.FileName,
						"position": attachment.Position,
						"size": size,
					}
				)
				client.files_upload_v2(
					channel=channel_id,
					file=attachment.Content,
					filename=attachment.FileName,
					initial_comment=body.format() if attachment.Position == 0 else None
				)
		except slack_sdk.errors.SlackApiError as e:
			L.warning("Failed to upload files to Slack: {}".format(e))
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


	def get_channel_id(self, client, channel_name, types="public_channel"):
		"""
		Fetches Slack channel ID from Slack API.
		"""
		for response in client.conversations_list(types=types):
			for channel in response['channels']:
				if channel['name'] == channel_name:
					return channel['id']

		raise KeyError("Slack channel '{}' not found.".format(channel_name))
