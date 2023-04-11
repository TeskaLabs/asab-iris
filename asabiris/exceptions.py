class SMTPDeliverError(Exception):
	pass

class MessageSizeError(Exception):
	pass



class PathError(Exception):
	"""

	Equivalent to HTTP 404 Not-Found.
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


class FormatError(Exception):
	"""

	Equivalent to HTTP 400 Bad-request.
	"""

	def __init__(self, message=None, *args, format=None):
		self.Format = format
		if message is not None:
			super().__init__(message, *args)
		elif format is not None:
			message = "Unsupported template format {!r}.".format(format)
			super().__init__(message, *args)
		else:
			super().__init__(message, *args)
