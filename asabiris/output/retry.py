"""Bounded delivery retries. Only explicit temporary failures are replayed."""
import asyncio
import logging
import math
import random
import time
import uuid

import aiohttp
import asab
import asab.contextvars

from ..errors import ASABIrisError, ErrorCode


L = logging.getLogger(__name__)

asab.Config.add_defaults({
	"notification_retry": {
		"max_attempts": "3",
		"initial_delay": "1",
		"max_delay": "10",
		"max_elapsed": "180",
	}
})


class DeliveryError(ASABIrisError):
	def __init__(self, message, classification="permanent", *, code=ErrorCode.SERVER_ERROR, details=None):
		self.Classification = classification
		error_details = dict(details or {})
		error_details.setdefault("classification", classification)
		error_details.setdefault("error_code", code.name)
		super().__init__(
			code, tech_message=message, error_i18n_key="Notification delivery failed.",
			error_dict=error_details,
		)


def http_error(status, headers, *, read_only=False):
	# A gateway/server failure can occur after a write. Do not replay those writes.
	if status == 429 or (read_only and 500 <= status < 600):
		classification = "temporary"
	elif status >= 500 or status == 408:
		classification = "uncertain"
	else:
		classification = "permanent"
	code = ErrorCode.SERVER_ERROR
	if status in (401, 403):
		code = ErrorCode.AUTHENTICATION_FAILED
	elif 400 <= status < 500 and status not in (408, 429):
		code = ErrorCode.INVALID_REQUEST
	return DeliveryError(
		"Provider returned HTTP {}.".format(status), classification, code=code,
		details={"status": status, "provider_status": status},
	)


async def http_request(session, method, url, *, success=(200,), read_only=False, **kwargs):
	"""One HTTP attempt; never follow a redirect that could replay a notification."""
	async with session.request(method, url, allow_redirects=False, **kwargs) as response:
		body = await response.text()
		if response.status not in success:
			error = http_error(response.status, response.headers, read_only=read_only)
			error.ErrorDict["provider_response"] = body
			raise error
		return body


class RetryPolicy:
	"""One notification's elapsed budget, with a bounded attempt count per step."""
	def __init__(self, provider, *, tenant=None):
		self.Provider = provider
		self.NotificationId = uuid.uuid4().hex
		self.Tenant = tenant if tenant is not None else asab.contextvars.Tenant.get(None)
		self.MaxAttempts = asab.Config.getint("notification_retry", "max_attempts")
		self.InitialDelay = asab.Config.getfloat("notification_retry", "initial_delay")
		self.MaxDelay = asab.Config.getfloat("notification_retry", "max_delay")
		self.MaxElapsed = asab.Config.getfloat("notification_retry", "max_elapsed")
		if self.MaxAttempts < 1 or not all(math.isfinite(x) and x > 0 for x in (self.InitialDelay, self.MaxDelay, self.MaxElapsed)):
			raise ASABIrisError(ErrorCode.INVALID_SERVICE_CONFIGURATION, tech_message="Invalid [notification_retry] limits.")
		self.Deadline = time.monotonic() + self.MaxElapsed

	async def run(self, operation, *, step="send"):
		delay = min(self.InitialDelay, self.MaxDelay)
		for attempt in range(1, self.MaxAttempts + 1):
			remaining = self.Deadline - time.monotonic()
			if remaining <= 0:
				error = DeliveryError("Notification elapsed-time budget exhausted.", details={"outcome": "exhausted"})
				self._record(error, attempt - 1, step, "exhausted")
				raise error
			try:
				result = await asyncio.wait_for(operation(), timeout=remaining)
			except DeliveryError as exc:
				error = exc
			except (aiohttp.ClientSSLError, aiohttp.InvalidURL) as exc:
				error = DeliveryError("Invalid provider URL or TLS configuration.")
				error.__cause__ = exc
			except aiohttp.ClientConnectorError as exc:
				error = DeliveryError("Could not connect to provider before submission.", "temporary")
				error.__cause__ = exc
			except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
				error = DeliveryError("Provider response lost or timed out; delivery is uncertain.", "uncertain")
				error.__cause__ = exc
			else:
				L.info("Notification step accepted.", struct_data=self._context(attempt, step, "accepted"))
				return result

			wait = random.uniform(delay / 2, delay)
			if error.Classification != "temporary":
				outcome = error.Classification
			elif attempt == self.MaxAttempts or time.monotonic() + wait >= self.Deadline:
				outcome = "exhausted"
			else:
				outcome = "retrying"
			self._record(error, attempt, step, outcome, wait)
			if outcome != "retrying":
				raise error
			await asyncio.sleep(wait)
			delay = min(delay * 2, self.MaxDelay)

	def _context(self, attempt, step, outcome):
		return {
			"notification_id": self.NotificationId, "tenant": self.Tenant, "provider": self.Provider,
			"attempt": attempt, "step": step, "outcome": outcome,
		}

	def _record(self, error, attempt, step, outcome, delay=None):
		error.ErrorDict.update(self._context(attempt, step, outcome))
		if error.__cause__ is not None:
			error.ErrorDict.setdefault("cause_type", type(error.__cause__).__name__)
		L.warning("Notification delivery step failed.", struct_data=dict(error.ErrorDict, delay=delay))
