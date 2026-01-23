import logging

import jsonata

import asab.web.rest
import asab.contextvars

import aiohttp.web
import aiohttp.payload_streamer

from ..schemas.emailschema import email_schema
from ..schemas.slackschema import slack_schema
from ..schemas.smsschema import sms_schema
from ..schemas.teamsschema import teams_schema

from ..errors import ASABIrisError, ErrorCode

import slack_sdk.errors
#

L = logging.getLogger(__name__)

#


class WebHandler(object):

	def __init__(self, app):
		self.App = app

		web_app = app.WebContainer.WebApp
		web_app.router.add_get(r"/features", self.get_features)
		web_app.router.add_put(r"/send_email", self.send_email)
		web_app.router.add_put(r"/send_mail", self.send_email)  # This one is for backward compatibility
		web_app.router.add_put(r"/send_email_jsonata/{jsonata}", self.send_email_jsonata)
		web_app.router.add_post(r"/send_email_jsonata/{jsonata}", self.send_email_jsonata)  # PUT and POST are intetionally the same
		web_app.router.add_put(r"/render", self.render)
		web_app.router.add_put(r"/send_sms", self.send_sms)
		web_app.router.add_put(r"/send_push", self.send_push)
		web_app.router.add_put(r"/send_slack", self.send_slack)
		web_app.router.add_put(r"/send_msteams", self.send_msteams)
		web_app.router.add_get(r"/authorize_ms365", self.authorize_ms365)


	async def get_features(self, request):
		"""
		Return the application's features (enabled orchestrators).
		"""
		response = {
			"orchestrators": list(self.App.enabled_orchestrators()),
		}
		return asab.web.rest.json_response(request, response)

	@asab.web.tenant.allow_no_tenant
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
			"filename": "Alert.pdf"
			}]
		}

		```
		Attached will be retrieved from request. Content when rendering the email is not required.

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
		return await self._send_email(request, json_data)

	@asab.web.tenant.allow_no_tenant
	async def send_email_jsonata(self, request):
		"""
		This endpoint is for sending emails - JSONata template is applied first to the request body.

		It applies JSONata template (stored in `/Templates/JSONata`) to the request body and then the output is used as a body to /send_email endpoint.
		It allows to transform arbitrary JSON data into a valid email body.

		Build the JSONata template at https://try.jsonata.org
		"""
		jsonata_template = request.match_info["jsonata"]
		assert '..' not in jsonata_template, "JSONata template cannot contain '..'"
		assert '/' not in jsonata_template, "JSONata template cannot contain '/'"

		async with self.App.LibraryService.open('/Templates/JSONata/' + jsonata_template + '.txt') as b:
			expr = jsonata.Jsonata(b.read().decode("utf-8"))

		result = expr.evaluate(await request.json())
		# TODO: Apply email_schema to the result
		return await self._send_email(request, json_data=result)

	async def _send_email(self, request, json_data):
		# If neither SMTP nor MS365 was set up, fail early
		if self.App.SendEmailOrchestrator is None:
			L.info("Email orchestrator is not enabled.")
			return aiohttp.web.json_response(
				{
					"result": "FAILED",
					"error": "Email service is not configured."
				},
				status=400
			)

		tenant = json_data.get("tenant", None)
		current_tenant = asab.contextvars.Tenant.get(None)
		token = None

		# Only set tenant from body if there is no tenant already set from the request context
		if tenant is not None and current_tenant is None:
			token = asab.contextvars.Tenant.set(tenant)

		try:
			await self.App.SendEmailOrchestrator.send_email(
				email_to=json_data.get("to", None),
				body_template=json_data["body"]["template"],
				body_template_wrapper=json_data["body"].get("wrapper", None),
				email_cc=json_data.get("cc", []),  # Optional
				email_bcc=json_data.get("bcc", []),  # Optional
				email_subject=json_data.get("subject", None),  # Optional
				email_from=json_data.get("from"),
				body_params=json_data["body"].get("params", {}),  # Optional
				attachments=json_data.get("attachments", []),
			)
		except ASABIrisError as e:
			# Map ErrorCode to HTTP status codes
			status_code = self.map_error_code_to_status(e.ErrorCode)

			response = {
				"result": "ERROR",
				"error": e.Errori18nKey,
				"error_dict": e.ErrorDict,
				"tech_err": e.TechMessage
			}
			return aiohttp.web.json_response(response, status=status_code)

		except Exception as e:
			L.exception(str(e))
			bad_response = {
				"result": "FAILED",
				"error": {
					"message": str(e),
					"error_code": "GENERAL_ERROR",
				}
			}
			return asab.web.rest.json_response(request, bad_response, status=400)
		finally:
			if token is not None:
				asab.contextvars.Tenant.reset(token)

		return asab.web.rest.json_response(request, {"result": "OK"})

	@asab.web.tenant.allow_no_tenant
	@asab.web.rest.json_schema_handler(slack_schema)
	async def send_slack(self, request, *, json_data):
		"""
		This endpoint is for sending slack-notification.
		```
		```
		Example body:

		```
		{
			"type": "slack",
			"body": {
				"template": "/Templates/Slack/message.md",
				"params": {
					"Name": "Toddy Siciro"
			}
		},
		---
		tags: ['Send alerts']
		"""
		if self.App.SendSlackOrchestrator is None:
			L.info("Slack orchestrator is not initialized. This feature is optional and not configured.")
			return aiohttp.web.json_response(
				{
					"result": "FAILED",
					"error": "Slack service is not configured."
				},
				status=400
			)

		tenant = json_data.get("tenant", None)
		current_tenant = asab.contextvars.Tenant.get(None)
		token = None

		if tenant is not None and current_tenant is None:
			token = asab.contextvars.Tenant.set(tenant)

		try:
			await self.App.SendSlackOrchestrator.send_to_slack(json_data)
		except ASABIrisError as e:
			# Map ErrorCode to HTTP status codes
			status_code = self.map_error_code_to_status(e.ErrorCode)

			response = {
				"result": "ERROR",
				"error": e.Errori18nKey,
				"error_dict": e.ErrorDict,
				"tech_err": e.TechMessage
			}
			return aiohttp.web.json_response(response, status=status_code)

		except slack_sdk.errors.SlackApiError as e:
			raise aiohttp.web.HTTPServiceUnavailable(text="{}".format(e))
		# More specific exception handling goes here so that the service provides nice output
		except Exception as e:
			L.exception(str(e))
			response = {
				"result": "FAILED",
				"error": {
					"message": str(e),
					"error_code": "GENERAL_ERROR",
				}
			}
			return aiohttp.web.json_response(response, status=400)
		finally:
			if token is not None:
				asab.contextvars.Tenant.reset(token)

		return asab.web.rest.json_response(request, {"result": "OK"})

	@asab.web.tenant.allow_no_tenant
	@asab.web.rest.json_schema_handler(teams_schema)
	async def send_msteams(self, request, *, json_data):
		"""
		This endpoint is for sending slack-notification.
		```
		```
		Example body:

		```
				{
				"title": "Testing iris",
				"body": {
					"template": "/Templates/MSTeams/alert.md",
					"params": {
					"message": "I am testing a template",
					"event": "Iris-Event"
				}
			}
		}

		---
		tags: ['Send MS Teams']
		"""
		if self.App.SendMSTeamsOrchestrator is None:
			L.info("MSTeams orchestrator is not initialized. This feature is optional and not configured.")
			return aiohttp.web.json_response(
				{
					"result": "FAILED",
					"error": "MSTeams service is not configured."
				},
				status=400
			)

		tenant = json_data.get("tenant", None)
		current_tenant = asab.contextvars.Tenant.get(None)
		token = None
		if tenant is not None and current_tenant is None:
			token = asab.contextvars.Tenant.set(tenant)

		try:
			await self.App.SendMSTeamsOrchestrator.send_to_msteams(json_data)
		except ASABIrisError as e:
			# Map ErrorCode to HTTP status codes
			status_code = self.map_error_code_to_status(e.ErrorCode)

			response = {
				"result": "ERROR",
				"error": e.Errori18nKey,
				"error_dict": e.ErrorDict,
				"tech_err": e.TechMessage
			}
			return aiohttp.web.json_response(response, status=status_code)

		except Exception as e:
			L.exception(str(e))
			response = {
				"result": "FAILED",
				"error": {
					"message": str(e),
					"error_code": "GENERAL_ERROR",
				}
			}
			return aiohttp.web.json_response(response, status=400)
		finally:
			if token is not None:
				asab.contextvars.Tenant.reset(token)

		return asab.web.rest.json_response(request, {"result": "OK"})

	L = logging.getLogger(__name__)

	@asab.web.tenant.allow_no_tenant
	@asab.web.rest.json_schema_handler({"type": "object"})
	async def render(self, request, *, json_data):
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
		---
		parameters: [{"name": "format", "in": "query", "description": "Format of the document"}, {"name": "template", "in": "query", "description": "Reference to the template"}]
		"""
		fmt = request.query.get("format", "html")
		template = request.query.get("template", None)
		template_data = await request.json()

		tenant = json_data.get("tenant", None)
		current_tenant = asab.contextvars.Tenant.get(None)
		token = None

		if tenant is not None and current_tenant is None:
			token = asab.contextvars.Tenant.set(tenant)


		# Render a body
		try:
			html = await self.App.RenderReportOrchestrator.render(template, template_data)
		except ASABIrisError as e:
			# Map ErrorCode to HTTP status codes
			status_code = self.map_error_code_to_status(e.ErrorCode)

			response = {
				"result": "ERROR",
				"error": e.Errori18nKey,
				"error_dict": e.ErrorDict,
				"tech_err": e.TechMessage
			}
			return aiohttp.web.json_response(response, status=status_code)
		except Exception as e:
			L.exception(str(e))
			response = {
				"result": "FAILED",
				"error": {
					"message": str(e),
					"error_code": "GENERAL_ERROR",
				}
			}
			return aiohttp.web.json_response(response, status=400)
		finally:
			if token is not None:
				asab.contextvars.Tenant.reset(token)

		# get pdf from html if present.
		if fmt == 'pdf':
			content_type = "application/pdf"
			pdf = self.App.PdfFormatterService.format(html)
		elif fmt == 'html':
			content_type = "text/html"
		else:
			raise aiohttp.web.HTTPBadRequest(text="Invalid/unknown conversion format: '{}'".format(fmt))

		return aiohttp.web.Response(
			content_type=content_type,
			body=html if content_type == "text/html" else file_sender(pdf)
		)

	@asab.web.tenant.allow_no_tenant
	@asab.web.rest.json_schema_handler(sms_schema)
	async def send_sms(self, request, *, json_data):
		"""Send an SMS message to the phone number specified in the request body.

			Args:
				request: The HTTP request object.
				json_data: A dictionary containing the following keys:
					- phone (int): The phone number to send the SMS message to.
					- message_body (str): The content of the SMS message.

			Returns:
				A JSON response with a "result" key set to "OK" and a "data" key containing the result of the SMSOutputService.
		```
		localhost:8080/send_sms

		Example body:

		```
				{
				"Phone": "123456789",
				"body": {
					"template": "/Templates/SMS/alert.md",
					"params": {
					"message": "I am testing a template",
					"event": "Iris-Event"
				}
			}
		}

		---
		```
		"""
		if self.App.SendSMSOrchestrator is None:
			L.info("SMS orchestrator is not initialized. This feature is optional and not configured.")
			return aiohttp.web.json_response(
				{
					"result": "FAILED",
					"error": "SMS service is not configured."
				},
				status=400
			)

		tenant = json_data.get("tenant", None)
		current_tenant = asab.contextvars.Tenant.get(None)
		token = None

		if tenant is not None and current_tenant is None:
			token = asab.contextvars.Tenant.set(tenant)

		# Render a body
		try:
			await self.App.SendSMSOrchestrator.send_sms(json_data)
		except ASABIrisError as e:
			# Map ErrorCode to HTTP status codes
			status_code = self.map_error_code_to_status(e.ErrorCode)

			response = {
				"result": "ERROR",
				"error": e.Errori18nKey,
				"error_dict": e.ErrorDict,
				"tech_err": e.TechMessage
			}
			return aiohttp.web.json_response(response, status=status_code)

		except Exception as e:
			L.exception(str(e))
			response = {
				"result": "FAILED",
				"error": {
					"message": str(e),
					"error_code": "GENERAL_ERROR",
				}
			}
			return aiohttp.web.json_response(response, status=400)
		finally:
			if token is not None:
				asab.contextvars.Tenant.reset(token)

		return asab.web.rest.json_response(request, {"result": "OK"})

	@asab.web.rest.json_schema_handler({"type": "object"})
	async def send_push(self, request, *, json_data):
		"""
		Send a push notification via ntfy.sh.
		Example body:
		```
		{
			"topic": "send_ph",
			"body": {
				"template": "/Templates/Push/alert.txt",
				"params": {
					"title": "IRIS Alert",
					"message": "Library sync failed at {{time}}",
					"time": "2025-10-23 10:40 UTC"
				}
			},
			"tenant": "pharma-dev"
		}
		```
		---
		tags: ['Send Push']
		"""
		if self.App.SendPushOrchestrator is None:
			L.info("Push orchestrator is not initialized.")
			return aiohttp.web.json_response(
				{
					"result": "FAILED",
					"error": "Push service is not configured."
				},
				status=400
			)

		try:
			await self.App.SendPushOrchestrator.send_push(json_data)
		except ASABIrisError as e:
			status_code = self.map_error_code_to_status(e.ErrorCode)
			response = {
				"result": "ERROR",
				"error": e.Errori18nKey,
				"error_dict": e.ErrorDict,
				"tech_err": e.TechMessage
			}
			return aiohttp.web.json_response(response, status=status_code)
		except Exception as e:
			L.exception(str(e))
			response = {
				"result": "FAILED",
				"error": {
					"message": str(e),
					"error_code": "GENERAL_ERROR"
				}
			}
			return aiohttp.web.json_response(response, status=400)

		return asab.web.rest.json_response(request, {"result": "OK"})

	def map_error_code_to_status(self, error_code):
		"""
		Maps error codes to HTTP status codes.
		"""
		error_code_mapping = {
			ErrorCode.INVALID_FORMAT: 400,
			ErrorCode.JINJA2_ERROR: 400,
			ErrorCode.RENDERING_ERROR: 400,
			ErrorCode.TEMPLATE_NOT_FOUND: 404,
			ErrorCode.TEMPLATE_IS_DISABLED: 403,
			ErrorCode.SERVER_ERROR: 502,
			ErrorCode.SLACK_API_ERROR: 401,
			ErrorCode.SMTP_CONNECTION_ERROR: 502,
			ErrorCode.SMTP_AUTHENTICATION_ERROR: 401,
			ErrorCode.SMTP_RESPONSE_ERROR: 400,
			ErrorCode.SMTP_SERVER_DISCONNECTED: 502,
			ErrorCode.SMTP_GENERIC_ERROR: 400,
			ErrorCode.SMTP_TIMEOUT: 504,
			ErrorCode.INVALID_SERVICE_CONFIGURATION: 400,
			ErrorCode.LIBRARY_NOT_READY: 503,
			ErrorCode.SLACK_CHANNEL_NOT_FOUND: 404,
			ErrorCode.INVALID_REQUEST: 400,
			ErrorCode.AUTHENTICATION_FAILED: 401,
		}

		return error_code_mapping.get(error_code, 400)  # Default to 400 Bad Request

	@asab.web.tenant.allow_no_tenant
	async def authorize_ms365(self, request):
		"""
		OAuth 2.0 Authorization Code Flow handler.
		Serves both as the initiator (no ?code) and the callback (with ?code).
		"""
		# Get the actual service instance from the app
		m365_service = self.App.get_service("M365EmailOutputService")
		if m365_service is None:
			# Service not configured
			return aiohttp.web.json_response(
				{
					"result": "ERROR",
					"message": "M365EmailOutputService is not configured.",
				},
				status=500,
			)

		# 1) First call: no ?code -> redirect user to Microsoft login
		if "code" not in request.query:
			try:
				auth_url = await m365_service.build_authorization_uri()
			except ASABIrisError as e:
				# Nicely propagate Iris errors
				return aiohttp.web.json_response(
					{
						"result": "ERROR",
						"error": e.Errori18nKey,
						"error_dict": e.ErrorDict,
						"tech_err": e.TechMessage,
					},
					status=400,
				)
			# Redirect browser to Microsoft login page
			return aiohttp.web.HTTPFound(auth_url)

		# 2) Callback from Microsoft: we have ?code=...
		code = request.query["code"]
		state = request.query.get("state", None)

		try:
			await m365_service.exchange_code_for_tokens(code, state)
		except ASABIrisError as e:
			return aiohttp.web.json_response(
				{
					"result": "ERROR",
					"error": e.Errori18nKey,
					"error_dict": e.ErrorDict,
					"tech_err": e.TechMessage,
				},
				status=400,
			)
		except Exception as e:
			L.exception("Unexpected error during MS365 token exchange: %s", e)
			return aiohttp.web.json_response(
				{
					"result": "ERROR",
					"message": "Internal Server Error in authorize_ms365",
				},
				status=500,
			)

		# IMPORTANT: return something to the browser
		return aiohttp.web.Response(
			text=(
				"MS365 delegated authorization successful. "
				"You can close this window and retry sending the email from Iris."
			)
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
