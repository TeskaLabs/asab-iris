import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer
import aiokafka.errors
import fastjsonschema

import asab

from asabiris.schemas.emailschema import email_schema
from asabiris.schemas.slackschema import slack_schema
#

L = logging.getLogger(__name__)


#


class KafkaHandler(asab.Service):

	# validate slack and email messages
	ValidationSchemaMail = fastjsonschema.compile(email_schema)
	ValidationSchemaSlack = fastjsonschema.compile(slack_schema)
	# TODO: ValidationSchemaMSTeams = fastjsonschema.compile(msteams_schema)

	def __init__(self, app, service_name="KafkaHandler"):
		super().__init__(app, service_name)

		self.Task = None
		self.JinjaService = app.get_service("JinjaService")
		topic = asab.Config.get("kafka", "topic")
		group_id = asab.Config.get("kafka", "group_id")
		bootstrap_servers = list(asab.Config.get("kafka", "bootstrap_servers").split(","))
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
			except fastjsonschema.exceptions.JsonSchemaException as e:
				L.warning("Invalid notification format: {}".format(e))
				return
			await self.send_email(msg)

		elif msg_type == "slack":
			try:
				KafkaHandler.ValidationSchemaSlack(msg)
			except fastjsonschema.exceptions.JsonSchemaException as e:
				L.warning("Invalid notification format: {}".format(e))
				return
			if self.App.SendSlackOrchestrator is not None:
				await self.App.SendSlackOrchestrator.send_to_slack(msg)
			else:
				L.warning("Slack is not configured, a notification is discarded")

		elif msg_type == "msteams":
			# TODO: This ...
			# try:
			# 	KafkaHandler.ValidationSchemaMSTeams(msg)
			# except fastjsonschema.exceptions.JsonSchemaException as e:
			# 	L.warning("Invalid notification format: {}".format(e))
			# 	return
			if self.App.SendMSTeamsOrchestrator is not None:
				await self.App.SendMSTeamsOrchestrator.send_to_msteams(msg)
			else:
				L.warning("MS Teams is not configured, a notification is discarded")

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
