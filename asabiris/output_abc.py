import abc


class OutputABC(abc.ABC):

	def __init__(self, app):
		self.App = app

	# Lifecycle

	async def initialize(self, app):
		pass

	async def finalize(self, app):
		pass

	async def send(self, to, body_html, attachment=None, cc=None, bcc=None, subject=None):
		"""
		Reads a declaration on the given path.
		"""
		pass
