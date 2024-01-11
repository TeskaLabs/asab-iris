import logging

from asabiris.exception_manager.exception_manager_abc import ExceptionManager
#

L = logging.getLogger(__name__)

#


class APIExceptionManager(ExceptionManager):

	def __init__(self, app):
		self.App = app

	async def handle_exception(self, exception, notification_params=None):
		"""
		Asynchronously handles an exception specific to the API context.

		This method provides a concrete implementation of the abstract method from the
		ExceptionManager class. It is designed to handle exceptions that occur in an
		API environment. Currently, it simply raises the caught exception.
		Args:
			exception (Exception): The exception that needs to be handled.
			notification_params (Optional[dict]): Additional parameters for notification purposes,
				such as user details, context of the exception, etc. Defaults to None.

		Raises:
			exception: Re-raises the caught exception.
		"""
		L.warning("Exception occurred: {}".format(exception))
		raise exception
