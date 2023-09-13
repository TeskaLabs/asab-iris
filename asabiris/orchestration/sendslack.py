import asab
import datetime
import logging
import mimetypes
import fastjsonschema
import os
import base64

from .. exceptions import PathError
from ..schemas import slack_schema

L = logging.getLogger(__name__)


#


class SendSlackOrchestrator(object):

	ValidationSchemaSlack = fastjsonschema.compile(slack_schema)


	def __init__(self, app):
		# formatters
		self.JinjaService = app.get_service("JinjaService")
		self.HtmlToPdfService = app.get_service("HtmlToPdfService")
		self.MarkdownToHTMLService = app.get_service("MarkdownToHTMLService")
		# output service
		self.SlackOutputService = app.get_service("SlackOutputService")
		# location of slack templates

	async def send_to_slack(self, msg):
		try:
			SendSlackOrchestrator.ValidationSchemaSlack(msg)
		except fastjsonschema.exceptions.JsonSchemaException as e:
			L.warning("Invalid notification format: {}".format(e))
			return

		body = msg['body']
		attachments = msg.get("attachments", [])

		# sertup render failed flag
		render_failed = False
		# if params no provided pass empty params
		# - primarily use absolute path - starts with "/"
		# - if absolute path is used, check it start with "/Templates"
		# - if it is not absolute path, it is file name - assume it's a file in Templates folder

		# templates must be stores in /Templates/Slack
		if not body['template'].startswith("/Templates/Slack/"):
			raise PathError(use_case='Slack', invalid_path=body['template'])

		atts = []

		for a in attachments:
			# If there are 'template' we render 'template's' else we throw a sweet warning.
			# If content-type is application/octet-stream we assume there is additional attachments in request else we raise bad-request error.
			template = a.get('template', None)

			if template is not None:
				params = a.get('params', {})

				render_failed = False
				# get file-name of the attachment
				file_name = self.get_file_name(a)
				jinja_output, render_failed = await self.render(template, params, render_failed)

				# if rendering failure occured
				if render_failed:
					atts = []
					break

				_, node_extension = os.path.splitext(template)
				content_type = self.get_content_type(node_extension)

				atts.append((jinja_output, content_type, file_name))
				continue

			# If there is `base64` field, then the content of the attachment is provided in the body in base64
			base64cnt = a.get('base64', None)
			if base64cnt is not None:
				content_type = a.get('content-type', "application/octet-stream")
				file_name = self.get_file_name(a)
				result = base64.b64decode(base64cnt)
				atts.append((result, content_type, file_name))
				continue

		body["params"] = body.get("params", {})
		output, render_failed = await self.render(body["template"], body["params"], render_failed)
		await self.SlackOutputService.send(output, atts)


	async def render(self, template, params, render_failed):
		"""
		This method renders templates based on the depending on the
		extension of template.

		Returns the html and optional subject line if found in the templat.

		jinja_output will be used for extracting subject.
		"""
		# templates must be stores in /Templates/Emails
		if not template.startswith("/Templates/Slack/"):
			raise PathError(path=template)

		try:
			jinja_output = await self.JinjaService.format(template, params)
		except Exception as e:
			L.warning("Jinja2 Rendering Error: {}".format(str(e)))
			# rendering failed
			render_failed = True

			if asab.Config.get("jinja", "failsafe"):
				# Get the current timestamp
				current_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

				# Prepare the error details including timestamp, recipients, and error message
				error_details = (
					"Timestamp: {}\n"
					"Error Message: {}\n"
				).format(current_timestamp, str(e))

				# User-friendly error message
				error_message = (
					"Hello!\n\n"
					"We encountered an issue while processing your request. "
					"Please review your input and try again.\n\n"
					"Thank you!\n"
					"\nError Details:\n```\n{}\n```".format(
						error_details
					)
				)
				# Add LogMan signature with HTML line breaks
				error_message += "\nBest regards,\nLogMan.io"

				return error_message, render_failed

		return jinja_output, render_failed

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
