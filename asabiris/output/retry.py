"""Temporary-delivery classification shared by notification providers."""

from ..errors import ASABIrisError, ErrorCode


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
	try:
		result = await operation()
	except Exception as error:
		if is_temporary(None, error):
			raise TemporaryDeliveryError(error=error) from error
		raise

	if is_temporary(result, None):
		raise TemporaryDeliveryError(result=result)
	return result
