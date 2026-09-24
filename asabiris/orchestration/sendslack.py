import datetime
import logging
import mimetypes
import base64
import io

import fastjsonschema

from ..errors import ASABIrisError, ErrorCode
from ..formatter.attachments import Attachment
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
			L.warning(
				"Slack notification request failed schema validation; fix the request payload structure.",
				struct_data={"validation_error": str(e)},
			)
			return

		body = msg['body']
		template = body["template"]
		channel = body.get("channel", None)

		# This allows to speficy channel id or member id directly, skipping the lookup by channel name.
		channel_id = body.get("channel_id", None)
		if channel_id is not None:
			channel = "id " + channel_id

		attachments = msg.get("attachments", None)
		# if params no provided pass empty params
		# - primarily use absolute path - starts with "/"
		# - if absolute path is used, check it start with "/Templates/Slack"
		# - if it is not absolute path, it is file name - assume it's a file in Templates folder

		# templates must be stores in /Templates/Slack
		if not template.startswith("/Templates/Slack/"):
			raise ASABIrisError(
				ErrorCode.INVALID_PATH,
				tech_message="Incorrect template path '{}'. Move templates to '/Templates/Slack/'.".format(template),
				error_i18n_key="Incorrect template path '{{incorrect_path}}'. Please move your templates to '/Templates/Slack/'.",
				error_dict={
					"incorrect_path": template,
				}
			)

		params = body.get("params", {})
		cached = msg.get("_iris_slack_content")
		if cached is None:
			output = await self.JinjaService.format(template, params)
			cached = {"output": output}
			msg["_iris_slack_content"] = cached
		else:
			output = cached["output"]

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

			await self.SlackOutputService.send_message(blocks, fallback_message, channel)
			return

		# Sending attachments

		output = self.MarkdownFormatterService.unformat(output)
		cached_attachments = cached.get("attachments")
		if cached_attachments is None:
			cached_attachments = []
			async for attachment in self.AttachmentRenderingService.render_attachment(attachments):
				attachment.Content.seek(0)
				cached_attachments.append({
					"content": base64.b64encode(attachment.Content.read()).decode("ascii"),
					"content_type": attachment.ContentType,
					"filename": attachment.FileName,
					"position": attachment.Position,
				})
			cached["attachments"] = cached_attachments
		atts_gen = self._cached_attachments(cached_attachments)
		await self.SlackOutputService.send_files(output, atts_gen, channel, retry_state=msg)

	async def _cached_attachments(self, attachments):
		for attachment in attachments:
			yield Attachment(
				Content=io.BytesIO(base64.b64decode(attachment["content"])),
				ContentType=attachment["content_type"],
				FileName=attachment["filename"],
				Position=attachment["position"],
			)


	async def render_attachment(self, template, params):
		"""
		This method renders attachment based on the depending on the extension of template.
		"""

		try:
			jinja_output = await self.JinjaService.format(template, params)
		except KeyError:
			L.warning(
				"Failed to load or render Slack attachment template; verify the template exists under /Templates/.",
				struct_data={'template': template},
			)
			raise

		return jinja_output


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
