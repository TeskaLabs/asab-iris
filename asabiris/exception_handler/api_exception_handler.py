from .exception_handler import ExceptionHandlingStrategy


class APIExceptionHandlingStrategy(ExceptionHandlingStrategy):

	def __init__(self, app):
		self.App = app

	async def handle_exception(self, exception, _):
		raise exception
