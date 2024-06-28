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
	except configparser.NoOptionError:
		L.error("Configuration parameter '{}' is missing in section '{}'.".format(parameter, section))
		exit()


class KafkaHandler(asab.Service):
	ValidationSchemaMail = fastjsonschema.compile(email_schema)
	ValidationSchemaSlack = fastjsonschema.compile(slack_schema)
	ValidationSchemaMSTeams = fastjsonschema.compile(teams_schema)
	ValidationSchemaSMS = fastjsonschema.compile(sms_schema)

	def __init__(self, app, service_name="KafkaHandler"):
		super().__init__(app, service_name)
		self.Task = None
		self.JinjaService = app.get_service("JinjaService")
		# output service's
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
		try:
			msg_type = msg.pop("type", "<missing>")
		except (AttributeError, Exception) as e:
			L.warning("Error sending notification from kafka. Reason : {}".format(str(e)))
			return

		if msg_type == "email":
			try:
				KafkaHandler.ValidationSchemaMail(msg)
			except fastjsonschema.exceptions.JsonSchemaException as e:
				L.warning("Invalid email notification format: {}".format(e))
				return
			try:
				await self.send_email(msg)
			except ASABIrisError as e:
				# if it is a server error do not send notification.
				server_errors = [
					ErrorCode.SMTP_CONNECTION_ERROR,
					ErrorCode.SMTP_AUTHENTICATION_ERROR,
					ErrorCode.SMTP_RESPONSE_ERROR,
					ErrorCode.SMTP_SERVER_DISCONNECTED,
					ErrorCode.SMTP_GENERIC_ERROR,
					ErrorCode.GENERAL_ERROR
				]
				if e.ErrorCode in server_errors:
					L.warning("Unable to dispatch email: Explanation {}".format(e.TechMessage))
					return
				else:
					# Handle other errors using handle_exception function
					await self.handle_exception(e.TechMessage, 'email', msg)
			except Exception as e:
				# Handle any other unexpected exceptions using handle_exception function
				await self.handle_exception(e, 'email', msg)

		elif msg_type == "slack":
			try:
				KafkaHandler.ValidationSchemaSlack(msg)
			except fastjsonschema.exceptions.JsonSchemaException as e:
				L.warning("Invalid slack notification format: {}".format(e))
				return

			try:
				if self.App.SendSlackOrchestrator is not None:
					await self.App.SendSlackOrchestrator.send_to_slack(msg)
				else:
					L.warning("Slack is not configured, a notification is discarded")
					return
			except ASABIrisError as e:
				# if it is a server error do not send notification.
				if e.ErrorCode == ErrorCode.SLACK_API_ERROR:
					L.warning("Notification to Slack unsuccessful: Explanation: {}".format(e.TechMessage))
					return
				else:
					# Handle other errors using handle_exception function
					await self.handle_exception(e.TechMessage, 'slack')
			except Exception as e:
				# Handle any other unexpected exceptions using handle_exception function
				await self.handle_exception(e, 'slack')

		elif msg_type == "msteams":
			try:
				KafkaHandler.ValidationSchemaMSTeams(msg)
			except fastjsonschema.exceptions.JsonSchemaException as e:
				L.warning("Invalid notification format: {}".format(e))
				return
			try:
				if self.App.SendMSTeamsOrchestrator is not None:
					await self.App.SendMSTeamsOrchestrator.send_to_msteams(msg)
				else:
					L.warning("MS Teams is not configured, a notification is discarded")
					return
			except ASABIrisError as e:
				# if it is a server error do not send notification.
				if e.ErrorCode == ErrorCode.SERVER_ERROR:
					L.warning("Notification to MSTeams unsuccessful: Explanation: {}".format(e.TechMessage))
					return
				else:
					# Handle other errors using handle_exception function
					await self.handle_exception(e.TechMessage, 'msteams')
			except Exception as e:
				# Handle any other unexpected exceptions using handle_exception function
				await self.handle_exception(e, 'msteams')

		elif msg_type == "sms":
			try:
				KafkaHandler.ValidationSchemaSMS(msg)
			except fastjsonschema.exceptions.JsonSchemaException as e:
				L.warning("Invalid notification format: {}".format(e))
				return
			try:
				if self.App.SendSMSOrchestrator is not None:
					await self.App.SendSMSOrchestrator.send_sms(msg)
				else:
					L.warning("SMS is not configured, a notification is discarded")
					return
			except ASABIrisError as e:
				# if it is a server error do not send notification.
				if e.ErrorCode == ErrorCode.SERVER_ERROR:
					L.warning("Notification to SMS unsuccessful: Explanation: {}".format(e.TechMessage))
					return
				else:
					# Handle other errors using handle_exception function
					await self.handle_exception(e.TechMessage, 'sms', msg)
			except Exception as e:
				# Handle any other unexpected exceptions using handle_exception function
				await self.handle_exception(e, 'sms', msg)

		else:
			L.warning(
				"Notification sending failed: Unsupported message type '{}'. "
				"Supported types are 'email', 'slack', and 'msteams'. ".format(msg_type)
			)

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
			# Log the problem first and then send error notification accordingly
			L.warning("Encountered an issue while sending '{}'. Details: {}.".format(service_type, exception))

			error_message, error_subject = self.generate_error_message(str(exception), service_type)

			# Check if error_message is None
			if error_message is None:
				return

			if service_type == 'email' and msg:
				try:
					L.log(asab.LOG_NOTICE, "Sending error notification to email.")
					await self.App.EmailOutputService.send(
						email_from=msg.get('from', None),
						email_to=msg['to'],
						email_subject=error_subject,
						body=error_message
					)
				except ASABIrisError as e:
					L.info("Error notification to email unsuccessful: Explanation: {}".format(e.TechMessage))
				except Exception:
					L.exception("Error notification to email unsuccessful.")

			elif service_type == 'slack':
				try:
					L.log(asab.LOG_NOTICE, "Sending error notification to slack.")
					await self.App.SlackOutputService.send_message(None, error_message)
				except ASABIrisError as e:
					L.info("Error notification to Slack unsuccessful: Explanation: {}".format(e.TechMessage))
				except Exception:
					L.exception("Error notification to Slack unsuccessful.")

			elif service_type == 'msteams':
				try:
					L.log(asab.LOG_NOTICE, "Sending error notification to MSTeams.")
					await self.App.MSTeamsOutputService.send(error_message)
				except ASABIrisError as e:
					L.info("Error notification to MSTeams unsuccessful: Explanation: {}".format(e.TechMessage))
				except Exception:
					L.exception("Error notification to MSTeams unsuccessful.")

			elif service_type == 'sms':
				try:
					L.log(asab.LOG_NOTICE, "Sending error notification to SMS.")
					msg['message_body'] = error_message
					await self.App.SMSOutputService.send(msg)
				except ASABIrisError as e:
					L.info("Error notification to SMS unsuccessful: Explanation: {}".format(e.TechMessage))
				except Exception:
					L.exception("Error notification to SMS unsuccessful.")


		except Exception:
			# Log any unexpected exceptions that might occur
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
					"Hello! We encountered an issue while processing your request: {}. Please review your input and try again. Time: {} UTC. Best regards, Your Team"
				).format(specific_error, timestamp)
				return error_message, None

		except Exception:
			# Log any unexpected exceptions that might occur while generating error message
			L.exception("An unexpected error occurred while generating error message.")
			return None, None
