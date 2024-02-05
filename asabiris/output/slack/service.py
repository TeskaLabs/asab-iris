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
	except configparser.NoOptionError:
		L.error("Configuration parameter '{}' is missing in section '{}'.".format(parameter, section))
		exit()


class SlackOutputService(asab.Service, OutputABC):

	def __init__(self, app, service_name="SlackOutputService"):
		super().__init__(app, service_name)

		try:
			self.SlackWebhookUrl = check_config(asab.Config, "slack", "token")
			self.Channel = check_config(asab.Config, "slack", "channel")
			self.Client = WebClient(token=self.SlackWebhookUrl)
		except configparser.NoOptionError:
			L.error("Please provide token and channel in slack configuration section.")
			exit()
		except configparser.NoSectionError:
			L.warning("Configuration section 'slack' is not provided.")
			self.SlackWebhookUrl = None


	async def send_message(self, blocks, fallback_message) -> None:
		"""
		Sends a message to a Slack channel.

		See https://api.slack.com/methods/chat.postMessage

		"""
		if self.Channel is None:
			raise ValueError("Cannot send message to Slack. Reason: Missing Slack channel")

		if self.SlackWebhookUrl is None:
			raise ValueError("Cannot send message to Slack. Reason: Missing Webhook URL or token")


		# TODO: This could be a blocking operation, launch it in the proactor service
		try:
			channel_id = self.get_channel_id(self.Channel)
			self.Client.chat_postMessage(
				channel=channel_id,
				text=fallback_message,
				blocks=blocks
			)
		except slack_sdk.errors.SlackApiError as e:
			L.warning("Failed to send message to Slack: {}".format(e))
			raise ASABIrisError(
				ErrorCode.SLACK_API_ERROR,
				tech_message="Slack API error occurred: {}".format(str(e)),
				error_i18n_key="Error occurred while sending message to Slack. Reason: '{{error_message}}'.",
				error_dict={
					"error_message": str(e)
				}
			)

	async def send_files(self, body: str, atts_gen):
		"""
		Sends a message to a Slack channel with attachments.
		"""
		if self.Channel is None:
			raise ValueError("Cannot send message to Slack. Reason: Missing Slack channel")

		if self.SlackWebhookUrl is None:
			raise ValueError("Cannot send message to Slack. Reason: Missing Webhook URL or token")

		channel_id = self.get_channel_id(self.Channel)
		try:
			async for attachment in atts_gen:
				# TODO: This could be a blocking operation, launch it in the proactor service
				self.Client.files_upload_v2(
					channel=channel_id,
					file=attachment.Content,
					filename=attachment.FileName,
					initial_comment=body if attachment.Position == 0 else None
				)
		except slack_sdk.errors.SlackApiError as e:
			L.warning("Failed to upload files to Slack: {}".format(e))
			raise ASABIrisError(
				ErrorCode.SLACK_API_ERROR,
				tech_message="Slack API error occurred: {}".format(str(e)),
				error_i18n_key="Error occurred while uploading files to Slack. Reason: '{{error_message}}'.",
				error_dict={
					"error_message": str(e)
				}
			)


	def get_channel_id(self, channel_name, types="public_channel"):
		# TODO: Cache the channel_id to limit number of requests to Slack API

		# TODO: This could be a blocking operation, launch it in the proactor service
		for response in self.Client.conversations_list(types=types):
			for channel in response['channels']:
				if channel['name'] == channel_name:
					return channel['id']

		raise KeyError("Slack channel not found.")
