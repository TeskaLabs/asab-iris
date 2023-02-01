import logging

import asab.web.rest

import aiohttp.web
import aiohttp.payload_streamer

import jinja2

from ..schemas.emailschema import email_schema
from ..schemas.slackschema import slack_schema

from ..exceptions import SMTPDeliverError

#

L = logging.getLogger(__name__)

#


class WebHandler(object):

	def __init__(self, app):
		self.App = app

		web_app = app.WebContainer.WebApp
		web_app.router.add_put(r"/send_email", self.send_email)
		web_app.router.add_put(r"/send_mail", self.send_email)  # This one is for backward compatibility
		web_app.router.add_put(r"/render", self.render)
		web_app.router.add_put(r"/send_slack", self.send_alert)


	@asab.web.rest.json_schema_handler(email_schema)
	async def send_email(self, request, *, json_data):
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
				"template": "/Templates/Emails/test.md",
				"params": {
					"Name": "Toddy Siciro"
			}
		},
		"attachments": [
			{
			"template": "/Templates/Emails/hello.html",
			"params": {
				"Name": "Michael Corleone"
				},
			"format": "pdf",
			"filename": "dd-mm--yy.pdf"
			}]
		}

		```
		Attached will be retrieved from request.content when rendering the email is not required.

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

		try:
			await self.App.SendEmailOrchestrator.send_email(
				email_to=json_data["to"],
				body_template=json_data["body"]["template"],
				email_cc=json_data.get("cc", []),  # Optional
				email_bcc=json_data.get("bcc", []),  # Optional
				email_subject=json_data.get("subject", None),  # Optional
				email_from=json_data.get("from"),
				body_params=json_data["body"].get("params", {}),  # Optional
				attachments=json_data.get("attachments", []),  # Optional
			)

		except ValueError as e:
			raise aiohttp.web.HTTPNotFound(text="{}".format(e))

		except KeyError as e:
			raise aiohttp.web.HTTPNotFound(text="{}".format(e))

		except jinja2.exceptions.UndefinedError as e:
			raise aiohttp.web.HTTPBadRequest(text="Jinja2 error: {}".format(e))

		except SMTPDeliverError:
			raise aiohttp.web.HTTPServiceUnavailable(text="SMTP error")

		# More specific exception handling goes here so that the service provides nice output
		return asab.web.rest.json_response(request, {"result": "OK"})

	@asab.web.rest.json_schema_handler(slack_schema)
	async def send_alert(self, request, *, json_data):
		"""
		This endpoint is for sending slack-notification.
		```
		```
		Example body:

		```
		{
			"type": "slack",
			"body": {
				"template": "/Templates/Slack/alert.md",
				"params": {
					"Name": "Toddy Siciro"
			}
		},
		---
		tags: ['Send alerts']
		"""

		try:
			await self.App.SendSlackOrchestrator.send_to_slack(json_data)

		except jinja2.exceptions.UndefinedError as e:
			raise aiohttp.web.HTTPBadRequest(text="Jinja2 error: {}".format(e))

		except ValueError as e:
			raise aiohttp.web.HTTPNotFound(text="{}".format(e))

		# More specific exception handling goes here so that the service provides nice output

		return asab.web.rest.json_response(request, {"result": "OK"})


	# TODO: JSON schema
	async def render(self, request):
		"""
		This endpoint renders request body into template based on the format specified.
		Example:
		```
		localhost:8080/render?format=pdf&template=/Templates/General/test.md

		format: pdf/html

		template : Location of template in the library (e.g. on the filesystem)
		```
		body example:
		```
		{
			"order_id":123,
			"order_creation_date":"2020-01-01 14:14:52",
			"company_name":"Test Company",
			"city":"Mumbai",
			"state":"MH"
		}
		```
		"""
		fmt = request.query.get("format", "html")
		template = request.query.get("template", None)
		template_data = await request.json()

		# Render a body
		try:
			html = await self.App.RenderReportOrchestrator.render(template, template_data)
		except ValueError as e:
			raise aiohttp.web.HTTPNotFound(text="{}".format(e))

		# get pdf from html if present.
		if fmt == 'pdf':
			content_type = "application/pdf"
			pdf = self.App.PdfFormatterService.format(html)
		elif fmt == 'html':
			content_type = "text/html"
		else:
			raise ValueError("Invalid/unknown format: '{}'".format(fmt))

		return aiohttp.web.Response(
			content_type=content_type,
			body=html if content_type == "text/html" else file_sender(pdf)
		)


@aiohttp.payload_streamer.streamer
async def file_sender(writer, pdf_content):
	"""
	This function will read large file chunk by chunk and send it through HTTP
	without reading them into memory
	"""
	while True:
		chunk = pdf_content.read(2048)
		if chunk is None or len(chunk) == 0:
			break
		await writer.write(chunk)
