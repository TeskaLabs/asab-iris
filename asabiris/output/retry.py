"""Temporary-delivery classification shared by notification providers."""

import contextvars
import logging

import asab

from ..errors import ASABIrisError, ErrorCode


L = logging.getLogger(__name__)

# Scoped to one provider attempt, including SDK calls executed through asyncio.to_thread.
DeliveryLogContext = contextvars.ContextVar("IrisDeliveryLogContext", default=None)


def log_provider_response(status, provider_error_code=None):
	context = DeliveryLogContext.get()
	if context is None:
		return
	data = {**context, "status": status}
	if provider_error_code is not None:
		data["provider_error_code"] = provider_error_code
	L.log(asab.LOG_NOTICE, "Notification provider responded.", struct_data=data)


class TemporaryDeliveryError(ASABIrisError):
	"""A provider operation that is safe to retry from the durable queue."""

	def __init__(self, error=None, result=None):
		message = str(error) if error is not None else "Temporary provider response: {!r}".format(result)
		super().__init__(
			ErrorCode.SERVER_ERROR,
			tech_message=message,
			error_i18n_key="Notification delivery temporarily unavailable.",
			error_dict={"error_message": message},
		)
		self.OriginalError = error
		self.Result = result


async def retry(operation, is_temporary):
	"""Make one attempt and classify its outcome; the disk spool owns retry scheduling."""
	try:
		result = await operation()
	except Exception as error:
		if is_temporary(None, error):
			raise TemporaryDeliveryError(error=error) from error
		raise

	if is_temporary(result, None):
		raise TemporaryDeliveryError(result=result)
	return result
