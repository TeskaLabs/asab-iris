import enum


class ASABIrisError(Exception):

	def __init__(self, error_code, error_dict=None, tech_message=None, error_i18n_key=None):
		super().__init__()
		self.ErrorCode = error_code
		self.ErrorDict = error_dict
		self.TechMessage = tech_message
		# Adds a prefix to an error key (internationalization)
		if error_i18n_key is not None:
			self.Errori18nKey = "IrisError|" + error_i18n_key
		else:
			self.Errori18nKey = "IrisError|"


class ErrorCode(enum.Enum):

	def get_i18n_name(self):
		"""
		Adds a prefix to an error name.
		"""
		return 'asab-iris|{}'.format(self.name)

	INVALID_FORMAT = 1001
	INVALID_PATH = 1002
	TEMPLATE_VARIABLE_UNDEFINED = 1003
	TEMPLATE_NOT_FOUND = 1004
	TEMPLATE_SYNTAX_ERROR = 1005
	JINJA2_ERROR = 1006
	SERVER_ERROR = 1007
	INVALID_SERVICE_CONFIGURATION = 1008
	RENDERING_ERROR = 1009
	SLACK_API_ERROR = 1010
	SMTP_CONNECTION_ERROR = 1011
	SMTP_AUTHENTICATION_ERROR = 1012
	SMTP_RESPONSE_ERROR = 1013
	SMTP_SERVER_DISCONNECTED = 1014
	SMTP_GENERIC_ERROR = 1015
	GENERAL_ERROR = 1016
	SMTP_TIMEOUT = 1017
	LIBRARY_NOT_READY = 1018
	TEMPLATE_IS_DISABLED = 1019
	SLACK_CHANNEL_NOT_FOUND = 1020
	AUTHENTICATION_FAILED = 1021
	INVALID_REQUEST = 1022
