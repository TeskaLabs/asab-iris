import asyncio
import contextlib
import hashlib
import json
import logging
import os
from pathlib import Path
import random
import time
import uuid

import asab
import asab.contextvars

from .output.retry import TemporaryDeliveryError


L = logging.getLogger(__name__)


asab.Config.add_defaults({
	"notification_retry": {
		"path": "./var/notification-retry",
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

	States = ("tmp", "ready", "processing", "retry", "failed")

	def __init__(self, app, service_name="NotificationQueueService"):
		super().__init__(app, service_name)
		metrics_service = app.get_service("asab.MetricsService")
		self.Counter = metrics_service.create_counter(
			"iris_notification_retry_total", reset=False, help="Notification retry outcomes."
		)
		self.Root = Path(asab.Config.get("notification_retry", "path")).expanduser()
		self.MaxAttempts = asab.Config.getint("notification_retry", "max_attempts")
		self.InitialDelay = asab.Config.getfloat("notification_retry", "initial_delay")
		self.MaxDelay = asab.Config.getfloat("notification_retry", "max_delay")
		self.Jitter = asab.Config.getfloat("notification_retry", "jitter")
		self.Retention = asab.Config.getfloat("notification_retry", "retention")
		self.WorkerCount = asab.Config.getint("notification_retry", "workers")
		self.RateLimit = asab.Config.getfloat("notification_retry", "rate_limit")
		self.Tasks = []
		self.Wakeup = asyncio.Event()
		self.RateLock = asyncio.Lock()
		self.NextDelivery = 0
		self._validate_config()

	def _validate_config(self):
		if self.MaxAttempts < 1:
			raise ValueError("notification_retry.max_attempts must be at least 1")
		if self.InitialDelay < 0 or self.MaxDelay < self.InitialDelay:
			raise ValueError("Invalid notification retry delays")
		if not 0 <= self.Jitter <= 1:
			raise ValueError("notification_retry.jitter must be between 0 and 1")
		if self.Retention <= 0 or self.WorkerCount < 1 or self.RateLimit <= 0:
			raise ValueError("Invalid notification retry retention, workers, or rate_limit")

	async def initialize(self, app):
		for state in self.States:
			self._directory(state).mkdir(mode=0o700, parents=True, exist_ok=True)
		for temporary in self._directory("tmp").glob("*.tmp"):
			temporary.unlink()
		self._recover_processing()
		for worker in range(self.WorkerCount):
			self.Tasks.append(asyncio.create_task(self._worker(worker)))
		self.Wakeup.set()

	async def finalize(self, app):
		for task in self.Tasks:
			task.cancel()
		for task in self.Tasks:
			with contextlib.suppress(asyncio.CancelledError):
				await task

	async def deliver(self, kind, payload, source_key=None):
		notification_id = self._notification_id(source_key)
		if self._find(notification_id) is not None:
			L.info(
				"Notification is already present in the local spool.",
				struct_data={"notification_id": notification_id, "provider": kind},
			)
			return False
		prepared = await self._prepare(kind, payload)
		if prepared is None:
			return True
		if prepared.get("tenant") is None and payload.get("tenant") is not None:
			prepared["tenant"] = payload["tenant"]
		now = time.time()
		envelope = {
			"id": notification_id,
			"kind": kind,
			"payload": prepared,
			"attempts": 0,
			"next_attempt_at": now,
			"expires_at": now + self.Retention,
			"last_error": None,
		}
		ready = self._path("ready", notification_id)
		self._write(ready, envelope)
		processing = self._claim(ready)
		if processing is None:
			return False
		return await self._process(processing, envelope, worker=None, raise_permanent=True)

	def _notification_id(self, source_key):
		if source_key is None:
			return uuid.uuid4().hex
		return hashlib.sha256(source_key.encode("utf-8")).hexdigest()

	def _directory(self, state):
		return self.Root / state

	def _path(self, state, notification_id):
		return self._directory(state) / "{}.json".format(notification_id)

	def _find(self, notification_id):
		for state in self.States:
			path = self._path(state, notification_id)
			if path.exists():
				return path
		return None

	def _write(self, path, envelope):
		temporary = self._directory("tmp") / "{}.{}.tmp".format(envelope["id"], uuid.uuid4().hex)
		data = json.dumps(envelope, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
		fd = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
		with os.fdopen(fd, "wb") as output:
			output.write(data)
			output.flush()
			os.fsync(output.fileno())
		os.replace(temporary, path)
		self._fsync_directory(temporary.parent)
		self._fsync_directory(path.parent)

	def _move(self, source, state):
		target = self._path(state, source.stem)
		os.replace(source, target)
		self._fsync_directory(source.parent)
		if target.parent != source.parent:
			self._fsync_directory(target.parent)
		return target

	def _delete(self, path):
		path.unlink(missing_ok=True)
		self._fsync_directory(path.parent)

	def _fsync_directory(self, directory):
		fd = os.open(str(directory), os.O_RDONLY)
		try:
			os.fsync(fd)
		finally:
			os.close(fd)

	def _recover_processing(self):
		for path in self._directory("processing").glob("*.json"):
			try:
				envelope = self._read(path)
				envelope["last_error"] = "Delivery outcome is uncertain after Iris stopped during an attempt"
				self._write(path, envelope)
				self._move(path, "failed")
				self.Counter.add("failed", 1)
				L.error(
					"Interrupted notification moved to failed because its delivery outcome is uncertain.",
					struct_data={"notification_id": envelope["id"], "provider": envelope["kind"]},
				)
			except Exception:
				L.exception("Failed to recover an interrupted notification.", struct_data={"path": str(path)})

	def _read(self, path):
		with open(path, "r", encoding="utf-8") as source:
			envelope = json.load(source)
		self._validate_envelope(envelope)
		return envelope

	def _validate_envelope(self, envelope):
		if not isinstance(envelope, dict):
			raise TypeError("Queued notification must be an object")
		for key in ("id", "kind", "payload", "attempts", "next_attempt_at", "expires_at"):
			if key not in envelope:
				raise KeyError(key)
		if not isinstance(envelope["id"], str) or not isinstance(envelope["kind"], str):
			raise TypeError("Queued notification id and kind must be strings")
		if not isinstance(envelope["payload"], dict) or not isinstance(envelope["attempts"], int):
			raise TypeError("Queued notification payload or attempts has an invalid type")
		float(envelope["next_attempt_at"])
		float(envelope["expires_at"])

	def _claim(self, path):
		target = self._path("processing", path.stem)
		try:
			os.replace(path, target)
		except FileNotFoundError:
			return None
		self._fsync_directory(path.parent)
		self._fsync_directory(target.parent)
		return target

	async def _worker(self, worker):
		while True:
			processed = False
			for state in ("ready", "retry"):
				for path in self._directory(state).glob("*.json"):
					try:
						envelope = self._read(path)
						if float(envelope["next_attempt_at"]) > time.time():
							continue
						processing = self._claim(path)
						if processing is None:
							continue
						processed = True
						await self._process(processing, envelope, worker=worker)
					except asyncio.CancelledError:
						raise
					except Exception:
						L.exception("Notification spool worker failed.", struct_data={"path": str(path), "worker": worker})
			if processed:
				continue
			self.Wakeup.clear()
			try:
				await asyncio.wait_for(self.Wakeup.wait(), timeout=1)
			except asyncio.TimeoutError:
				pass

	async def _process(self, path, envelope, worker, raise_permanent=False):
		if time.time() >= envelope["expires_at"]:
			await self._fail(path, envelope, "Retry retention expired", worker)
			return False
		await self._throttle()
		envelope["attempts"] += 1
		self.Counter.add("attempted", 1)
		self._write(path, envelope)
		try:
			await self._dispatch(envelope["kind"], envelope["payload"])
		except TemporaryDeliveryError as error:
			if envelope["attempts"] >= self.MaxAttempts or time.time() >= envelope["expires_at"]:
				await self._fail(path, envelope, error.TechMessage, worker)
				return False
			envelope["last_error"] = error.TechMessage
			envelope["next_attempt_at"] = time.time() + self._delay(envelope["attempts"])
			self._write(path, envelope)
			self._move(path, "retry")
			self.Counter.add("queued", 1)
			self.Wakeup.set()
			L.warning(
				"Notification stored for retry after a temporary provider failure.",
				struct_data={"notification_id": envelope["id"], "provider": envelope["kind"], "attempt": envelope["attempts"]},
			)
			return False
		except Exception as error:
			await self._fail(path, envelope, str(error), worker, fallback=not raise_permanent)
			if raise_permanent:
				raise
			return False
		self._delete(path)
		self.Counter.add("delivered_without_retry" if envelope["attempts"] == 1 else "delivered_after_retry", 1)
		return True

	async def _fail(self, path, envelope, error, worker, fallback=True):
		envelope["last_error"] = error
		self._write(path, envelope)
		self._move(path, "failed")
		self.Counter.add("failed", 1)
		L.error(
			"Notification delivery stopped.",
			struct_data={"notification_id": envelope["id"], "provider": envelope["kind"], "attempts": envelope["attempts"], "worker": worker, "error": error},
		)
		if fallback:
			await self._terminal_fallback(envelope["kind"], envelope["payload"], error)

	async def _terminal_fallback(self, kind, payload, error):
		fallback = {"tenant": payload.get("tenant")}
		if kind == "email":
			fallback.update({
				"to": payload.get("to"),
				"cc": payload.get("cc"),
				"bcc": payload.get("bcc"),
				"from": payload.get("from"),
			})
		elif kind == "mattermost":
			fallback.update({
				"channel_id": payload.get("channel_id"),
				"username": payload.get("username"),
			})
		elif kind == "sms":
			fallback["to"] = payload.get("to") or payload.get("phone")
		try:
			await self.App.KafkaHandler.handle_exception(error, kind, fallback)
		except Exception:
			L.exception("Notification failure fallback could not be delivered.", struct_data={"provider": kind})

	def _delay(self, attempts):
		base = min(self.MaxDelay, self.InitialDelay * (2 ** max(0, attempts - 1)))
		return base + random.uniform(0, base * self.Jitter)

	async def _throttle(self):
		async with self.RateLock:
			now = self.App.Loop.time()
			if self.NextDelivery > now:
				await asyncio.sleep(self.NextDelivery - now)
			self.NextDelivery = self.App.Loop.time() + (1 / self.RateLimit)

	async def _prepare(self, kind, payload):
		if kind == "email":
			return await self.App.SendEmailOrchestrator.prepare_email(
				email_to=payload.get("to"), body_template=payload["body"]["template"],
				body_template_wrapper=payload["body"].get("wrapper"), body_params=payload["body"].get("params", {}),
				email_from=payload.get("from"), email_cc=payload.get("cc", []), email_bcc=payload.get("bcc", []),
				email_subject=payload.get("subject"), attachments=payload.get("attachments", []),
			)
		if kind == "slack":
			return await self.App.SendSlackOrchestrator.prepare_slack(payload)
		if kind == "mattermost":
			return await self.App.SendMattermostOrchestrator.prepare_mattermost(payload)
		if kind == "msteams":
			return await self.App.SendMSTeamsOrchestrator.prepare_msteams(payload)
		if kind == "sms":
			return await self.App.SendSMSOrchestrator.prepare_sms(payload)
		if kind == "push":
			return await self.App.SendPushOrchestrator.prepare_push(payload)
		raise ValueError("Unsupported notification kind: {}".format(kind))

	async def _dispatch(self, kind, payload):
		tenant = payload.get("tenant")
		token = None
		if tenant is not None and asab.contextvars.Tenant.get(None) is None:
			token = asab.contextvars.Tenant.set(tenant)
		try:
			if kind == "email":
				await self.App.SendEmailOrchestrator.send_prepared_email(payload, queued_delivery=True)
			elif kind == "slack":
				await self.App.SendSlackOrchestrator.send_prepared_slack(payload)
			elif kind == "mattermost":
				await self.App.SendMattermostOrchestrator.send_prepared_mattermost(payload)
			elif kind == "msteams":
				await self.App.SendMSTeamsOrchestrator.send_prepared_msteams(payload)
			elif kind == "sms":
				await self.App.SendSMSOrchestrator.send_prepared_sms(payload)
			elif kind == "push":
				await self.App.SendPushOrchestrator.send_prepared_push(payload)
			else:
				raise ValueError("Unsupported notification kind: {}".format(kind))
		finally:
			if token is not None:
				asab.contextvars.Tenant.reset(token)
