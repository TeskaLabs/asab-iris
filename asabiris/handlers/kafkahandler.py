import asyncio
import configparser
import json
import logging
import datetime

from aiokafka import AIOKafkaConsumer
import aiokafka.errors
import fastjsonschema

import asab

from asabiris.schemas.emailschema import email_schema
from asabiris.schemas.slackschema import slack_schema
from asabiris.schemas.teamsschema import teams_schema
from asabiris.schemas.smsschema import sms_schema

from ..errors import ASABIrisError, ErrorCode

L = logging.getLogger(__name__)


def check_config(config, section, parameter):
	try:
		value = config.get(section, parameter)
		return value
	except (configparser.NoOptionError, configparser.NoSectionError) as e:
		L.error("Configuration parameter '{}' is missing in section '{}': {}".format(parameter, section, e))
		return None


class KafkaHandler(asab.Service):
	ValidationSchemaMail = fastjsonschema.compile(email_schema)
	ValidationSchemaSlack = fastjsonschema.compile(slack_schema)
	ValidationSchemaMSTeams = fastjsonschema.compile(teams_schema)
	ValidationSchemaSMS = fastjsonschema.compile(sms_schema)

	def __init__(self, app, service_name="KafkaHandler"):
		super().__init__(app, service_name)
		self.Task = None
		self.JinjaService = app.get_service("JinjaService")
		self.Consumer = None  # Ensure Consumer is always initialized

		try:
			topic = check_config(asab.Config, "kafka", "topic")
			group_id = check_config(asab.Config, "kafka", "group_id")
			bootstrap_servers = check_config(asab.Config, "kafka", "bootstrap_servers")

			if not topic or not group_id or not bootstrap_servers:
				L.warning("Kafka configuration is missing. Skipping Kafka initialization.")
				return

			bootstrap_servers = bootstrap_servers.split(",")

			self.Consumer = AIOKafkaConsumer(
				topic,
				group_id=group_id,
				bootstrap_servers=bootstrap_servers,
				loop=self.App.Loop,
				retry_backoff_ms=10000,
				auto_offset_reset="earliest",
			)

		except Exception as e:
			L.error("KafkaHandler initialization failed: {}".format(e), exc_info=True)
			self.Consumer = None

	async def initialize(self, app):
		if self.Consumer is None:
			L.warning("Kafka consumer is not initialized. Skipping Kafka initialization.")
			return

		max_retries = 5
		initial_delay = 5  # Initial delay in seconds
		max_delay = 300  # Maximum delay in seconds (5 minutes)
		delay = initial_delay

		for attempt in range(max_retries):
			try:
				await self.Consumer.start()
				break
			except aiokafka.errors.KafkaConnectionError as e:
				L.warning("No connection to Kafka established. Attempt {} of {}. Retrying in {} seconds... {}".format(
					attempt + 1, max_retries, delay, e))
				await asyncio.sleep(delay)
				delay = min(delay * 2, max_delay)
		else:
			L.error("Failed to connect to Kafka after {} attempts.".format(max_retries))
			return

		self.Task = asyncio.ensure_future(self.consume(), loop=self.App.Loop)

	async def finalize(self, app):
		if self.Consumer is not None:
			await self.Consumer.stop()
		if self.Task and self.Task.exception():
			L.warning("Exception occurred during alert notifications: {}".format(self.Task.exception()))

	async def consume(self):
		if self.Consumer is None:
			return
		async for msg in self.Consumer:
			try:
				msg = msg.value.decode("utf-8")
				msg = json.loads(msg)
			except (UnicodeDecodeError, json.JSONDecodeError) as e:
				L.warning("Failed to decode or parse message: {}".format(e))
				continue
			try:
				await self.dispatch(msg)
			except Exception as e:
				L.exception("General error when dispatching message: {}".format(e))

	async def dispatch(self, msg):
		try:
			msg_type = msg.pop("type", "<missing>")
		except (AttributeError, Exception) as e:
			L.warning("Error extracting message type: {}".format(str(e)))
			return

		if msg_type == "email":
			await self.handle_email(msg)
		elif msg_type == "slack":
			if self.App.SendSlackOrchestrator is None:
				L.warning("Slack service is not configured. Discarding notification.")
				return
			await self.handle_slack(msg)
		elif msg_type == "msteams":
			if self.App.SendMSTeamsOrchestrator is None:
				L.warning("MS Teams service is not configured. Discarding notification.")
				return
			await self.handle_msteams(msg)
		elif msg_type == "sms":
			if self.App.SendSMSOrchestrator is None:
				L.warning("SMS service is not configured. Discarding notification.")
				return
			await self.handle_sms(msg)
		else:
			L.warning(
				"Notification sending failed: Unsupported message type '{}'. Supported types are 'email', 'slack', 'msteams', and 'sms'.".format(msg_type)
			)

	async def handle_email(self, msg):
		try:
			KafkaHandler.ValidationSchemaMail(msg)
		except fastjsonschema.exceptions.JsonSchemaException as e:
			L.warning("Invalid email notification format: {}".format(e))
			return

		try:
			await self.send_email(msg)
		except ASABIrisError as e:
			server_errors = [
				ErrorCode.SMTP_CONNECTION_ERROR,
				ErrorCode.SMTP_AUTHENTICATION_ERROR,
				ErrorCode.SMTP_RESPONSE_ERROR,
				ErrorCode.SMTP_SERVER_DISCONNECTED,
				ErrorCode.SMTP_GENERIC_ERROR,
				ErrorCode.GENERAL_ERROR,
			]
			if e.ErrorCode in server_errors:
				L.warning("Email dispatch failed: {}".format(e.TechMessage))
			else:
				await self.handle_exception(e.TechMessage, 'email', msg)
		except Exception as e:
			await self.handle_exception(e, 'email', msg)

	async def handle_slack(self, msg):
		try:
			KafkaHandler.ValidationSchemaSlack(msg)
		except fastjsonschema.exceptions.JsonSchemaException as e:
			L.warning("Invalid Slack notification format: {}".format(e))
			return

		try:
			await self.App.SendSlackOrchestrator.send_to_slack(msg)
		except ASABIrisError as e:
			if e.ErrorCode == ErrorCode.SLACK_API_ERROR:
				L.warning("Slack notification failed: {}".format(e.TechMessage))
			else:
				await self.handle_exception(e.TechMessage, 'slack')
		except Exception as e:
			await self.handle_exception(e, 'slack')

	async def handle_msteams(self, msg):
		try:
			KafkaHandler.ValidationSchemaMSTeams(msg)
		except fastjsonschema.exceptions.JsonSchemaException as e:
			L.warning("Invalid MSTeams notification format: {}".format(e))
			return

		try:
			await self.App.SendMSTeamsOrchestrator.send_to_msteams(msg)
		except ASABIrisError as e:
			if e.ErrorCode == ErrorCode.SERVER_ERROR:
				L.warning("MSTeams notification failed: {}".format(e.TechMessage))
			else:
				await self.handle_exception(e.TechMessage, 'msteams')
		except Exception as e:
			await self.handle_exception(e, 'msteams')

	async def handle_sms(self, msg):
		try:
			KafkaHandler.ValidationSchemaSMS(msg)
		except fastjsonschema.exceptions.JsonSchemaException as e:
			L.warning("Invalid SMS notification format: {}".format(e))
			return

		try:
			await self.App.SendSMSOrchestrator.send_sms(msg)
		except ASABIrisError as e:
			if e.ErrorCode == ErrorCode.SERVER_ERROR:
				L.warning("SMS notification failed: {}".format(e.TechMessage))
			else:
				await self.handle_exception(e.TechMessage, 'sms', msg)
		except Exception as e:
			await self.handle_exception(e, 'sms', msg)


	async def send_email(self, json_data):
		await self.App.SendEmailOrchestrator.send_email(
			email_from=json_data.get('from', None),
			email_to=json_data['to'],
			email_subject=json_data.get('subject', None),
			body_template=json_data['body']['template'],
			body_template_wrapper=json_data["body"].get("wrapper", None),
			body_params=json_data['body']['params'],
			email_cc=json_data.get('cc', []),
			email_bcc=json_data.get('bcc', []),
			attachments=json_data.get('attachments', [])
		)
		L.info("Email sent successfully")

	async def handle_push(self, msg):
		try:
			KafkaHandler.ValidationSchemaPush(msg)
		except fastjsonschema.exceptions.JsonSchemaException as e:
			L.warning("Invalid Push notification format: {}".format(e))
			return

		try:
			# Orchestrator is responsible for rendering the template & calling PushOutputService
			await self.App.SendPushOrchestrator.send_push(msg)
		except ASABIrisError as e:
			# Network/remote errors are SERVER_ERROR; others bubble to error handler
			if e.ErrorCode == ErrorCode.SERVER_ERROR:
				L.warning("Push notification failed: {}".format(e.TechMessage))
			else:
				await self.handle_exception(e.TechMessage, 'push', msg)
		except Exception as e:
			await self.handle_exception(e, 'push', msg)

	async def handle_exception(self, exception, service_type, msg=None):
		"""
		No hardcoded bodies. Use orchestrators + Jinja templates from [error_templates].
		- service_type: 'email' | 'slack' | 'msteams' | 'sms'
		- msg: optional dict carrying routing (to/cc/bcc/from/tenant/attachments)
		"""
		try:
			L.warning("Encountered an issue while sending '{}'. Details: {}.".format(service_type, exception))

			# 1) Build params (exception + UTC time only)
			params = _build_exception_params(exception, service_type)

			# 2) Load templates once and cache on the instance
			if not hasattr(self, "_ErrorTemplates") or not isinstance(self._ErrorTemplates, dict):
				self._ErrorTemplates = _load_error_templates_from_config()

			tpl_email = self._ErrorTemplates.get("email")
			tpl_slack = self._ErrorTemplates.get("slack")
			tpl_teams = self._ErrorTemplates.get("msteams")
			tpl_sms = self._ErrorTemplates.get("sms")

			# 3) Orchestrator dispatch (no raw provider calls)
			msg = msg or {}

			if service_type == "email":
				if tpl_email is None:
					L.info("No email template configured in [error_templates]. Skipping email error notification.")
					return
				if not tpl_email.startswith("/Templates/Email/"):
					L.warning("Email template must start with /Templates/Email/: {}".format(tpl_email))
					return

				email_to = _ensure_list(msg.get("to"))
				if not email_to:
					L.info("Skip email notification: no recipients provided in 'msg.to'.")
					return

				try:
					L.log(asab.LOG_NOTICE, "Sending error notification via Email Orchestrator.")
					await self.App.SendEmailOrchestrator.send_email(
						email_to=email_to,
						body_template=tpl_email,
						body_params=params,
						email_from=msg.get("from"),
						email_cc=_ensure_list(msg.get("cc")),
						email_bcc=_ensure_list(msg.get("bcc")),
						email_subject=None,
						attachments=_ensure_list(msg.get("attachments"))
					)
				except Exception:
					L.exception("Error notification to Email unsuccessful.")
				return

			elif service_type == "slack":
				if tpl_slack is None:
					L.info("No Slack template configured in [error_templates]. Skipping Slack error notification.")
					return
				if not tpl_slack.startswith("/Templates/Slack/"):
					L.warning("Slack template must start with /Templates/Slack/: {}".format(tpl_slack))
					return

				try:
					L.log(asab.LOG_NOTICE, "Sending error notification via Slack Orchestrator.")
					await self.App.SendSlackOrchestrator.send_to_slack({
						"body": {
							"template": tpl_slack,
							"params": params
						},
						"attachments": msg.get("attachments"),
						"tenant": msg.get("tenant")
					})
				except ASABIrisError as e:
					L.info("Error notification to Slack unsuccessful: Explanation: {}".format(e.TechMessage))
				except Exception:
					L.exception("Error notification to Slack unsuccessful.")
				return

			elif service_type == "msteams":
				if tpl_teams is None:
					L.info("No MS Teams template configured in [error_templates]. Skipping Teams error notification.")
					return
				# Your Teams orchestrator enforces '/Templates/MSTeams/' — we do not normalize here.
				if not tpl_teams.startswith("/Templates/MSTeams/"):
					L.warning("MS Teams template must start with /Templates/MSTeams/: {}".format(tpl_teams))
					return

				try:
					L.log(asab.LOG_NOTICE, "Sending error notification via MS Teams Orchestrator.")
					await self.App.SendMSTeamsOrchestrator.send_to_msteams({
						"body": {
							"template": tpl_teams,
							"params": params
						},
						"tenant": msg.get("tenant")
					})
				except ASABIrisError as e:
					L.info("Error notification to MSTeams unsuccessful: Explanation: {}".format(e.TechMessage))
				except Exception:
					L.exception("Error notification to MSTeams unsuccessful.")
				return

			elif service_type == "sms":
				if tpl_sms is None:
					L.info("No SMS template configured in [error_templates]. Skipping SMS error notification.")
					return
				if not tpl_sms.startswith("/Templates/SMS/"):
					L.warning("SMS template must start with /Templates/SMS/: {}".format(tpl_sms))
					return

				to_numbers = _ensure_list(msg.get("to"))
				if not to_numbers:
					L.info("Skip SMS notification: no phone recipient in 'msg.to'.")
					return

				try:
					L.log(asab.LOG_NOTICE, "Sending error notification via SMS Orchestrator.")
					await self.App.SendSMSOrchestrator.send_sms({
						"to": to_numbers[0],
						"body": {
							"template": tpl_sms,
							"params": params
						},
						"tenant": msg.get("tenant")
					})
				except Exception:
					L.exception("Error notification to SMS unsuccessful.")
				return

			else:
				L.warning("Unknown service_type '{}'; no error notification sent.".format(service_type))

		except Exception:
			L.exception("An unexpected error occurred while sending error message for {}.".format(service_type))


def _now_utc_iso():
	return datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _split_csv(value):
	if not value:
		return []
	return [x.strip() for x in value.split(",") if x.strip()]


def _ensure_list(value):
	if value is None:
		return []
	if isinstance(value, (list, tuple)):
		return list(value)
	return _split_csv(value)


def _build_exception_params(exception, service_type):
	return {
		"ts_utc": _now_utc_iso(),
		"service_type": service_type,
		"exception_type": type(exception).__name__,
		"exception_message": "{}".format(exception),
	}


def _load_error_templates_from_config():
	"""
	Read [error_templates] once. Returns dict or {} if missing.
	Expected keys (any subset is fine): email, slack, msteams, sms
	"""
	cfg = asab.Config
	sec = "error_templates"
	if not cfg.has_section(sec):
		L.warning("Missing [{}] section.".format(sec))
		return {}
	tpls = {}
	for key in ("email", "slack", "msteams", "sms"):
		if cfg.has_option(sec, key):
			tpls[key] = cfg.get(sec, key).strip()
	return tpls
