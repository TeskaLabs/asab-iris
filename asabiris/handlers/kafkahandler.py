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

from typing import Tuple

#

L = logging.getLogger(__name__)


#

def check_config(config, section, parameter):
	try:
		value = config.get(section, parameter)
		return value
	except configparser.NoOptionError:
		L.error("Configuration parameter '{}' is missing in section '{}'.".format(parameter, section))
		exit()


class KafkaHandler(asab.Service):
	# validate slack and email messages
	ValidationSchemaMail = fastjsonschema.compile(email_schema)
	ValidationSchemaSlack = fastjsonschema.compile(slack_schema)

	# TODO: ValidationSchemaMSTeams = fastjsonschema.compile(msteams_schema)

	def __init__(self, app, service_name="KafkaHandler"):
		super().__init__(app, service_name)

		self.Task = None
		self.JinjaService = app.get_service("JinjaService")
		# output services
		self.EmailOutputService = app.get_service("SmtpService")
		try:
			topic = check_config(asab.Config, "kafka", "topic")
			group_id = check_config(asab.Config, "kafka", "group_id")
			bootstrap_servers = check_config(asab.Config, "kafka", "bootstrap_servers").split(",")
		except configparser.NoOptionError:
			L.error("Configuration missing. Required parameters: Kafka/group_id/bootstrap_servers")
			exit()

		self.Consumer = AIOKafkaConsumer(
			topic,
			group_id=group_id,
			bootstrap_servers=bootstrap_servers,
			loop=self.App.Loop,
			retry_backoff_ms=10000,
			auto_offset_reset="earliest",
		)

	async def initialize(self, app):
		try:
			await self.Consumer.start()
		except aiokafka.errors.KafkaConnectionError as e:
			L.warning("No connection to Kafka established. Stopping the app... {}".format(e))
			exit()
		self.Task = asyncio.ensure_future(self.consume(), loop=self.App.Loop)

	async def finalize(self, app):
		await self.Consumer.stop()
		if self.Task.exception() is not None:
			L.warning("Exception occurred during alert notifications: {}".format(self.Task.exception()))

	async def consume(self):
		async for msg in self.Consumer:
			try:
				msg = msg.value.decode("utf-8")
				msg = json.loads(msg)
			except Exception as e:
				L.warning("Invalid message format: '{}'".format(e))
			try:
				await self.dispatch(msg)
			except Exception:
				L.exception("General error when dispatching message")

	async def dispatch(self, msg):
		msg_type = msg.pop("type", "<missing>")
		if msg_type == "email":
			try:
				KafkaHandler.ValidationSchemaMail(msg)
				await self.send_email(msg)
			except fastjsonschema.exceptions.JsonSchemaException as e:
				L.warning("Invalid notification format: {}".format(e))
			except Exception as e:
				L.exception("Failed to send email: {}".format(e))
				await self.handle_exception(e, msg)

		elif msg_type == "slack":
			try:
				KafkaHandler.ValidationSchemaSlack(msg)
				if self.App.SendSlackOrchestrator is not None:
					await self.App.SendSlackOrchestrator.send_to_slack(msg)
				else:
					L.warning("Slack is not configured, a notification is discarded")
			except fastjsonschema.exceptions.JsonSchemaException as e:
				L.warning("Invalid notification format: {}".format(e))
			except Exception as e:
				L.exception("Failed to send slack message: {}".format(e))

		elif msg_type == "msteams":
			# TODO: Validation for MSTeams
			try:
				if self.App.SendMSTeamsOrchestrator is not None:
					await self.App.SendMSTeamsOrchestrator.send_to_msteams(msg)
				else:
					L.warning("MS Teams is not configured, a notification is discarded")
			except Exception as e:
				L.exception("Failed to send MS Teams message: {}".format(e))

		else:
			L.warning("Message type '{}' not implemented.".format(msg_type))

	async def send_email(self, json_data):
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

	async def handle_exception(self, exception, msg):
		"""
		Asynchronously handles an exception by sending an email notification.

		Overrides the abstract method from ExceptionStrategy. It sends an email using the
		EmailOutputService if 'from_email' and 'to_emails' are provided in notification_params.
		Logs an error message if the necessary parameters are missing.

		Args:
			exception (Exception): The exception to handle.
			notification_params (Optional[dict]): Parameters for the email notification,
			including 'from_email' and 'to_emails'.

		Raises:
			KeyError: If 'from_email' or 'to_emails' are missing in notification_params.
		"""
		L.warning("Exception occurred: {}".format(exception))

		error_message, error_subject = self._generate_error_message(str(exception))

		# Send the email
		await self.EmailOutputService.send(
			email_from=msg['from'],
			email_to=msg['to'],
			email_subject=error_subject,
			body=error_message
		)

	def _generate_error_message(self, specific_error: str) -> Tuple[str, str]:
		"""
		Generates an error message and subject for the email.

		Args:
			specific_error: The specific error message.

		Returns:
			Tuple containing the error message and subject.
		"""
		timestamp = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

		error_message = (
			"<p>Hello!</p>"
			"<p>We encountered an issue while processing your request:<br><b>{}</b></p>"
			"<p>Please review your input and try again.<p>"
			"<p>Time: {} UTC</p>"
			"<p>Best regards,<br>Your Team</p>").format(specific_error, timestamp)
		return error_message, "Error when generating email"
