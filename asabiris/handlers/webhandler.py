import logging

import jsonata

import asab.web.rest
import asab.contextvars

import aiohttp.web
import aiohttp.payload_streamer

from ..schemas.emailschema import email_schema
from ..schemas.mattermostschema import mattermost_schema
from ..schemas.slackschema import slack_schema
from ..schemas.smsschema import sms_schema
from ..schemas.teamsschema import teams_schema
from ..schemas.pushschema import push_schema

from ..errors import ASABIrisError, ErrorCode

try:
	from slack_sdk.errors import SlackApiError
except ModuleNotFoundError:
	class SlackApiError(Exception):
		pass
#

L = logging.getLogger(__name__)

#


class WebHandler(object):
	"""
	REST API for document rendering and outbound notifications.

	Each send endpoint returns `{"result": "OK"}` on success. When a channel is
	not configured, the endpoint responds with HTTP 400 and
	`{"result": "FAILED", "error": "..."}`.
	"""

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
		web_app.router.add_put(r"/send_mattermost", self.send_mattermost)
		web_app.router.add_put(r"/send_msteams", self.send_msteams)
		web_app.router.add_get(r"/authorize_ms365", self.authorize_ms365)


	@asab.web.tenant.allow_no_tenant
	async def get_features(self, request):
		"""
		List notification channels enabled in the current Iris instance.

		The response contains orchestrator names such as `email`, `slack`,
		`mattermost`, `msteams`, `sms`, `push`, and `render-report`. Channels
		that are not configured are omitted from the list.

		Example response:

		```json
		{
			"orchestrators": ["email", "slack", "render-report"]
		}
		```
		---
		tags: ['Features']
		responses:
			'200':
				description: Enabled orchestrators.
				content:
					application/json:
						schema:
							type: object
							required: [orchestrators]
							properties:
								orchestrators:
									type: array
									items:
										type: string
									example: ["email", "slack", "render-report"]
		"""
		response = {
			"orchestrators": list(self.App.enabled_orchestrators()),
		}
		return asab.web.rest.json_response(request, response)

	@asab.web.tenant.allow_no_tenant
	@asab.web.rest.json_schema_handler(email_schema)
	async def send_email(self, request, *, json_data):
		"""
		Send one email defined by the request JSON payload.

		The request contract covers message content only:
		1. collect recipients and optional headers (`to`, `cc`, `bcc`, `subject`, `from`)
		2. render the email body from a template under `/Templates/Email/`
		3. optionally render or attach files from `/Templates/Attachment/` or caller-supplied Base64 content

		Transport behavior such as direct SMTP, SMTP via HTTP CONNECT proxy, or MS365
		is selected by server-side configuration and is not part of the request body.

		Example body:

		```json
		{
			"to": ["tony.montana@goodfellas.com"],
			"cc": ["jimmy.conway@goodfellas.com"],
			"bcc": ["henry.hill@goodfellas.com"],
			"subject": "Lufthansa Heist",
			"from": "jimmy.conway@goodfellas.com",
			"body": {
				"template": "/Templates/Email/test.md",
				"params": {
					"name": "Toddy Siciro"
				}
			},
			"attachments": [
				{
					"template": "/Templates/Attachment/hello.html",
					"params": {
						"name": "Michael Corleone"
					},
					"format": "pdf",
					"filename": "Alert.pdf"
				}
			]
		}
		```

		Example of an email body template:

		```text
		SUBJECT: Automated email for {{name}}

		Hi {{name}},

		This is a nice template for an email.
		It is {{time}} to leave.

		Br,
		Your automated ASAB report
		```

		On success returns `{"result": "OK"}`. Transport (SMTP, SMTP via proxy, or
		MS365) is selected by server configuration, not by the request body.

		`/send_mail` is an alias of this endpoint kept for backward compatibility.
		---
		tags: ['E-Mail']
		responses:
			'200':
				description: Email accepted for delivery.
				content:
					application/json:
						schema:
							type: object
							properties:
								result:
									type: string
									example: OK
			'400':
				description: Invalid payload, email service not configured, or SMTP/MS365 error.
				content:
					application/json:
						schema:
							type: object
							properties:
								result:
									type: string
									enum: [FAILED, ERROR]
								error:
									oneOf:
										- type: string
										- type: object
			'401':
				description: SMTP or MS365 authentication failed.
			'403':
				description: Template is disabled.
			'404':
				description: Template not found.
			'502':
				description: Upstream mail server error.
			'504':
				description: SMTP timeout.
		"""
		return await self._send_email(request, json_data)

	@asab.web.tenant.allow_no_tenant
	async def send_email_jsonata(self, request):
		"""
		Transform the request body with a JSONata template, then send the result via `/send_email`.

		JSONata templates live under `/Templates/JSONata/` and must evaluate to an
		object compatible with the `/send_email` request contract.

		Path parameter `{jsonata}` is the template file name without the `.txt`
		extension (for example, `alert` loads `/Templates/JSONata/alert.txt`).

		Both PUT and POST are supported and behave identically.

		Example request to `/send_email_jsonata/alert`:

		```json
		{
			"customer": "Acme Corp",
			"severity": "high"
		}
		```

		The JSONata template transforms the payload above into the `/send_email`
		shape before delivery.
		---
		tags: ['E-Mail']
		responses:
			'200':
				description: Email accepted for delivery.
				content:
					application/json:
						schema:
							type: object
							properties:
								result:
									type: string
									example: OK
			'400':
				description: Invalid JSONata template name, invalid payload, or email delivery error.
		"""
		jsonata_template = request.match_info["jsonata"]
		if '..' in jsonata_template or '/' in jsonata_template:
			raise aiohttp.web.HTTPBadRequest(text="Invalid JSONata template name.")

		async with self.App.LibraryService.open('/Templates/JSONata/' + jsonata_template + '.txt') as b:
			expr = jsonata.Jsonata(b.read().decode("utf-8"))

		result = expr.evaluate(await request.json())
		# TODO: Apply email_schema to the result
		return await self._send_email(request, json_data=result)

	async def _send_email(self, request, json_data):
		# If neither SMTP nor MS365 was set up, fail early
		if self.App.SendEmailOrchestrator is None:
			L.info(
				"Email send request rejected because no email provider is configured. Configure [smtp] host or [m365_email], or expect HTTP 400 responses.",
			)
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
			L.exception(
				"Unexpected error while processing email send request; HTTP 400 returned to the client.",
				struct_data={"endpoint": "send_email", "tenant": tenant, "template": json_data.get("body", {}).get("template")},
			)
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
		Send a Slack message rendered from a template under `/Templates/Slack/`.

		The message can target the default configured channel, a named channel,
		or a channel/member ID. Optional attachments are supported.

		Example body:

		```json
		{
			"type": "slack",
			"body": {
				"template": "/Templates/Slack/message.md",
				"params": {
					"name": "Toddy Siciro",
					"error": "None"
				},
				"channel": "alerts"
			}
		}
		```

		On success returns `{"result": "OK"}`.
		---
		tags: ['Slack']
		responses:
			'200':
				description: Message accepted for delivery.
				content:
					application/json:
						schema:
							type: object
							properties:
								result:
									type: string
									example: OK
			'400':
				description: Invalid payload, Slack not configured, or Slack API error.
			'401':
				description: Slack authentication failed.
			'404':
				description: Template or Slack channel not found.
			'503':
				description: Slack service unavailable.
		"""
		if self.App.SendSlackOrchestrator is None:
			L.info(
				"Slack send request rejected because Slack is not configured. Add [slack] configuration or expect HTTP 400 responses.",
			)
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

		except SlackApiError as e:
			raise aiohttp.web.HTTPServiceUnavailable(text="{}".format(e))
		# More specific exception handling goes here so that the service provides nice output
		except Exception as e:
			L.exception(
				"Unexpected error while processing Slack send request; HTTP 400 returned to the client.",
				struct_data={"endpoint": "send_slack", "tenant": tenant, "template": json_data.get("body", {}).get("template")},
			)
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
		Send a Microsoft Teams message rendered from a template under `/Templates/MSTeams/`.

		Delivery uses the incoming webhook configured in `[msteams] webhook_url`.

		Example body:

		```json
		{
			"type": "msteams",
			"title": "Testing Iris",
			"body": {
				"template": "/Templates/MSTeams/alert.md",
				"params": {
					"message": "I am testing a template",
					"event": "Iris-Event"
				}
			}
		}
		```

		On success returns `{"result": "OK"}`.
		---
		tags: ['Microsoft Teams']
		responses:
			'200':
				description: Message accepted for delivery.
				content:
					application/json:
						schema:
							type: object
							properties:
								result:
									type: string
									example: OK
			'400':
				description: Invalid payload or Microsoft Teams not configured.
		"""
		if self.App.SendMSTeamsOrchestrator is None:
			L.info(
				"Microsoft Teams send request rejected because MS Teams is not configured. Add [msteams] webhook_url or expect HTTP 400 responses.",
			)
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
			L.exception(
				"Unexpected error while processing Microsoft Teams send request; HTTP 400 returned to the client.",
				struct_data={"endpoint": "send_msteams", "tenant": tenant, "template": json_data.get("body", {}).get("template")},
			)
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
	@asab.web.rest.json_schema_handler(mattermost_schema)
	async def send_mattermost(self, request, *, json_data):
		"""
		Send a Mattermost notification to a channel or as a direct message.

		Templates must live under `/Templates/Mattermost/`. Provide `channel_id`
		to post to a channel, or `username` to send a direct message. When
		neither is supplied, the configured `security_channel_id` is used.

		Example body:

		```json
		{
			"type": "mattermost",
			"channel_id": "security_channel_id",
			"body": {
				"template": "/Templates/Mattermost/message.md",
				"params": {
					"user.name": "alice",
					"event.code": "HIP_Sentinel_Fail"
				}
			}
		}
		```

		On success returns `{"result": "OK"}`.
		---
		tags: ['Mattermost']
		responses:
			'200':
				description: Message accepted for delivery.
				content:
					application/json:
						schema:
							type: object
							properties:
								result:
									type: string
									example: OK
			'400':
				description: Invalid payload or Mattermost not configured.
		"""
		if self.App.SendMattermostOrchestrator is None:
			L.info(
				"Mattermost send request rejected because Mattermost is not configured. Add [mattermost] url and token or expect HTTP 400 responses.",
			)
			return aiohttp.web.json_response(
				{
					"result": "FAILED",
					"error": "Mattermost service is not configured."
				},
				status=400
			)

		tenant = json_data.get("tenant", None)
		current_tenant = asab.contextvars.Tenant.get(None)
		token = None

		if tenant is not None and current_tenant is None:
			token = asab.contextvars.Tenant.set(tenant)

		try:
			await self.App.SendMattermostOrchestrator.send_to_mattermost(json_data)
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
			L.exception(
				"Unexpected error while processing Mattermost send request; HTTP 400 returned to the client.",
				struct_data={"endpoint": "send_mattermost", "tenant": tenant, "template": json_data.get("body", {}).get("template")},
			)
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
	@asab.web.rest.json_schema_handler({"type": "object"})
	async def render(self, request, *, json_data):
		"""
		Render a template with the JSON request body and return HTML or PDF.

		Query parameters select the output format and template location. The JSON
		body supplies template parameters (Jinja variables).

		Example:

		```http
		PUT /render?format=pdf&template=/Templates/General/test.md
		Content-Type: application/json

		{
			"order_id": 123,
			"order_creation_date": "2020-01-01 14:14:52",
			"company_name": "Test Company",
			"city": "Mumbai",
			"state": "MH"
		}
		```

		Returns `text/html` when `format=html` (default) or `application/pdf`
		when `format=pdf`.
		---
		tags: ['Rendering']
		parameters: [{"name": "format", "in": "query", "description": "Output format.", "schema": {"type": "string", "enum": ["html", "pdf"], "default": "html"}}, {"name": "template", "in": "query", "required": true, "description": "Library path to the template (for example `/Templates/General/test.md`).", "schema": {"type": "string"}}]
		responses:
			'200':
				description: Rendered document.
				content:
					text/html:
						schema:
							type: string
					application/pdf:
						schema:
							type: string
							format: binary
			'400':
				description: Invalid format, invalid payload, or rendering error.
				content:
					application/json:
						schema:
							type: object
							properties:
								result:
									type: string
									example: ERROR
			'403':
				description: Template is disabled.
			'404':
				description: Template not found.
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
			L.exception(
				"Unexpected error while rendering a template; HTTP 400 returned to the client.",
				struct_data={"endpoint": "render", "tenant": tenant, "template": template, "format": fmt},
			)
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
		"""
		Send an SMS message rendered from a template under `/Templates/SMS/`.

		The destination phone number is provided in the `phone` field. Long
		messages are split automatically into multiple SMS segments.

		Example body:

		```json
		{
			"phone": "123456789",
			"body": {
				"template": "/Templates/SMS/alert.md",
				"params": {
					"message": "I am testing a template",
					"event": "Iris-Event"
				}
			}
		}
		```

		On success returns `{"result": "OK"}`.
		---
		tags: ['SMS']
		responses:
			'200':
				description: SMS accepted for delivery.
				content:
					application/json:
						schema:
							type: object
							properties:
								result:
									type: string
									example: OK
			'400':
				description: Invalid payload, invalid phone number, or SMS not configured.
		"""
		if self.App.SendSMSOrchestrator is None:
			L.info(
				"SMS send request rejected because SMS is not configured. Add [sms] configuration or expect HTTP 400 responses.",
			)
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
			L.exception(
				"Unexpected error while processing SMS send request; HTTP 400 returned to the client.",
				struct_data={"endpoint": "send_sms", "tenant": tenant, "template": json_data.get("body", {}).get("template")},
			)
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
	@asab.web.rest.json_schema_handler(push_schema)
	async def send_push(self, request, *, json_data):
		"""
		Send a push notification via ntfy.sh (or a self-hosted ntfy server).

		Templates must live under `/Templates/Push/`. When `topic` is omitted,
		the configured `[push] default_topic` is used.

		Example body:

		```json
		{
			"topic": "alerts",
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

		On success returns `{"result": "OK"}`.
		---
		tags: ['Push Notification (ntfy.sh)']
		responses:
			'200':
				description: Push notification accepted for delivery.
				content:
					application/json:
						schema:
							type: object
							properties:
								result:
									type: string
									example: OK
			'400':
				description: Invalid payload or push service not configured.
		"""
		if self.App.SendPushOrchestrator is None:
			L.info(
				"Push send request rejected because push (ntfy) is not configured. Add [push] url or expect HTTP 400 responses.",
			)
			return aiohttp.web.json_response(
				{
					"result": "FAILED",
					"error": "Push service is not configured."
				},
				status=400
			)

		tenant = json_data.get("tenant", None)
		current_tenant = asab.contextvars.Tenant.get(None)
		token = None

		if tenant is not None and current_tenant is None:
			token = asab.contextvars.Tenant.set(tenant)

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
			L.exception(
				"Unexpected error while processing push send request; HTTP 400 returned to the client.",
				struct_data={"endpoint": "send_push", "tenant": json_data.get("tenant"), "topic": json_data.get("topic"), "template": json_data.get("body", {}).get("template")},
			)
			response = {
				"result": "FAILED",
				"error": {
					"message": str(e),
					"error_code": "GENERAL_ERROR"
				}
			}
			return aiohttp.web.json_response(response, status=400)
		finally:
			if token is not None:
				asab.contextvars.Tenant.reset(token)

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
		Complete the Microsoft 365 delegated OAuth authorization flow.

		This endpoint serves two roles:

		1. **Initiation** (no `code` query parameter): redirects the browser to the Microsoft login page.
		2. **Callback** (`?code=...`): exchanges the authorization code for access and refresh tokens, then returns a confirmation page.

		Required only when `[m365_email] mode=delegated` and SMTP is not
		configured. The `redirect_uri` in Azure must match the public URL of
		this endpoint.

		Example initiation:

		```http
		GET /authorize_ms365
		```

		Example callback:

		```http
		GET /authorize_ms365?code=...&state=...
		```
		---
		tags: ['Microsoft 365']
		parameters: [{"name": "code", "in": "query", "required": false, "description": "Authorization code returned by Microsoft on callback.", "schema": {"type": "string"}}, {"name": "state", "in": "query", "required": false, "description": "OAuth state parameter returned by Microsoft.", "schema": {"type": "string"}}]
		responses:
			'200':
				description: Authorization completed successfully.
				content:
					text/plain:
						schema:
							type: string
			'302':
				description: Redirect to Microsoft login (initiation request).
			'400':
				description: Configuration or token exchange error.
				content:
					application/json:
						schema:
							type: object
							properties:
								result:
									type: string
									example: ERROR
			'500':
				description: M365EmailOutputService is not configured or internal error.
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
		except Exception:
			L.exception(
				"Unexpected error during Microsoft 365 OAuth token exchange on /authorize_ms365; HTTP 500 returned to the client.",
			)
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
