class SMTPDeliverError(Exception):
	pass


class PathError(Exception):
	"""
	Equivalent to HTTP 404 Not-Found.
	"""

	def __init__(self, message=None, *args, use_case=None, invalid_path=None):
		self.UseCase = use_case
		self.InvalidPath = invalid_path

		if message is not None:
			super().__init__(message, *args)
		elif invalid_path is not None:
			message = "The entered path '{}' is not correct. Please move your files to '/Templates/{}/'.".format(invalid_path, use_case)
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
