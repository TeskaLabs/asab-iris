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
		Adds a prefix to an error name, e.g. bs-query|SCHEMAS_DONT_MATCH (internationalization)
		"""
		return 'asab-iris|{}'.format(self.name)

	INVALID_FORMAT = 1001
	INVALID_PATH = 1002
	TEMPLATE_VARIABLE_UNDEFINED = 1003
	MISSING_HEADER_LIST = 1002
	EMAIL_NOT_SENT = 1003
	EMAIL_SERVICE_NOT_AVAILABLE = 1004
	JUPYTER_NOT_AVAILABLE = 1006
	FILE_SIZE_LIMIT = 1007
	INVALID_TIMEZONE_FORMAT = 1008
	MISSING_SCHEMA = 1011
	INCORRECT_EXPORT_ID = 1012
	UNFINISHED_EXPORT = 1013
	INVALID_LINK = 1014
	SCHEMAS_DONT_MATCH = 1015
	INCORRECT_OUTPUT = 1016
	INVALID_YAML_FORMAT = 1017
	FAILED_READ_FROM_LIBRARY = 1018
	INVALID_DATASOURCE_DEFINITION = 1019
	INVALID_DATASOURCE_TYPE = 1020
