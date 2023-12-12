import datetime
import logging
import mimetypes

import fastjsonschema


from typing import Tuple

from ..exceptions import PathError
from ..schemas import slack_schema

#

L = logging.getLogger(__name__)

#


class SendSlackOrchestrator(object):

	ValidationSchemaSlack = fastjsonschema.compile(slack_schema)


	def __init__(self, app):
		# formatters
		self.JinjaService = app.get_service("JinjaService")
		self.MarkdownFormatterService = app.get_service("MarkdownToHTMLService")
		self.AttachmentRenderingService = app.get_service("AttachmentRenderingService")

		# output service
		self.SlackOutputService = app.get_service("SlackOutputService")


	async def send_to_slack(self, msg):
		try:
			SendSlackOrchestrator.ValidationSchemaSlack(msg)
		except fastjsonschema.exceptions.JsonSchemaException as e:
			L.warning("Invalid notification format: {}".format(e))
			return

		body = msg['body']
		template = body["template"]
		attachments = msg.get("attachments", None)
		# if params no provided pass empty params
		# - primarily use absolute path - starts with "/"
		# - if absolute path is used, check it start with "/Templates/Slack"
		# - if it is not absolute path, it is file name - assume it's a file in Templates folder

		try:
			# templates must be stores in /Templates/Slack
			if not template.startswith("/Templates/Slack/"):
				raise PathError(use_case='Slack', invalid_path=template)

			params = body.get("params", {})
			output = await self.JinjaService.format(template, params)

			if attachments is None:
				# No attachments provided, send the message as a block

				if template.endswith('.md'):
					# Translate output from markdown to plain text
					fallback_message = self.MarkdownFormatterService.unformat(output)

					# See https://api.slack.com/reference/block-kit/blocks
					blocks = [
						{
							"type": "section",
							"text": {
								"type": "mrkdwn",
								"text": output
							}
						}
					]

				else:
					# This is a plain text Slack message
					fallback_message = output
					blocks = None

				await self.SlackOutputService.send_message(blocks, fallback_message)
				return

			# Sending attachments

			output = self.MarkdownFormatterService.unformat(output)
			atts_gen = self.AttachmentRenderingService.render_attachment(attachments)
			await self.SlackOutputService.send_files(output, atts_gen)
		except Exception as e:
			L.exception("Error occurred when preparing slack notification")
			error_message = self._generate_error_message_slack(str(e))
			blocks = None
			await self.SlackOutputService.send_message(blocks, error_message)


	def get_file_name(self, attachment):
		"""
		This method returns a file-name if provided in the attachment-dict.
		If not then the name of the file is current date with appropriate
		extensions.
		"""
		if attachment.get('filename') is None:
			now = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
			return "att-" + now + "." + attachment.get('format')
		else:
			return attachment.get('filename')


	def get_content_type(self, file_extension):
		"""
		Get content type based on file extension.

		Args:
			file_extension (str): File extension.

		Returns:
			str: Content type.
		"""
		content_type = mimetypes.guess_type('dummy' + file_extension)[0]
		return content_type or 'application/octet-stream'

	def _generate_error_message_slack(self, specific_error: str) -> Tuple[str, str]:
		timestamp = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
		error_message = (
			":warning: *Hello!*\n\n"
			"We encountered an issue while processing your request:\n`{}`\n\n"
			"Please review your input and try again.\n\n"
			"*Time:* `{}` UTC\n\n"
			"Best regards,\nASAB Iris :robot_face:"
		).format(
			specific_error,
			timestamp
		)
		return error_message
