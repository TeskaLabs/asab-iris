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

from ..errors import ASABIrisError

L = logging.getLogger(__name__)


def check_config(config, section, parameter):
	try:
		value = config.get(section, parameter)
		return value
	except configparser.NoOptionError:
		L.error("Configuration parameter '{}' is missing in section '{}'.".format(parameter, section))
		exit()


class KafkaHandler(asab.Service):
	ValidationSchemaMail = fastjsonschema.compile(email_schema)
	ValidationSchemaSlack = fastjsonschema.compile(slack_schema)
	ValidationSchemaMSTeams = fastjsonschema.compile(teams_schema)

	def __init__(self, app, service_name="KafkaHandler"):
		super().__init__(app, service_name)
		self.Task = None
		self.JinjaService = app.get_service("JinjaService")
		# output service's
		self.EmailOutputService = app.get_service("SmtpService")
		self.SlackOutputService = app.get_service("SlackService")
		self.MSTeamsOutputService = app.get_service("MSTeamsService")
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
				self.ValidationSchemaMail(msg)
				await self.send_email(msg)
			except fastjsonschema.exceptions.JsonSchemaException as e:
				L.warning("Invalid notification format: {}".format(e))
				return
			except ASABIrisError as e:
				# if it is a server error do not send notification.
				if e.ErrorCode in [1011, 1012, 1013, 1014, 1015, 1016]:
					L.warning("Failed to send email: {}".format(e))
					return
				else:
					await self.handle_exception(e, 'email', msg)
			except Exception as e:
				L.warning("Failed to send email: {}".format(e))
				await self.handle_exception(e, 'email', msg)

		elif msg_type == "slack":
			try:
				self.ValidationSchemaSlack(msg)
			except fastjsonschema.exceptions.JsonSchemaException as e:
				L.warning("Invalid notification format: {}".format(e))
				return
			except ASABIrisError as e:
				# if it is a server error do not send notification.
				if e.ErrorCode == 1010:
					L.warning("Failed to send notification to slack: {}".format(e))
					return
				else:
					await self.handle_exception(e, 'slack')
			except Exception as e:
				L.warning("Failed to send notification to slack: {}".format(e))
				await self.handle_exception(e, 'slack')

		elif msg_type == "msteams":
			try:
				self.ValidationSchemaMSTeams(msg)
			except fastjsonschema.exceptions.JsonSchemaException as e:
				L.warning("Invalid notification format: {}".format(e))
				return
			except ASABIrisError as e:
				# if it is a server error do not send notification.
				if e.ErrorCode == 1007:
					L.warning("Failed to send notification to MSTeams: {}".format(e))
					return
				else:
					await self.handle_exception(e, 'slack')
			except Exception as e:
				L.warning("Failed to send MS Teams message: {}".format(e))
				await self.handle_exception(e, 'msteams')

	# Add similar logic for 'msteams' if needed

	async def send_email(self, json_data):
		await self.EmailOutputService.send_email(
			from_addr=json_data['from'],
			to_addrs=json_data['to'],
			subject=json_data.get('subject', 'No Subject'),
			body=json_data.get('body', ''),
			cc=json_data.get('cc', []),
			bcc=json_data.get('bcc', []),
			attachments=json_data.get('attachments', [])
		)
		L.info("Email sent successfully")

	async def handle_exception(self, exception, service_type, msg=None):
		L.warning("Exception occurred: {}".format(exception))
		error_message, error_subject = self.generate_error_message(str(exception), service_type)

		if service_type == 'email' and msg:
			await self.EmailOutputService.send(
				email_from=msg['from'],
				email_to=msg['to'],
				email_subject=error_subject,
				body=error_message
			)
		elif service_type == 'slack':
			await self.SlackOutputService.send_message(error_message)
		elif service_type == 'msteams':
			await self.MSTeamsOutputService.send_message(error_message)

	def generate_error_message(self, specific_error: str, service_type: str):
		timestamp = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

		if service_type == 'email':
			error_subject = "Error when generating notification"
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
			return error_message

		elif service_type == 'msteams':
			error_message = (
				"Warning: *Hello!\n\n"
				"We encountered an issue while processing your request:\n`{}`\n\n"
				"Please review your input and try again.\n\n"
				"Time: `{}` UTC\n\n"
				"Best regards,\nYour Team"
			).format(specific_error, timestamp)
			return error_message
