from asabiris.exception_manager_abc import ExceptionManager


class APIExceptionManager(ExceptionManager):

	def __init__(self, app):
		self.App = app

	async def handle_exception(self, exception, _):
		raise exception
