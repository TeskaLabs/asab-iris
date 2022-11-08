import os
import datetime
import logging

from .. import utils

#

L = logging.getLogger(__name__)

#


class SendMailOrchestrator(object):

	def __init__(self, app):

		# formatters
		self.JinjaService = app.get_service("JinjaService")
		self.HtmlToPdfService = app.get_service("HtmlToPdfService")
		self.MarkdownToHTMLService = app.get_service("MarkdownToHTMLService")

		# output
		self.SmtpService = app.get_service("SmtpService")


	async def send_mail(
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

		# Render a body
		body_html, email_subject_body = await self.render(body_template, body_params)

		if email_subject is None:
			email_subject = email_subject_body

		atts = []

		if len(attachments) == 0:
			L.debug("No attachment's to render.")

		else:
			for a in attachments:
				"""
				If there are 'params' we render 'template's' else we throw a sweet warning.
				If content-type is application/octet-stream we assume there is additional attachments in
				request else we raise bad-request error.
				"""
				params = a.get('params', None)
				if params is not None:
					# get file-name of the attachment
					file_name = self.get_file_name(a)
					jinja_output, result = await self.render(a['template'], params)

					# get pdf from html if present.
					fmt = a.get('format', 'html')
					if fmt == 'pdf':
						result = self.HtmlToPdfService.format(jinja_output)
						content_type = "application/pdf"
					elif fmt == 'html':
						result = jinja_output
						content_type = "text/html"
					else:
						raise ValueError("Invalid/unknown format '{}'".format(fmt))

					atts.append((result, content_type, file_name))

				else:
					# get attachment from request-content if present.
					content_type = a.get('content-type')
					if content_type is not None:
						result = await self.get_attachment_from_request_content(a, content_type)
						atts.append((result, content_type, file_name))
					else:
						L.info("No attachment's in request's content.")

		await self.SmtpService.send(
			email_from=email_from,
			email_to=email_to,
			email_cc=email_cc,
			email_bcc=email_bcc,
			email_subject=email_subject, 
			body=body_html,
			attachments=atts
		)


	async def render(self, template, params):
		"""
		This method renders templates based on the depending on the
		extension of template.

		Returns the html and optional subject line if found in the templat.

		jinja_output will be used for extracting subject.
		"""
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
			raise RuntimeError("Failed to render templates. Reason: Unknown extention '{}'".format(extension))


	async def get_attachment_from_request_content(self, req_content, content_type):
		"""
		This method extracts attachmenst from request's contant.
		if content type is not 'application/octet-stream'
		it raises HTTP bad=-req.
		"""
		if content_type == 'application/octet-stream':
			buffer = b""
			async for data, _ in req_content.iter_chunks():
				buffer += data
				if req_content.content.at_eof():
					result = buffer
					buffer = b""
				return result
		else:
			raise ValueError("Use content_type 'application/octet-stream'")


	def get_file_name(self, attachment):
		"""
		This method returns a file-name if provided in the attachment-dict.
		If not then the name of the file is current date with appropriate
		extensions.
		"""
		date = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
		if attachment.get('filename') is None:
			return "att-" + date + "." + attachment.get('format')
		elif attachment.get('content-type') == 'application/octet-stream':
			return "att-" + date + ".zip"
		else:
			return attachment.get('filename')
