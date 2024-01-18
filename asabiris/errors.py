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
