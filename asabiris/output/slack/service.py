import configparser
import logging
from io import BytesIO

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from typing import List, Tuple
import asab

from ...output_abc import OutputABC


L = logging.getLogger(__name__)


class SlackOutputService(asab.Service, OutputABC):
    def __init__(self, app, service_name="SlackOutputService"):
        super().__init__(app, service_name)
        try:
            self.SlackWebhookUrl = asab.Config.get("slack", "webhook_url")
            self.Client = WebClient(token=self.SlackWebhookUrl)
            self.Channel = asab.Config.get("slack", "slack_channel")
        except configparser.NoOptionError as e:
            L.error("Please provide webhook_url in slack configuration section.")
            raise e
        except configparser.NoSectionError:
            self.SlackWebhookUrl = None

    async def send(self, body: str, atts: List[Tuple[bytes, str, str]]) -> None:
        """
        Sends a message to a Slack channel with optional attachments.

        :param body: The main text of the message to send.
        :type body: str
        :param atts: A list of tuples, where each tuple represents an attachment to send. The first item in the tuple is the
                    attachment's binary data, the second is the attachment's file type, and the third is the attachment's
                    file name.
        :type atts: List[Tuple[bytes, str, str]]
        :return: None
        :raises ValueError: If Slack channel is missing.
        :raises SlackApiError: If there was an error sending the message.
        """
        if self.Channel is None:
            raise ValueError("Cannot send message to Slack. Reason: Missing Slack channel")

        if not self.SlackWebhookUrl:
            return

        try:
            if len(atts) == 0:
                self.Client.chat_postMessage(
                    channel=self.Channel,
                    text=body
                )
            else:
            # Prepare and send attachments
                for attachment in atts:
                    file_content = attachment[0].encode('utf-8') if not isinstance(attachment[0], bytes) else attachment[0]
                    file_obj = BytesIO(file_content)
                    self.Client.files_upload(
                        channels=self.Channel,
                        file=file_obj,
                        filetype=attachment[1],
                        filename=attachment[2],
                        title=attachment[2],
                        initial_comment=body
                    )
        except SlackApiError as e:
            raise SlackApiError(f"Failed to send message: {e}")
