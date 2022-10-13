import asyncio
import configparser
import json
import logging

from aiokafka import AIOKafkaConsumer
import kafka.errors
import aiohttp
import fastjsonschema

import asab
import asab.web.rest

from .. import utils

#

L = logging.getLogger(__name__)

#


class NotificationsService(asab.Service):


	def __init__(self, app, service_name="asab.NotificationsService"):
		super().__init__(app, service_name)
		self.EmailOutputService = self.App.get_service("asab.SmtpService")
		self.JinjaService = self.App.get_service("asab.JinjaService")
		self.MarkdownService = self.App.get_service("asab.MarkdowntoHTMLService")
		self.Task = None

		TOPIC = asab.Config.get("kafka", "topic")
		GROUP_ID = asab.Config.get("kafka", "group_id")
		BOOTSTRAP_SERVERS = list(asab.Config.get("kafka", "bootstrap_servers").split(","))
		self.Consumer = AIOKafkaConsumer(
			TOPIC,
			group_id=GROUP_ID,
			bootstrap_servers=BOOTSTRAP_SERVERS,
			loop=self.App.Loop,
			retry_backoff_ms=10000
		)

		# If there is slack configuration section, but no webhook_url, exception is raised.
		try:
			self.SlackWebhookUrl = asab.Config.get("slack", "webhook_url")
		except configparser.NoOptionError as e:
			L.error("Please provide webhook_url in slack configuration section.")
			raise e
		except configparser.NoSectionError:
			self.SlackWebhookUrl = None


	async def initialize(self, app):
		try:
			await self.Consumer.start()
		except kafka.errors.KafkaConnectionError as e:
			L.warning("No connection to Kafka established. Stopping the app... {}".format(e))
			exit()
		self.Task = asyncio.ensure_future(self.consume(), loop=self.App.Loop)


	async def finalize(self, app):
		await self.Consumer.stop()
		if self.Task.exception() is not None:
			L.warning("Exception occured during alert notifications: {}".format(self.Task.exception()))


	async def consume(self):
		async for msg in self.Consumer:
			await self.dispatch(json.loads(msg.value.decode("utf-8")))


	async def dispatch(self, msg):
		notif_type = msg.get("type")
		if notif_type in {"mail", "e-mail"}:
			try:
				NotificationsService.ValidationSchemaMail(msg)
			except fastjsonschema.exceptions.JsonSchemaException as e:
				L.warning("Invalid notification format. E-mail was not sent. {}".format(e))
				return
			msg.pop("type")
			await self.send_mail(msg)

		elif notif_type == "slack":
			try:
				NotificationsService.ValidationSchemaSlack(msg)
			except fastjsonschema.exceptions.JsonSchemaException as e:
				L.warning("Invalid notification format. Alert was not sent to Slack. {}".format(e))
				return
			msg.pop("type")
			await self.send_to_slack(msg)

		else:
			L.warning("Notification type '{}' not implemented. Sorry :( ".format(notif_type))

	@asab.web.rest.json_schema_handler({
		"type": "object",
		"properties": {
			"type": {"type": "string"},
			"to": {"type": "string"},
			"template": {"type": "string"},
			"alert": {"type": "object"},
			"event": {"type": "object"}
		},
		"required": ["type", "to", "template", "alert", "event"],
	})
	async def send_mail(self, msg):
		to = msg.pop("to")
		template = msg.pop("template")
		body = await self.JinjaService.format(msg, template)
		subject, body = utils.find_subject_in_html(body)
		if template.endswith(".md"):
			body = self.MarkdownService.format(body)
		await self.EmailOutputService.send(to=to, body_html=body, subject=subject)

	@asab.web.rest.json_schema_handler({
		"type": "object",
		"properties": {
			"type": {"type": "string"},
			"template": {"type": "string"},
			"alert": {"type": "object"},
			"event": {"type": "object"}
		},
		"required": ["type", "template", "alert", "event"],
	})
	async def send_to_slack(self, msg):
		if self.SlackWebhookUrl is None:
			return
		template = msg.pop("template")
		body = await self.JinjaService.format(msg, template)
		async with aiohttp.ClientSession() as session:
			async with session.post(self.SlackWebhookUrl, json={"text": body}) as resp:
				if resp.status != 200:
					L.warning("Sending alert to Slack was NOT successful. Response status: {}, response: {}".format(resp.status, await resp.text()))
