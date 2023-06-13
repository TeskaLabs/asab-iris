class SMTPDeliverError(Exception):
	pass


class PathError(Exception):
	"""
	Equivalent to HTTP 404 Not-Found.
	"""

	def __init__(self, message=None, *args, use_case=None, invalid_path=None):
		self.use_case = use_case
		self.invalid_path = invalid_path

		if message is not None:
			super().__init__(message, *args)
		elif invalid_path is not None:
			message = "Invalid path '{}'. Expected path to start with '/Templates/{}/'.".format(invalid_path, use_case)
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
