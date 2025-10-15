import logging
import configparser

import asab
import asab.exceptions
import datetime
import pathlib
import json
import jinja2
import urllib.parse

from ...errors import ASABIrisError, ErrorCode
from ...formater_abc import FormatterABC

#

L = logging.getLogger(__name__)


#


class JinjaFormatterService(asab.Service, FormatterABC):

	def __init__(self, app, service_name="JinjaService"):
		super().__init__(app, service_name)

		try:
			self.Variables = {option: asab.Config.get('variables', option) for option in asab.Config.options('variables')}
		except configparser.NoSectionError:
			self.Variables = {}

		self.Environment = jinja2.Environment()
		# Inject 'now' function and datetimeformat filter into the Jinja2 template's global namespace
		self.Environment.globals['now'] = self._jinja_now
		self.Environment.filters['datetimeformat'] = self.datetimeformat
		self.Environment.filters['quote_plus'] = urllib.parse.quote_plus
		self._load_variables_from_json()

	def _jinja_now(self):
		current_time = datetime.datetime.utcnow()
		return current_time

	def datetimeformat(self, value, format='%Y-%m-%d %H:%M:%S'):
		return value.strftime(format)

	def _load_variables_from_json(self):
		"""
		Load variables from a JSON file specified in the 'jinja' section of the configuration.

		This function attempts to read the path to a JSON file from the 'variables' key
		under the 'jinja' section of the configuration. If the 'jinja' section or the
		'variables' key is missing, the function returns without loading any variables.

		If the specified JSON file is found, it reads and updates the internal variables
		with the contents of the file. If the file is not found, cannot be read, or contains
		invalid JSON, a warning is logged and the function returns without updating variables.

		Overwrites any existing variables from the configuration file with the same keys.
		"""
		try:
			json_path_str = asab.Config.get('jinja', 'variables')
		except (configparser.NoSectionError, configparser.NoOptionError):
			return

		json_path = pathlib.Path(json_path_str)
		if not json_path.is_file():
			L.warning("JSON file specified '{}' in configuration does not exist.".format(json_path))
			return

		try:
			with open(json_path, 'r') as json_file:
				json_data = json.load(json_file)
		except IOError as io_err:
			L.warning("Failed to read JSON file '{}': {}".format(json_path, io_err))
			return
		except json.JSONDecodeError as json_err:
			L.warning("Invalid JSON format in file '{}': {}".format(json_path, json_err))
			return

		self.Variables.update(json_data)
		L.debug("Variables successfully loaded from JSON file '{}'.".format(json_path))

	async def format(self, template_path, template_params):
		try:
			# Load the template
			async with self.App.LibraryService.open(template_path) as b:
				if b is None:
					# Call check_disabled() only once and reuse its value
					try:
						is_disabled = self.App.LibraryService.check_disabled(template_path)
					except AttributeError:
						is_disabled = False

					if is_disabled:
						raise ASABIrisError(
							ErrorCode.TEMPLATE_IS_DISABLED,
							tech_message="Failed to render. Reason: Template {} is disabled.".format(
								template_path),
							error_i18n_key="Template '{{template_path}}' is disabled.",
							error_dict={"template_path": template_path}
						)
					else:
						raise ASABIrisError(
							ErrorCode.TEMPLATE_NOT_FOUND,
							tech_message="Failed to render. Reason: Template {} does not exist.".format(template_path),
							error_i18n_key="Template '{{incorrect_path}}' does not exist.",
							error_dict={"incorrect_path": template_path}
						)

				template_io = b.read().decode("utf-8")  # use `await b.read()` if read() is async
				template = self.Environment.from_string(template_io)

			# Prepare template variables (aka context)
			context = construct_context(dict(), self.Variables, template_params)

			# Do the rendering
			return template.render(context)

		except asab.exceptions.LibraryNotReadyError as e:
			raise ASABIrisError(
				ErrorCode.LIBRARY_NOT_READY,
				tech_message="Template rendering failed because the library is not yet ready.",
				error_i18n_key="Template rendering is currently unavailable because the library is still initializing. Please try again later.",
			) from e

		except jinja2.exceptions.UndefinedError as e:
			raise ASABIrisError(
				ErrorCode.TEMPLATE_VARIABLE_UNDEFINED,
				tech_message="'{}' is undefined in Jinja2 template '{}'.".format(str(e), template_path),
				error_i18n_key="Undefined variable: '{{variable_name}}' found in template path: '{{template_path}}'.",
				error_dict={
					"variable_name": str(e),
					"template_path": template_path
				}
			) from e

		except jinja2.TemplateSyntaxError as e:
			raise ASABIrisError(
				ErrorCode.TEMPLATE_SYNTAX_ERROR,
				tech_message="Syntax error: '{}' in Jinja2 template '{}'.".format(str(e), template_path),
				error_i18n_key="There's an error in the structure of the template '{{template_path}}': '{{syntax_error}}'. Please check the template for any incorrect or misplaced elements and correct them.",
				error_dict={
					"syntax_error": str(e),
					"template_path": template_path
				}
			) from e

		except jinja2.exceptions.TemplateError as e:
			raise ASABIrisError(
				ErrorCode.JINJA2_ERROR,
				tech_message="Jinja2 error '{}' occurred in template '{}'.".format(str(e), template_path),
				error_i18n_key="We encountered a problem '{{jinja2_error}}' located at: '{{template_path}}'.",
				error_dict={
					"jinja2_error": str(e),
					"template_path": template_path
				}
			) from e

		except ASABIrisError:
			# Pass through already raised domain errors to avoid double-wrapping
			raise

		except Exception as e:
			raise ASABIrisError(
				ErrorCode.RENDERING_ERROR,
				tech_message="Error rendering template '{}': {}".format(template_path, str(e)),
				error_i18n_key="Error occurred while rendering '{{template_path}}'. Reason: '{{error_message}}'.",
				error_dict={
					"template_path": template_path,
					"error_message": str(e)
				}
			) from e


def construct_context(context, *other_dicts):
	"""
	Merges multiple dictionaries into a single context dictionary,
	handling both case-insensitivity and nested structures.

	This function iterates over each provided dictionary in `other_dicts`
	and integrates their key-value pairs into the `context` dictionary.
	The merging process is designed to support both case-insensitive keys
	and nested structures defined using dot notation in keys.

	Parameters:
	- context (dict): The primary dictionary where all data from the other dictionaries will be merged.
		This dictionary is modified in place.
	- *other_dicts (dict): Variable number of dictionaries to be merged into the `context`.

	Functionality:
	1. Dot Notation in Keys: If a key contains a dot ('.'), it's treated as a nested structure.
		The part before the dot is used to access or create a sub-dictionary in `context`.
		The function recursively handles the nested dictionary.
	2. Nested Dictionaries: If the value for a key is itself a dictionary,
		the function again recurses into this dictionary, merging its contents appropriately.
	3. Case-Insensitive Keys: For each key, the function ensures that
		both lowercase and uppercase versions are available in the `context`,
		allowing for case-insensitive access.
	4. Handling Conflicts: If there's a conflict (different values for keys that are the same when case-normalized),
		the function will overwrite existing values in the `context`.

	Returns:
	- The function modifies the `context` dictionary in place and also returns it.

	"""

	for other_dict in other_dicts:
		for k, v in other_dict.items():
			if '.' in k:
				k1, k2 = k.split('.', 1)
				k1 = k1.lower()
				d = context.get(k1)
				if d is None:
					d = {}
					context[k1] = d
					context[k1.upper()] = d
				construct_context(d, {k2: v})

			elif isinstance(v, dict):
				d = context.get(k.lower())
				if d is None:
					d = {}
					context[k.lower()] = d
					context[k.upper()] = d
				construct_context(d, v)

			else:
				context[k.lower()] = v
				context[k.upper()] = v

	return context
