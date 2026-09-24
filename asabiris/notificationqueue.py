import asyncio
import contextlib
import json
import logging
import random
import time
import uuid

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import aiokafka.errors

import asab
import asab.contextvars

from .output.retry import TemporaryDeliveryError


L = logging.getLogger(__name__)


asab.Config.add_defaults({
	"notification_retry": {
		"bootstrap_servers": "",
		"topic": "asab-iris-retries",
		"group_id": "asab-iris-retries",
		"max_attempts": "8",
		"initial_delay": "5",
		"max_delay": "300",
		"jitter": "0.2",
		"retention": "86400",
		"workers": "2",
		"rate_limit": "5",
	}
})


class NotificationQueueService(asab.Service):

	def __init__(self, app, service_name="NotificationQueueService"):
		super().__init__(app, service_name)
		metrics_service = app.get_service("asab.MetricsService")
		self.Counter = metrics_service.create_counter(
			"iris_notification_retry_total",
			reset=False,
			help="Notification retry outcomes.",
		)
		self.Topic = asab.Config.get("notification_retry", "topic")
		self.GroupId = asab.Config.get("notification_retry", "group_id")
		self.MaxAttempts = asab.Config.getint("notification_retry", "max_attempts")
		self.InitialDelay = asab.Config.getfloat("notification_retry", "initial_delay")
		self.MaxDelay = asab.Config.getfloat("notification_retry", "max_delay")
		self.Jitter = asab.Config.getfloat("notification_retry", "jitter")
		self.Retention = asab.Config.getfloat("notification_retry", "retention")
		self.WorkerCount = asab.Config.getint("notification_retry", "workers")
		self.RateLimit = asab.Config.getfloat("notification_retry", "rate_limit")
		self.BootstrapServers = None
		self.Producer = None
		self.Consumers = []
		self.Tasks = []
		self.RateLock = asyncio.Lock()
		self.NextDelivery = 0
		self._validate_config()

	def _validate_config(self):
		if not self.Topic or not self.GroupId:
			raise ValueError("notification_retry.topic and group_id must not be empty")
		if self.MaxAttempts < 1:
			raise ValueError("notification_retry.max_attempts must be at least 1")
		if self.InitialDelay < 0 or self.MaxDelay < self.InitialDelay:
			raise ValueError("Invalid notification retry delays")
		if not 0 <= self.Jitter <= 1:
			raise ValueError("notification_retry.jitter must be between 0 and 1")
		if self.Retention <= 0 or self.WorkerCount < 1 or self.RateLimit <= 0:
			raise ValueError("Invalid notification retry retention, workers, or rate_limit")

	async def initialize(self, app):
		bootstrap_servers = asab.Config.get("notification_retry", "bootstrap_servers")
		if not bootstrap_servers and asab.Config.has_section("kafka"):
			bootstrap_servers = asab.Config.get("kafka", "bootstrap_servers", fallback="")
		if not bootstrap_servers:
			L.warning("Notification retries are disabled because no Kafka bootstrap servers are configured.")
			return
		self.BootstrapServers = bootstrap_servers.split(",")

		self.Producer = AIOKafkaProducer(
			bootstrap_servers=self.BootstrapServers,
			loop=self.App.Loop,
			enable_idempotence=True,
		)
		try:
			await self.Producer.start()
		except aiokafka.errors.KafkaError:
			L.exception(
				"Notification retry producer could not connect to Kafka; retries are disabled.",
				struct_data={"topic": self.Topic, "bootstrap_servers": self.BootstrapServers},
			)
			self.Producer = None
			return

		for index in range(self.WorkerCount):
			consumer = AIOKafkaConsumer(
				self.Topic,
				group_id=self.GroupId,
				bootstrap_servers=self.BootstrapServers,
				loop=self.App.Loop,
				enable_auto_commit=False,
				auto_offset_reset="earliest",
				max_poll_interval_ms=int((self.MaxDelay + 60) * 1000),
			)
			try:
				await consumer.start()
			except aiokafka.errors.KafkaError:
				L.exception(
					"Notification retry worker could not connect to Kafka.",
					struct_data={"topic": self.Topic, "worker": index},
				)
				with contextlib.suppress(Exception):
					await consumer.stop()
				continue
			self.Consumers.append(consumer)
			self.Tasks.append(asyncio.create_task(self._consume(consumer, index)))

	async def finalize(self, app):
		for task in self.Tasks:
			task.cancel()
		for task in self.Tasks:
			with contextlib.suppress(asyncio.CancelledError):
				await task
		for consumer in self.Consumers:
			await consumer.stop()
		if self.Producer is not None:
			await self.Producer.stop()

	async def deliver(self, kind, payload, source_key=None):
		now = time.time()
		envelope = {
			"id": source_key or uuid.uuid4().hex,
			"kind": kind,
			"payload": payload,
			"attempts": 0,
			"next_attempt_at": now,
			"expires_at": now + self.Retention,
		}
		error = await self._attempt_delivery(envelope)
		if error is None:
			self.Counter.add("delivered_without_retry", 1)
			return True

		if envelope["attempts"] >= self.MaxAttempts or self.Producer is None:
			raise error
		envelope["next_attempt_at"] = time.time() + self._delay(envelope["attempts"])
		envelope["last_error"] = error.TechMessage
		await self._publish(envelope)
		self.Counter.add("queued", 1)
		L.warning(
			"Notification queued in Kafka after a temporary provider failure.",
			struct_data={"notification_id": envelope["id"], "provider": kind, "attempt": envelope["attempts"]},
		)
		return False

	async def _publish(self, envelope):
		value = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
		key = envelope["id"].encode("utf-8")
		await self.Producer.send_and_wait(self.Topic, value=value, key=key)

	def _delay(self, attempts):
		base = min(self.MaxDelay, self.InitialDelay * (2 ** max(0, attempts - 1)))
		return base + random.uniform(0, base * self.Jitter)

	async def _consume(self, consumer, worker):
		async for message in consumer:
			try:
				envelope = json.loads(message.value.decode("utf-8"))
				self._validate_envelope(envelope)
			except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
				L.warning(
					"Invalid notification retry message was discarded.",
					struct_data={"topic": self.Topic, "worker": worker, "error_type": type(error).__name__},
				)
				await consumer.commit()
				continue

			try:
				await self._wait_until_due(envelope)
				await self._throttle()
				await self._process(envelope, worker)
				await consumer.commit()
			except asyncio.CancelledError:
				raise
			except aiokafka.errors.KafkaError:
				L.exception(
					"Kafka retry message was not committed and will be read again.",
					struct_data={"notification_id": envelope["id"], "worker": worker},
				)
			except Exception:
				L.exception(
					"Notification retry worker failed; the Kafka message was not committed.",
					struct_data={"notification_id": envelope["id"], "provider": envelope["kind"], "worker": worker},
				)

	def _validate_envelope(self, envelope):
		if not isinstance(envelope, dict):
			raise TypeError("Retry message must be an object")
		for key in ("id", "kind", "payload", "attempts", "next_attempt_at", "expires_at"):
			if key not in envelope:
				raise KeyError(key)
		if not isinstance(envelope["id"], str) or not isinstance(envelope["kind"], str):
			raise TypeError("Retry id and kind must be strings")
		if not isinstance(envelope["payload"], dict) or not isinstance(envelope["attempts"], int):
			raise TypeError("Retry payload or attempts has an invalid type")
		float(envelope["next_attempt_at"])
		float(envelope["expires_at"])

	async def _wait_until_due(self, envelope):
		delay = max(0, float(envelope["next_attempt_at"]) - time.time())
		if delay:
			await asyncio.sleep(min(delay, self.MaxDelay))

	async def _throttle(self):
		async with self.RateLock:
			now = self.App.Loop.time()
			if self.NextDelivery > now:
				await asyncio.sleep(self.NextDelivery - now)
			self.NextDelivery = self.App.Loop.time() + (1 / self.RateLimit)

	async def _process(self, envelope, worker):
		kind = envelope["kind"]
		payload = envelope["payload"]
		if time.time() >= envelope["expires_at"]:
			self.Counter.add("failed", 1)
			L.error(
				"Notification retry retention expired.",
				struct_data={"notification_id": envelope["id"], "provider": kind, "attempts": envelope["attempts"]},
			)
			await self._terminal_fallback(kind, payload, "Retry retention expired")
			return

		try:
			error = await self._attempt_delivery(envelope)
		except Exception as error:
			self.Counter.add("failed", 1)
			L.exception(
				"Notification retry stopped after a permanent failure.",
				struct_data={"notification_id": envelope["id"], "provider": kind, "worker": worker},
			)
			await self._terminal_fallback(kind, payload, str(error))
			return

		if error is None:
			self.Counter.add("delivered_after_retry", 1)
			L.info(
				"Queued notification delivered.",
				struct_data={"notification_id": envelope["id"], "provider": kind, "attempts": envelope["attempts"]},
			)
			return

		now = time.time()
		if envelope["attempts"] >= self.MaxAttempts or now >= envelope["expires_at"]:
			self.Counter.add("failed", 1)
			L.error(
				"Notification retry exhausted.",
				struct_data={"notification_id": envelope["id"], "provider": kind, "attempts": envelope["attempts"]},
			)
			await self._terminal_fallback(kind, payload, error.TechMessage)
			return
		envelope["next_attempt_at"] = now + self._delay(envelope["attempts"])
		envelope["last_error"] = error.TechMessage
		await self._publish(envelope)

	async def _attempt_delivery(self, envelope):
		envelope["attempts"] += 1
		self.Counter.add("attempted", 1)
		try:
			await self._dispatch(envelope["kind"], envelope["payload"])
		except TemporaryDeliveryError as error:
			return error
		return None

	async def _terminal_fallback(self, kind, payload, error):
		await self.App.KafkaHandler.handle_exception(error, kind, payload)

	async def _dispatch(self, kind, payload):
		tenant = payload.get("tenant")
		token = None
		if tenant is not None and asab.contextvars.Tenant.get(None) is None:
			token = asab.contextvars.Tenant.set(tenant)
		try:
			if kind == "email":
				await self.App.SendEmailOrchestrator.send_email(
					email_to=payload.get("to"),
					body_template=payload["body"]["template"],
					body_template_wrapper=payload["body"].get("wrapper"),
					body_params=payload["body"].get("params", {}),
					email_from=payload.get("from"),
					email_cc=payload.get("cc", []),
					email_bcc=payload.get("bcc", []),
					email_subject=payload.get("subject"),
					attachments=payload.get("attachments", []),
					retry_payload=payload,
				)
			elif kind == "slack":
				await self.App.SendSlackOrchestrator.send_to_slack(payload)
			elif kind == "mattermost":
				await self.App.SendMattermostOrchestrator.send_to_mattermost(payload)
			elif kind == "msteams":
				await self.App.SendMSTeamsOrchestrator.send_to_msteams(payload)
			elif kind == "sms":
				await self.App.SendSMSOrchestrator.send_sms(payload)
			elif kind == "push":
				await self.App.SendPushOrchestrator.send_push(payload)
			else:
				raise ValueError("Unsupported notification kind: {}".format(kind))
		finally:
			if token is not None:
				asab.contextvars.Tenant.reset(token)
