import logging
import configparser

from slack_sdk import WebClient

import asab

from ...output_abc import OutputABC


L = logging.getLogger(__name__)


class SlackOutputService(asab.Service, OutputABC):

	def __init__(self, app, service_name="SlackOutputService"):
		super().__init__(app, service_name)

		try:
			self.SlackWebhookUrl = asab.Config.get("slack", "token")
			self.Client = WebClient(token=self.SlackWebhookUrl)
			self.Channel = asab.Config.get("slack", "channel")

		except configparser.NoOptionError as e:
			L.error("Please provide token and channel in slack configuration section.")
			raise e

		except configparser.NoSectionError:
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

		channel_id = self.get_channel_id(self.Channel)

		# TODO: This could be a blocking operation, launch it in the proactor service
		self.Client.chat_postMessage(
			channel=channel_id,
			text=fallback_message,
			blocks=blocks
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

		async for attachment in atts_gen:
			# TODO: This could be a blocking operation, launch it in the proactor service
			self.Client.files_upload_v2(
				channel=channel_id,
				file=attachment.Content,
				filename=attachment.FileName,
				initial_comment=body if attachment.Position == 0 else None
			)


	def get_channel_id(self, channel_name, types="public_channel"):
		# TODO: Cache the channel_id to limit number of requests to Slack API

		# TODO: This could be a blocking operation, launch it in the proactor service
		for response in self.Client.conversations_list(types=types):
			for channel in response['channels']:
				if channel['name'] == channel_name:
					return channel['id']

		raise KeyError("Slack channel not found.")
