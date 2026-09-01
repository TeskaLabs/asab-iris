import asyncio
import configparser
import json
import logging
import datetime

from aiokafka import AIOKafkaConsumer
import aiokafka.errors
import fastjsonschema

import asab
import asab.contextvars

from asabiris.schemas.emailschema import email_schema
from asabiris.schemas.mattermostschema import mattermost_schema
from asabiris.schemas.slackschema import slack_schema
from asabiris.schemas.teamsschema import teams_schema
from asabiris.schemas.smsschema import sms_schema
from asabiris.schemas.pushschema import push_schema

from ..errors import ASABIrisError, ErrorCode

L = logging.getLogger(__name__)


def check_config(config, section, parameter):
	try:
		value = config.get(section, parameter)
		return value
	except (configparser.NoOptionError, configparser.NoSectionError) as e:
		L.error(
			"Required Kafka configuration option is missing; Kafka consumer will not start. Add the missing option to [kafka] or remove the [kafka] section to disable Kafka.",
			struct_data={"config_section": section, "config_option": parameter, "error_type": e.__class__.__name__},
		)
		return None


class KafkaHandler(asab.Service):
	ValidationSchemaMail = fastjsonschema.compile(email_schema)
	ValidationSchemaMattermost = fastjsonschema.compile(mattermost_schema)
	ValidationSchemaSlack = fastjsonschema.compile(slack_schema)
	ValidationSchemaMSTeams = fastjsonschema.compile(teams_schema)
	ValidationSchemaSMS = fastjsonschema.compile(sms_schema)
	ValidationSchemaPush = fastjsonschema.compile(push_schema)

	def __init__(self, app, service_name="KafkaHandler"):
		super().__init__(app, service_name)
		self.Task = None
		self.Consumer = None  # Ensure Consumer is always initialized
		self.KafkaTopic = None
		self.KafkaGroupId = None
		self.KafkaBootstrapServers = None

		try:
			topic = check_config(asab.Config, "kafka", "topic")
			group_id = check_config(asab.Config, "kafka", "group_id")
			bootstrap_servers = check_config(asab.Config, "kafka", "bootstrap_servers")

			if not topic or not group_id or not bootstrap_servers:
				L.warning(
					"Kafka consumer is not starting because [kafka] is incomplete. Configure topic, group_id, and bootstrap_servers, or remove [kafka] to disable alert consumption.",
					struct_data={"topic": topic, "group_id": group_id, "bootstrap_servers": bootstrap_servers},
				)
				return

			self.KafkaTopic = topic
			self.KafkaGroupId = group_id
			self.KafkaBootstrapServers = bootstrap_servers.split(",")

			self.Consumer = AIOKafkaConsumer(
				topic,
				group_id=group_id,
				bootstrap_servers=self.KafkaBootstrapServers,
				loop=self.App.Loop,
				retry_backoff_ms=10000,
				auto_offset_reset="earliest",
			)

		except Exception as e:
			L.error(
				"Kafka consumer failed to initialize; alert notifications from Kafka will not be processed. Check [kafka] settings and broker connectivity.",
				struct_data={"error_type": e.__class__.__name__},
				exc_info=True,
			)
			self.Consumer = None

	async def initialize(self, app):
		if self.Consumer is None:
			L.warning(
				"Kafka consumer was not created during startup; skipping Kafka connection. Review earlier ERROR/WARNING logs for the root cause.",
			)
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
				L.warning(
					"Kafka broker connection failed; retrying consumer startup.",
					struct_data={
						"attempt": attempt + 1,
						"max_attempts": max_retries,
						"retry_delay_seconds": delay,
						"bootstrap_servers": self.KafkaBootstrapServers,
						"topic": self.KafkaTopic,
						"group_id": self.KafkaGroupId,
						"error_type": e.__class__.__name__,
					},
				)
				await asyncio.sleep(delay)
				delay = min(delay * 2, max_delay)
		else:
			L.error(
				"Kafka consumer could not connect after all retry attempts; alert notifications from Kafka will not be processed. Verify bootstrap_servers, network access, and broker health.",
				struct_data={"max_attempts": max_retries, "bootstrap_servers": self.KafkaBootstrapServers, "topic": self.KafkaTopic, "group_id": self.KafkaGroupId},
			)
			return

		self.Task = asyncio.ensure_future(self.consume(), loop=self.App.Loop)

	async def finalize(self, app):
		if self.Consumer is not None:
			await self.Consumer.stop()
		if self.Task and self.Task.done():
			exception = self.Task.exception()
			if exception is not None:
				L.warning(
					"Kafka alert notification consumer task ended with an unhandled exception; new Kafka messages may not be processed until the service is restarted.",
					struct_data={"error_type": type(exception).__name__},
				)

	async def consume(self):
		if self.Consumer is None:
			return
		async for msg in self.Consumer:
			try:
				msg = msg.value.decode("utf-8")
				msg = json.loads(msg)
			except (UnicodeDecodeError, json.JSONDecodeError) as e:
				L.warning(
					"Kafka alert message is not valid UTF-8 JSON; message was skipped. Verify the producer publishes JSON to the configured topic.",
					struct_data={"topic": self.KafkaTopic, "error_type": e.__class__.__name__},
				)
				continue
			try:
				await self.dispatch(msg)
			except Exception:
				L.exception(
					"Unexpected error while dispatching a Kafka alert notification; message processing stopped for this payload.",
					struct_data={"topic": self.KafkaTopic, "message_type": msg.get("type") if isinstance(msg, dict) else None},
				)

	async def dispatch(self, msg):
		tenant = None
		token = None

		# Set tenant context from Kafka message body (if present)
		try:
			if isinstance(msg, dict):
				tenant = msg.get("tenant", None)
			current_tenant = asab.contextvars.Tenant.get(None)
			if tenant is not None and current_tenant is None:
				token = asab.contextvars.Tenant.set(tenant)
		except Exception as e:
			L.warning(
				"Could not set tenant context from Kafka message; notification will use global configuration.",
				struct_data={"tenant": tenant, "error_type": e.__class__.__name__},
			)
		try:
			try:
				msg_type = msg.pop("type", "<missing>")
			except AttributeError as e:
				L.warning(
					"Kafka alert message is not a JSON object; message was discarded.",
					struct_data={"error_type": e.__class__.__name__},
				)
				return

			if msg_type == "email":
				await self.handle_email(msg)
			elif msg_type == "mattermost":
				if self.App.SendMattermostOrchestrator is None:
					L.warning(
						"Kafka Mattermost notification discarded because Mattermost is not configured. Add [mattermost] configuration or stop publishing mattermost messages.",
						struct_data={"message_type": msg_type, "tenant": tenant},
					)
					return
				await self.handle_mattermost(msg)
			elif msg_type == "slack":
				if self.App.SendSlackOrchestrator is None:
					L.warning(
						"Kafka Slack notification discarded because Slack is not configured. Add [slack] configuration or stop publishing slack messages.",
						struct_data={"message_type": msg_type, "tenant": tenant},
					)
					return
				await self.handle_slack(msg)
			elif msg_type == "msteams":
				if self.App.SendMSTeamsOrchestrator is None:
					L.warning(
						"Kafka Microsoft Teams notification discarded because MS Teams is not configured. Add [msteams] configuration or stop publishing msteams messages.",
						struct_data={"message_type": msg_type, "tenant": tenant},
					)
					return
				await self.handle_msteams(msg)
			elif msg_type == "sms":
				if self.App.SendSMSOrchestrator is None:
					L.warning(
						"Kafka SMS notification discarded because SMS is not configured. Add [sms] configuration or stop publishing sms messages.",
						struct_data={"message_type": msg_type, "tenant": tenant},
					)
					return
				await self.handle_sms(msg)
			elif msg_type == "push":
				if not hasattr(self.App, "SendPushOrchestrator") or self.App.SendPushOrchestrator is None:
					L.warning(
						"Kafka push notification discarded because push (ntfy) is not configured. Add [push] url configuration or stop publishing push messages.",
						struct_data={"message_type": msg_type, "tenant": tenant},
					)
					return
				await self.handle_push(msg)
			else:
				L.warning(
					"Kafka alert message has unsupported type and was discarded. Supported types: email, mattermost, slack, msteams, sms, push.",
					struct_data={"message_type": msg_type, "tenant": tenant},
				)
		finally:
			if token is not None:
				try:
					asab.contextvars.Tenant.reset(token)
				except Exception:
					L.exception(
						"Failed to reset tenant context after processing a Kafka alert notification; subsequent messages may inherit the wrong tenant.",
						struct_data={"tenant": tenant},
					)

	async def handle_email(self, msg):
		try:
			KafkaHandler.ValidationSchemaMail(msg)
		except fastjsonschema.exceptions.JsonSchemaException as e:
			L.warning(
				"Kafka email notification failed schema validation; message was discarded. Fix the producer payload to match the email notification schema.",
				struct_data={"validation_error": str(e)},
			)
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
				L.warning(
					"Kafka email notification could not be delivered due to an upstream mail server error.",
					struct_data={"error_code": e.ErrorCode.name if hasattr(e.ErrorCode, "name") else str(e.ErrorCode)},
				)
			else:
				await self.handle_exception(e.TechMessage, 'email', msg)
		except Exception as e:
			await self.handle_exception(e, 'email', msg)

	async def handle_slack(self, msg):
		try:
			KafkaHandler.ValidationSchemaSlack(msg)
		except fastjsonschema.exceptions.JsonSchemaException as e:
			L.warning(
				"Kafka Slack notification failed schema validation; message was discarded. Fix the producer payload to match the Slack notification schema.",
				struct_data={"validation_error": str(e)},
			)
			return

		try:
			await self.App.SendSlackOrchestrator.send_to_slack(msg)

		except ASABIrisError as e:
			# 1. Business error (DO NOT trigger error notification)
			if e.ErrorCode == ErrorCode.SLACK_CHANNEL_NOT_FOUND:
				L.warning(
					"Kafka Slack notification rejected because the target channel was not found. Verify the channel name or channel_id in the message and Slack workspace configuration.",
					struct_data={"error_code": e.ErrorCode.name},
				)
				return

			# 2. Slack API / network error (DO NOT trigger error notification)
			if e.ErrorCode == ErrorCode.SLACK_API_ERROR:
				L.warning(
					"Kafka Slack notification failed due to a Slack API or network error.",
					struct_data={"error_code": e.ErrorCode.name},
				)
				return

			await self.handle_exception(e.TechMessage, 'slack', msg)
		except Exception as e:
			await self.handle_exception(e, 'slack', msg)

	async def handle_mattermost(self, msg):
		try:
			KafkaHandler.ValidationSchemaMattermost(msg)
		except fastjsonschema.exceptions.JsonSchemaException as e:
			L.warning(
				"Kafka Mattermost notification failed schema validation; message was discarded. Fix the producer payload to match the Mattermost notification schema.",
				struct_data={"validation_error": str(e)},
			)
			return

		try:
			await self.App.SendMattermostOrchestrator.send_to_mattermost(msg)
		except ASABIrisError as e:
			if e.ErrorCode in (
				ErrorCode.INVALID_REQUEST,
				ErrorCode.AUTHENTICATION_FAILED,
				ErrorCode.SERVER_ERROR,
			):
				L.warning(
					"Kafka Mattermost notification failed due to a Mattermost API or configuration error.",
					struct_data={"error_code": e.ErrorCode.name},
				)
				return

			await self.handle_exception(e.TechMessage, 'mattermost', msg)
		except Exception as e:
			await self.handle_exception(e, 'mattermost', msg)

	async def handle_msteams(self, msg):
		try:
			KafkaHandler.ValidationSchemaMSTeams(msg)
		except fastjsonschema.exceptions.JsonSchemaException as e:
			L.warning(
				"Kafka Microsoft Teams notification failed schema validation; message was discarded. Fix the producer payload to match the MS Teams notification schema.",
				struct_data={"validation_error": str(e)},
			)
			return

		try:
			await self.App.SendMSTeamsOrchestrator.send_to_msteams(msg)
		except ASABIrisError as e:
			if e.ErrorCode == ErrorCode.SERVER_ERROR:
				L.warning(
					"Kafka Microsoft Teams notification failed due to a Teams webhook or network error.",
					struct_data={"error_code": e.ErrorCode.name},
				)
				return
			else:
				await self.handle_exception(e.TechMessage, 'msteams', msg)
		except Exception as e:
			await self.handle_exception(e, 'msteams', msg)

	async def handle_sms(self, msg):
		try:
			KafkaHandler.ValidationSchemaSMS(msg)
		except fastjsonschema.exceptions.JsonSchemaException as e:
			L.warning(
				"Kafka SMS notification failed schema validation; message was discarded. Fix the producer payload to match the SMS notification schema.",
				struct_data={"validation_error": str(e)},
			)
			return

		try:
			await self.App.SendSMSOrchestrator.send_sms(msg)
		except ASABIrisError as e:
			if e.ErrorCode == ErrorCode.SERVER_ERROR:
				L.warning(
					"Kafka SMS notification failed due to an SMS provider or network error.",
					struct_data={"error_code": e.ErrorCode.name},
				)
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
		L.info(
			"Kafka email notification delivered successfully.",
			struct_data={"recipients": json_data.get("to")},
		)

	async def handle_push(self, msg):
		try:
			KafkaHandler.ValidationSchemaPush(msg)
		except fastjsonschema.exceptions.JsonSchemaException as e:
			L.warning(
				"Kafka push notification failed schema validation; message was discarded. Fix the producer payload to match the push notification schema.",
				struct_data={"validation_error": str(e)},
			)
			return

		try:
			# Orchestrator is responsible for rendering the template & calling PushOutputService
			await self.App.SendPushOrchestrator.send_push(msg)
		except ASABIrisError as e:
			# Network/remote errors are SERVER_ERROR; others bubble to error handler
			if e.ErrorCode == ErrorCode.SERVER_ERROR:
				L.warning(
					"Kafka push notification failed due to an ntfy server or network error.",
					struct_data={"error_code": e.ErrorCode.name, "topic": msg.get("topic")},
				)
			else:
				await self.handle_exception(e.TechMessage, 'push', msg)
		except Exception as e:
			await self.handle_exception(e, 'push', msg)

	async def handle_exception(self, exception, service_type, msg=None):
		"""
		No hardcoded bodies. Use orchestrators + Jinja templates from [error_templates].
		- service_type: 'email' | 'mattermost' | 'slack' | 'msteams' | 'sms' | 'push'
		- msg: optional dict carrying routing (to/cc/bcc/from/tenant/attachments/topic)
		"""

		try:
			L.warning(
				"Notification delivery failed; attempting configured error-notification fallback.",
				struct_data={"channel": service_type, "exception_type": type(exception).__name__},
			)

			# 1) Build params (exception + UTC time only)
			params = _build_exception_params(exception, service_type)

			# 2) Load templates once and cache on the instance
			if not hasattr(self, "_ErrorTemplates") or not isinstance(self._ErrorTemplates, dict):
				self._ErrorTemplates = _load_error_templates_from_config()

			tpl_email = self._ErrorTemplates.get("email")
			tpl_mattermost = self._ErrorTemplates.get("mattermost")
			tpl_slack = self._ErrorTemplates.get("slack")
			tpl_teams = self._ErrorTemplates.get("msteams")
			tpl_sms = self._ErrorTemplates.get("sms")

			# 3) Orchestrator dispatch (no raw provider calls)
			msg = msg or {}

			if service_type == "email":
				if tpl_email is None:
					L.info(
						"Error notification via email skipped because no template is configured in [error_templates]. Add an email template path or configure error_templates.email.",
					)
					return
				if not tpl_email.startswith("/Templates/Email/"):
					L.warning(
						"Error notification via email skipped because the configured template path is invalid. Templates must start with /Templates/Email/.",
						struct_data={"template": tpl_email},
					)
					return

				email_to = _ensure_list(msg.get("to"))
				if not email_to:
					L.info(
						"Error notification via email skipped because the original Kafka message has no recipients in 'to'.",
					)
					return

				try:
					L.log(asab.LOG_NOTICE, "Sending configured error notification via email.", struct_data={"channel": "email"})
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
					L.exception(
						"Configured error notification via email could not be delivered.",
						struct_data={"channel": "email", "recipients": email_to},
					)
				return

			elif service_type == "mattermost":
				if tpl_mattermost is None:
					L.info(
						"Error notification via Mattermost skipped because no template is configured in [error_templates].",
					)
					return
				if not tpl_mattermost.startswith("/Templates/Mattermost/"):
					L.warning(
						"Error notification via Mattermost skipped because the configured template path is invalid. Templates must start with /Templates/Mattermost/.",
						struct_data={"template": tpl_mattermost},
					)
					return

				try:
					L.log(asab.LOG_NOTICE, "Sending configured error notification via Mattermost.", struct_data={"channel": "mattermost"})
					await self.App.SendMattermostOrchestrator.send_to_mattermost({
						"body": {
							"template": tpl_mattermost,
							"params": params
						},
						"channel_id": msg.get("channel_id"),
						"username": msg.get("username"),
						"tenant": msg.get("tenant")
					})
				except ASABIrisError as e:
					L.warning(
						"Configured error notification via Mattermost was rejected by the Mattermost API.",
						struct_data={"channel": "mattermost", "error_code": e.ErrorCode.name if hasattr(e.ErrorCode, "name") else str(e.ErrorCode)},
					)
				except Exception:
					L.exception(
						"Configured error notification via Mattermost could not be delivered.",
						struct_data={"channel": "mattermost"},
					)
				return

			elif service_type == "slack":
				if tpl_slack is None:
					L.info(
						"Error notification via Slack skipped because no template is configured in [error_templates].",
					)
					return
				if not tpl_slack.startswith("/Templates/Slack/"):
					L.warning(
						"Error notification via Slack skipped because the configured template path is invalid. Templates must start with /Templates/Slack/.",
						struct_data={"template": tpl_slack},
					)
					return

				try:
					L.log(asab.LOG_NOTICE, "Sending configured error notification via Slack.", struct_data={"channel": "slack"})
					await self.App.SendSlackOrchestrator.send_to_slack({
						"body": {
							"template": tpl_slack,
							"params": params
						},
						"attachments": msg.get("attachments"),
						"tenant": msg.get("tenant")
					})
				except ASABIrisError as e:
					L.warning(
						"Configured error notification via Slack was rejected by the Slack API.",
						struct_data={"channel": "slack", "error_code": e.ErrorCode.name if hasattr(e.ErrorCode, "name") else str(e.ErrorCode)},
					)
				except Exception:
					L.exception(
						"Configured error notification via Slack could not be delivered.",
						struct_data={"channel": "slack"},
					)
				return

			elif service_type == "msteams":
				if tpl_teams is None:
					L.info(
						"Error notification via Microsoft Teams skipped because no template is configured in [error_templates].",
					)
					return
				# Your Teams orchestrator enforces '/Templates/MSTeams/' — we do not normalize here.
				if not tpl_teams.startswith("/Templates/MSTeams/"):
					L.warning(
						"Error notification via Microsoft Teams skipped because the configured template path is invalid. Templates must start with /Templates/MSTeams/.",
						struct_data={"template": tpl_teams},
					)
					return

				try:
					L.log(asab.LOG_NOTICE, "Sending configured error notification via Microsoft Teams.", struct_data={"channel": "msteams"})
					await self.App.SendMSTeamsOrchestrator.send_to_msteams({
						"body": {
							"template": tpl_teams,
							"params": params
						},
						"tenant": msg.get("tenant")
					})
				except ASABIrisError as e:
					L.warning(
						"Configured error notification via Microsoft Teams was rejected by the Teams webhook.",
						struct_data={"channel": "msteams", "error_code": e.ErrorCode.name if hasattr(e.ErrorCode, "name") else str(e.ErrorCode)},
					)
				except Exception:
					L.exception(
						"Configured error notification via Microsoft Teams could not be delivered.",
						struct_data={"channel": "msteams"},
					)
				return

			elif service_type == "sms":
				if tpl_sms is None:
					L.info(
						"Error notification via SMS skipped because no template is configured in [error_templates].",
					)
					return
				if not tpl_sms.startswith("/Templates/SMS/"):
					L.warning(
						"Error notification via SMS skipped because the configured template path is invalid. Templates must start with /Templates/SMS/.",
						struct_data={"template": tpl_sms},
					)
					return

				to_numbers = _ensure_list(msg.get("to"))
				if not to_numbers:
					L.info(
						"Error notification via SMS skipped because the original Kafka message has no phone recipient in 'to'.",
					)
					return

				try:
					L.log(asab.LOG_NOTICE, "Sending configured error notification via SMS.", struct_data={"channel": "sms", "phone": to_numbers[0]})
					await self.App.SendSMSOrchestrator.send_sms({
						"to": to_numbers[0],
						"body": {
							"template": tpl_sms,
							"params": params
						},
						"tenant": msg.get("tenant")
					})
				except Exception:
					L.exception(
						"Configured error notification via SMS could not be delivered.",
						struct_data={"channel": "sms", "phone": to_numbers[0]},
					)
				return

			elif service_type == "push":
				if not hasattr(self.App, "SendPushOrchestrator") or self.App.SendPushOrchestrator is None:
					L.info(
						"Error notification via push skipped because push (ntfy) is not configured.",
					)
					return

				tpl_push = self._ErrorTemplates.get("push")
				if tpl_push is None:
					L.info(
						"Error notification via push skipped because no template is configured in [error_templates].",
					)
					return
				if not tpl_push.startswith("/Templates/Push/"):
					L.warning(
						"Error notification via push skipped because the configured template path is invalid. Templates must start with /Templates/Push/.",
						struct_data={"template": tpl_push},
					)
					return

				try:
					L.log(asab.LOG_NOTICE, "Sending configured error notification via push (ntfy).", struct_data={"channel": "push", "topic": msg.get("topic")})
					await self.App.SendPushOrchestrator.send_push({
						"topic": msg.get("topic"),  # or use default_topic from config
						"body": {
							"template": tpl_push,
							"params": params
						},
						"tenant": msg.get("tenant")
					})
				except ASABIrisError as e:
					L.warning(
						"Configured error notification via push was rejected by the ntfy server.",
						struct_data={"channel": "push", "error_code": e.ErrorCode.name if hasattr(e.ErrorCode, "name") else str(e.ErrorCode), "topic": msg.get("topic")},
					)
				except Exception:
					L.exception(
						"Configured error notification via push could not be delivered.",
						struct_data={"channel": "push", "topic": msg.get("topic")},
					)
				return

			else:
				L.warning(
					"Error notification fallback skipped because the failed channel type is unknown.",
					struct_data={"channel": service_type},
				)

		except Exception:
			L.exception(
				"Unexpected failure while sending configured error notification fallback.",
				struct_data={"channel": service_type},
			)


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
	Expected keys (any subset is fine): email, mattermost, slack, msteams, sms, push
	"""
	cfg = asab.Config
	sec = "error_templates"
	if not cfg.has_section(sec):
		L.warning(
			"[error_templates] section is missing; notification failure fallbacks are disabled. Add error_templates.* paths to enable secondary alerts.",
			struct_data={"config_section": sec},
		)
		return {}
	tpls = {}
	for key in ("email", "mattermost", "slack", "msteams", "sms", "push"):
		if cfg.has_option(sec, key):
			value = cfg.get(sec, key).strip()
			if value:
				tpls[key] = value

	for key in ("msteams", "teams"):
		if cfg.has_option(sec, key):
			value = cfg.get(sec, key).strip()
			if value:
				tpls["msteams"] = value
				break

	return tpls
