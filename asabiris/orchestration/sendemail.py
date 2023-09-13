import asab
import os
import base64
import datetime
import logging
import jinja2.exceptions

from .. import utils
from .. exceptions import PathError, FormatError
#

L = logging.getLogger(__name__)


#


class SendEmailOrchestrator(object):

	def __init__(self, app):

		# formatters
		self.JinjaService = app.get_service("JinjaService")
		self.HtmlToPdfService = app.get_service("HtmlToPdfService")
		self.MarkdownToHTMLService = app.get_service("MarkdownToHTMLService")

		# output
		self.SmtpService = app.get_service("SmtpService")

	async def send_email(
		self, *,
		email_to,
		email_from=None,
		email_cc=[],
		email_bcc=[],
		email_subject=None,
		body_template,
		body_params={},
		attachments=[],
	):
		"""
		It sends an email

		:param email_to: The email address to send the email to
		:param email_from: The email address to send the email from. If not provided, the default email
		address will be used
		:param email_cc: A list of email addresses to CC
		:param email_bcc: A list of email addresses to send a blind carbon copy to
		:param email_subject: The subject of the email
		:param body_template: The name of the template to use for the body of the email
		:param body_params: A dictionary of parameters to pass to the template
		:param attachments: a list of tuples, each tuple containing the filename and the file contents
		"""

		render_failed = False

		# Render a body
		body_html, email_subject_body, render_failed = await self.render(body_template, body_params, email_to, render_failed)

		if email_subject is None or email_subject == '':
			email_subject = email_subject_body

		if render_failed("jinja", "failsafe"):
			attachments = []

		atts = []

		if len(attachments) == 0:
			L.debug("No attachment's to render.")

		else:
			for a in attachments:
				# If there are 'template' we render 'template's' else we throw a sweet warning.
				# If content-type is application/octet-stream we assume there is additional attachments in request else we raise bad-request error.
				template = a.get('template', None)

				if template is not None:
					params = a.get('params', {})
					# templates must be stores in /Templates/Email
					if not template.startswith("/Templates/Email/"):
						raise PathError(use_case='Email', invalid_path=template)

					# get file-name of the attachment
					file_name = self.get_file_name(a)

					jinja_output, result, render_failed = await self.render(template, params, email_to, render_failed)

					if render_failed:
						atts = []
						break

					# get pdf from html if present.
					fmt = a.get('format', 'html')
					if fmt == 'pdf':
						result = self.HtmlToPdfService.format(jinja_output).read()
						content_type = "application/pdf"
					elif fmt == 'html':
						result = jinja_output.encode("utf-8")
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

				L.warning("Unknown/invalid attachment.")

		await self.SmtpService.send(
			email_from=email_from,
			email_to=email_to,
			email_cc=email_cc,
			email_bcc=email_bcc,
			email_subject=email_subject,
			body=body_html,
			attachments=atts
		)

	async def render(self, template, params, email_to, render_failed):
		"""
		This method renders templates based on the depending on the
		extension of template.

		Returns the html and optional subject line if found in the template.

		jinja_output will be used for extracting subject.
		"""
		try:
			# templates must be stored in /Templates/Emails
			if not template.startswith("/Templates/Email/"):
				raise PathError(use_case='Email', invalid_path=template)

			jinja_output = await self.JinjaService.format(template, params)

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


		except jinja2.exceptions.TemplateError as e:
			L.warning("Jinja2 Rendering Error: {}".format(str(e)))
			# render failed
			render_failed = True
			if asab.Config.get("jinja", "failsafe"):
				# Get the current timestamp
				current_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

				email_addresses = [recipient.split('<')[1].strip('>') for recipient in email_to]
				# Prepare the error details including timestamp, recipients, and error message
				error_details = (
					"Timestamp: {}\n"
					"Recipients: {}\n"
					"Error Message: {}\n"
				).format(current_timestamp, email_addresses, str(e))

				# User-friendly error message
				error_message = (
					"Hello!<br><br>"
					"We encountered an issue while processing your request. "
					"Please review your input and try again.<br><br>"
					"Thank you!<br>"
					"<br>Error Details:<br><pre style='font-family: monospace;'>{}</pre>".format(
						error_details
					)
				)

				# Add LogMan signature with HTML line breaks
				error_message += "<br>Best regards,<br>LogMan.io"

				subject = "Error Processing Request"

				return error_message, subject, render_failed

		except Exception as e:
			L.warning("Jinja2 Rendering Error: {}".format(str(e)))
			# rendering failed
			render_failed = True
			if asab.Config.get("jinja", "failsafe"):
				# Get the current timestamp
				current_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

				email_addresses = [recipient.split('<')[1].strip('>') for recipient in email_to]
				# Prepare the error details including timestamp, recipients, and error message
				error_details = (
					"Timestamp: {}\n"
					"Recipients: {}\n"
					"Error Message: {}\n"
				).format(current_timestamp, email_addresses, str(e))

				# User-friendly error message
				error_message = (
					"Hello!<br><br>"
					"We encountered an issue while processing your request. "
					"Please review your input and try again.<br><br>"
					"Thank you!<br>"
					"<br>Error Details:<br><pre style='font-family: monospace;'>{}</pre>".format(
						error_details
					)
				)

				# Add LogMan signature with HTML line breaks
				error_message += "<br>Best regards,<br>LogMan.io"

				subject = "Error Processing Request"

				return error_message, subject, render_failed

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
