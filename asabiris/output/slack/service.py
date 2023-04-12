import configparser
import logging
from io import BytesIO

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

import asab

from ...output_abc import OutputABC


L = logging.getLogger(__name__)


class SlackOutputService(asab.Service, OutputABC):
    def __init__(self, app, service_name="SlackOutputService"):
        super().__init__(app, service_name)

        try:
            self.SlackWebhookUrl = asab.Config.get("slack", "webhook_url")
            self.Client = WebClient(token=self.SlackWebhookUrl)
            self.Channel = "iris"
        except configparser.NoOptionError as e:
            L.error("Please provide webhook_url in slack configuration section.")
            raise e
        except configparser.NoSectionError:
            self.SlackWebhookUrl = None

    async def send(self, body, atts):

        if self.SlackWebhookUrl is None:
            return

        try:
            self.Client.chat_postMessage(
                channel=self.Channel,
                text=body
            )

            if len(atts) != 0:
                for attachment in atts:
                    file_content = attachment[0].encode('utf-8')
                    file_obj = BytesIO(file_content)
                    self.Client.files_upload(
                        channels=self.Channel,
                        file=file_obj,
                        filetype=attachment[1],
                        filename=attachment[2],
                        title=attachment[2]
                    )
            else:
                L.info("Sending slack message without attachment")
        except SlackApiError as e:
            L.error("Error sending message: {}".format(e))
            raise SlackApiError("Error sending message: {}".format(e))
