import datetime
import logging
import fastjsonschema
import json
import os
import base64

from .. import utils
from .. exceptions import PathError, FormatError
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
		# if params no provided pass empty params
		# - primarily use absolute path - starts with "/"
		# - if absolute path is used, check it start with "/Templates"
		# - if it is not absolute path, it is file name - assume it's a file in Templates folder

		# templates must be stores in /Templates/Slack
		if not body['template'].startswith("/Templates/Slack/"):
			raise PathError(path=body['template'])

		atts = []

		for a in attachments:
			# If there are 'template' we render 'template's' else we throw a sweet warning.
			# If content-type is application/octet-stream we assume there is additional attachments in request else we raise bad-request error.
			template = a.get('template', None)

			if template is not None:
				params = a.get('params', {})
				# templates must be stores in /Templates/Emails
				if not template.startswith("/Templates/Slack/"):
					raise PathError(path=template)

				# get file-name of the attachment
				file_name = self.get_file_name(a)
				jinja_output, result = await self.render(template, params)

				# get pdf from html if present.
				fmt = a.get('format', 'html')
				if fmt == 'pdf':
					result = self.HtmlToPdfService.format(jinja_output)
					content_type = "application/pdf"
				elif fmt == 'html':
					result = jinja_output
					content_type = "text/html"
				else:
					raise FormatError(format=fmt)

				atts.append((result, content_type, file_name))
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
		output = await self.JinjaService.format(body["template"], body["params"])
		await self.SlackOutputService.send(output, atts)


	async def render(self, template, params):
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
		except KeyError:
			L.warning("Failed to load or render a template (missing?)", struct_data={'template': template})
			raise

		_, extension = os.path.splitext(template)

		if extension == '.html':
			return utils.find_subject_in_html(jinja_output)

		elif extension == '.md':
			jinja_output, subject = utils.find_subject_in_md(jinja_output)
			html_output = self.MarkdownToHTMLService.format(jinja_output)
			if not html_output.startswith("<!DOCTYPE html>"):
				html_output = utils.normalize_body(html_output)
			return html_output, subject

		else:
			raise FormatError(format=extension)
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
