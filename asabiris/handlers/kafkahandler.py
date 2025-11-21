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
			# 1. Business error (DO NOT trigger error notification)
			if e.ErrorCode == ErrorCode.SLACK_CHANNEL_NOT_FOUND:
				L.warning("Slack channel not found: {}".format(e.TechMessage))
				return

			# 2. Slack API / network error (DO NOT trigger error notification)
			if e.ErrorCode == ErrorCode.SLACK_API_ERROR:
				L.warning("Slack notification failed: {}".format(e.TechMessage))
				return

			await self.handle_exception(e.TechMessage, 'slack', msg)
		except Exception as e:
			await self.handle_exception(e, 'slack', msg)

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
				return
			else:
				await self.handle_exception(e.TechMessage, 'msteams', msg)
		except Exception as e:
			await self.handle_exception(e, 'msteams', msg)

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
				return
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

	async def handle_exception(self, exception, service_type, msg=None):
		try:
			L.warning("Encountered an issue while sending '{}'. Details: {}.".format(service_type, exception))

			error_message, error_subject = self.generate_error_message(str(exception), service_type)

			if error_message is None:
				return

			if service_type == 'email' and msg:
				try:
					L.log(asab.LOG_NOTICE, "Sending error notification to email.")
					await self.App.SendEmailOrchestrator.send_email_raw(
						email_from=msg.get('from', None),
						email_to=msg['to'],
						email_subject=error_subject or "Error Notification",
						body=error_message,
						content_type="HTML"
					)
				except Exception:
					L.exception("Error notification to email unsuccessful.")

			elif service_type == 'slack':
				try:
					L.log(asab.LOG_NOTICE, "Sending error notification to slack.")
					tenant = msg.get("tenant", None)
					await self.App.SlackOutputService.send_message(None, error_message, tenant)
				except ASABIrisError as e:
					L.info("Error notification to Slack unsuccessful: Explanation: {}".format(e.TechMessage))

			elif service_type == 'msteams':
				try:
					L.log(asab.LOG_NOTICE, "Sending error notification to MSTeams.")
					tenant = msg.get("tenant", None)
					await self.App.MSTeamsOutputService.send(error_message, tenant)
				except ASABIrisError as e:
					L.info("Error notification to MSTeams unsuccessful: Explanation: {}".format(e.TechMessage))

			elif service_type == 'sms':
				try:
					L.log(asab.LOG_NOTICE, "Sending error notification to SMS.")
					msg_copy = msg.copy()
					msg_copy['message_body'] = error_message
					await self.App.SMSOutputService.send(msg_copy)
				except Exception:
					L.exception("Error notification to SMS unsuccessful.")

		except Exception:
			L.exception("An unexpected error occurred while sending error message for {}.".format(service_type))

	def generate_error_message(self, specific_error: str, service_type: str):
		try:
			timestamp = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

			if service_type == 'email':
				error_subject = "Error Generating Email Notification."
				error_message = (
					"<p>Hello!</p>"
					"<p>We encountered an issue while processing your request:<br><b>{}</b></p>"
					"<p>Please review your input and try again.<p>"
					"<p>Time: {} UTC</p>"
					"<p>Best regards,<br>Your Team</p>"
				).format(specific_error, timestamp)
				return error_message, error_subject

			elif service_type == 'slack':
				error_message = (
					":warning: *Hello!*\n\n"
					"We encountered an issue while processing your request:\n`{}`\n\n"
					"Please review your input and try again.\n\n"
					"*Time:* `{}` UTC\n\n"
					"Best regards,\nYour Team :robot_face:"
				).format(specific_error, timestamp)
				return error_message, None

			elif service_type == 'msteams':
				error_message = (
					"Warning: Hello!\n\n"
					"We encountered following issue while processing your request.\n\n`{}`\n\n"
					"Please review your input and try again.\n\n"
					"Time: `{}` UTC\n\n"
					"Best regards,\nYour Team"
				).format(specific_error, timestamp)
				return error_message, None

			elif service_type == 'sms':
				error_message = (
					"Hello! Issue processing your request: {}. Please check and retry. Time: {} UTC."
				).format(specific_error[:50], timestamp)  # Truncate specific_error if necessary
				return error_message, None

		except Exception:
			L.exception("An unexpected error occurred while generating error message.")
			return None, None
