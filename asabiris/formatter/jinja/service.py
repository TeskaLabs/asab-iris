import logging
import asab
import configparser
import collections
import jinja2
import json
import os

from ...exceptions import PathError
from ...formater_abc import FormatterABC
from ... import utils

L = logging.getLogger(__name__)


class JinjaFormatterService(asab.Service, FormatterABC):
	"""
	JinjaFormatterService is responsible for formatting templates using Jinja2.
	It loads variables from the configuration and optionally from a JSON file.
	"""

	def __init__(self, app, service_name="JinjaService"):
		"""
		Initialize the JinjaFormatterService.

		:param app: The application instance.
		:param service_name: The name of the service.
		"""
		super().__init__(app, service_name)

		# Load variables from the configuration section named 'variables'
		try:
			self.Variables = {option: asab.Config.get('variables', option) for option in
							  asab.Config.options('variables')}
		except configparser.NoSectionError:
			self.Variables = {}

		# Load variables from JSON file if specified in the configuration
		json_path = asab.Config.get('jinja', 'variables', fallback=None)
		if json_path and os.path.exists(json_path):
			with open(json_path, 'r') as json_file:
				self.Variables.update(json.load(json_file))

	def __getitem__(self, key):
		"""
		Retrieve the value of a variable using the square bracket notation.

		:param key: The name of the variable.
		:return: The value of the variable or None if not found.
		"""
		return self.Variables.get(key, None)

	async def format(self, template_path, template_params):
		"""
		Format a given template using Jinja2.

		:param template_path: The path to the Jinja2 template.
		:param template_params: The parameters to be used in the template.
		:return: The formatted template.
		"""
		# Combine the provided template_params with the loaded Variables
		jinja_variables = collections.ChainMap(template_params, self.Variables)

		# Read the template from the specified template_path
		template_io = await self.App.LibraryService.read(template_path)
		if template_io is None:
			raise PathError("Template '{}' not found".format(template_path))

		# Create a Jinja2 template from the read content
		template = jinja2.Template(template_io.read().decode('utf-8'))

		# Convert keys with dot notation into nested dictionaries
		template_params = utils.create_nested_dict_from_dots_in_keys(jinja_variables)

		# Render the template with the combined variables
		return template.render(**template_params)
