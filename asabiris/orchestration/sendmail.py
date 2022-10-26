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
		email_to, body_template,
		email_cc=[], email_bcc=[], email_subject=None, email_from=None,
		body_params={},
		attachments=[],
	):
		# Render a body
		body, html = await self.render(body_template, body_params)
		email_subject_body, body = await self.extract_subject_body_from_html(body, body_template)

		if email_subject_body is not None:
			email_subject = email_subject_body
		else:
			L.debug("Subject not present in body template. Using subject from configuration.")

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
					template_path = a['template']
					jinja_output, result = await self.render(a['template'], params)
					# get subject of mail and it's body
					email_subject_body, body = await self.extract_subject_body_from_html(jinja_output, template_path)

					if email_subject_body is not None:
						email_subject = email_subject_body

					# get pdf from html if present.
					fmt = a.get('format')
					if fmt == 'pdf':
						result = self.HtmlToPdfService.format(body)
						content_type = "application/pdf"
					elif fmt == 'html':
						result = jinja_output
						content_type = "text/html"
					else:
						raise ValueError("Invalid/unknown format '{}'".format(fmt))

					# fill-up the tuple and add it to attachment list.
					attach_tuple = (result, content_type, file_name)
					atts.append(attach_tuple)

				else:
					# get attachment from request-content if present.
					content_type = a.get('content-type')
					if content_type is not None:
						result = await self.get_attachment_from_request_content(a, content_type)
						# fill-up the tuple and add it to attachment list.
						attach_tuple = (result, content_type, file_name)
						atts.append(attach_tuple)
					else:
						L.info("No attachment's in request's content.")

		return await self.SmtpService.send(
			email_to=email_to, body=body,
			email_cc=email_cc, email_bcc=email_bcc, email_subject=email_subject, email_from=email_from,
			attachments=atts
		)


	async def render(self, template, params):
		"""
			This method renders templates based on the depending on the
			extension of template.

			Returns the jinja_output, html.

			jinja_output will be used for extracting subject.
		"""
		try:
			jinja_output = await self.JinjaService.format(template, params)
		except KeyError:
			L.warning("Failed to load or render a template (missing?)", struct_data={'template': template})
			raise

		_, extension = os.path.splitext(template)

		if extension == '.html':
			return jinja_output, None

		elif extension == '.md':
			html = self.MarkdownToHTMLService.format(jinja_output)
			if not html.startswith("<!DOCTYPE html>"):
				html = utils.normalize_body(html)

			return jinja_output, html

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


	async def extract_subject_body_from_html(self, html, template_path):
		"""
			This method separates subject and body from html.
		"""

		_, extension = os.path.splitext(template_path)
		if '.md' in extension:
			subject, body = utils.find_subject_in_md(html)
		elif '.html' in extension:
			subject, body = utils.find_subject_in_html(html)
		else:
			raise RuntimeError("Failed to extract subject. Unknown extention '{}'".format(extension))

		return subject, body


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
