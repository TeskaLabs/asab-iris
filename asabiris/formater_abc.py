import abc


class FormatterABC(abc.ABC):

	def __init__(self, app):
		self.App = app

	# Lifecycle

	async def initialize(self, app):
		pass

	async def finalize(self, app):
		pass

	async def format(self, content, path=None):
		"""
		Reads a declaration on the given path.
		"""
		pass
