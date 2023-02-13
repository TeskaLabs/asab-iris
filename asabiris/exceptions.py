class SMTPDeliverError(Exception):
	pass


class InvalidPathError(Exception):
	"""

	Equivalent to HTTP 404 Forbidden.
	"""

	def __init__(self, message=None, *args, path=None):
		self.Path = path
		if message is not None:
			super().__init__(message, *args)
		elif path is not None:
			message = "Invalid path {!r}.".format(path)
			super().__init__(message, *args)
		else:
			super().__init__(message, *args)
