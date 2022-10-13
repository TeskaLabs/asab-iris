import os
import datetime
import logging

import asab.web.rest

import aiohttp
import aiohttp.web
import aiohttp.payload_streamer

from .. import utils

#

L = logging.getLogger(__name__)

#


class SendMailHandler(object):

	def __init__(self, app):
		web_app = app.WebContainer.WebApp
		web_app.router.add_put(r"/send_mail", self.send)

		self.Orchestrator = SendMailOrchestrator(app)

	@asab.web.rest.json_schema_handler({
		"type": "object",
		"required": [
			"to",
			"body"
		],
		"properties": {
			"to": {
				"type": "array",
				"items": {
					"type": "string",
				},
				"default": ['henry.hill@teskalabs.com'],
			},
			"cc": {
				"type": "array",
				"items": {
					"type": "string",
				},
				"default": ['charlie.chaplin@teskalabs.com'],
			},
			"bcc": {
				"type": "array",
				"items": {
					"type": "string",
				},
				"default": ['jimmy.conway@teskalabs.com'],
			},
			"subject": {
				"type": "string",
				"default": "Alert-reports",
			},
			"from": {
				"type": "string",
				"default": "tony.montana@teskalabs.com",
			},
			"body": {
				"type": "object",
				"required": [
					"template",
					"params"
				],
				"properties": {
					"template": {
						"type": "string",
						"default": "alert.md",
					},
					"params": {
						"type": "object",
						"default": {},
					}
				},
			},
			"attachments": {
				"type": "array",
				"items": {
					"type": "object",
					"required": [
						"template",
						"params",
						"format"
					],
					"properties": {
						"template": {
							"type": "string",
							"default": "alert.md",
						},
						"params": {
							"type": "object",
							"default": {},
						},
						"format": {
							"type": "string",
							"default": "html",
						}
					},
				},
			}
		},
	})
	async def send(self, request, *, json_data):
		"""
		This endpoint is for sending emails.
		```
		1) It collects the basic email info (to, cc, bcc, subject, from)
		2) It renders the email body based on the template
		3) Optionally it adds attachments:

			3.1) The attachment is renders by this service.

			3.2) The attachment is provided by the caller.

		```
		Example body:

		```
		{
			"to": ['Tony.Montana@Goodfellas.com'],
			"cc": ['Jimmy2.times@Goodfellas.com'],
			"bcc": ['Henry.Hill@Goodfellas.com'],
			"subject": "Lufthansa Hiest",
			"from": "Jimmy.Conway@Goodfellas.com",
			"body": {
				"template": "test.md",
				"params": {
					"Name": "Toddy Siciro"
			}
		},
		"attachments": [
			{
			"template": "test.md",
			"params": {
				"Name": "Michael Corleone"
				},
			"format": "pdf",
			"filename": "Made.pdf"
			}]
		}

		```
		Attached will be retrieved from request.conent when rendering the email is not required.

		Example of the email body template:
		```
		SUBJECT: Automated email for {{name}}

		Hi {{name}},

		this is a nice template for an email.
		It is {{time}} to leave.

		Br,
		Your automated ASAB report
		```

		It is a markdown template.
		---
		tags: ['Send mail']
		"""

		response = await self.Orchestrator.send_mail(
			email_to=json_data["to"],
			body_template=json_data["body"]["template"],
			email_cc=json_data.get("cc", []),  # Optional
			email_bcc=json_data.get("bcc", []),  # Optional
			email_subject=json_data.get("subject", None),  # Optional
			email_from=json_data.get("from"),
			body_params=json_data["body"].get("params", {}),  # Optional
			attachments=json_data.get("attachments", []),  # Optional
		)

		if response is True:
			return asab.web.rest.json_response(request, {"result": "OK"}, reason=200)
		else:
			return asab.web.rest.json_response(request, {"result": "ERROR"})


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
			L.info("Subject not present in body template. Using subject from configuration.")

		atts = []

		if len(attachments) == 0:
			L.info("No attachment's to render.")
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
					if a.get('format') == 'pdf':
						result = self.HtmlToPdfService.format(body)
						content_type = "application/pdf"
					elif a.get('format') == 'html':
						result = jinja_output
						content_type = "text/html"
					else:
						raise aiohttp.web.HTTPBadRequest(reason="Invalid format {}`".format(a.get('format')))
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
			raise aiohttp.web.HTTPBadRequest(reason="Please use content_type `application/octet-stream`")


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
