import logging

import asab
import configparser
import collections
import jinja2

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


	async def format(self, template_path, template_params):
		jinja_variables = collections.ChainMap(self.Variables, template_params)

		template_io = await self.App.LibraryService.read(template_path)
		if template_io is None:
			raise KeyError("Template '{}' not found".format(template_path))

		template = jinja2.Template(template_io.read().decode('utf-8'))

		# This creates nested dictionary from keys with dot notation
		jinja_variables = create_nested_dict_from_dots_in_keys(jinja_variables)
		return template.render(**jinja_variables)


def create_nested_dict_from_dots_in_keys(data):
	"""
	This function creates a nested dictionary from a dictionary with keys containing dots.

	:param data: The input dictionary that may contain keys with dots in them, indicating nested levels
	of dictionaries
	:return: a nested dictionary where keys containing dots (".") have been split into sub-dictionaries.
	"""
	nested_dict = {}
	for key, value in data.items():
		if isinstance(value, dict):
			value = create_nested_dict_from_dots_in_keys(value)

		if '.' in key:
			parts = key.split('.')
			current_dict = nested_dict
			for part in parts[:-1]:
				current_dict.setdefault(part, {})
				current_dict = current_dict[part]

			current_dict[parts[-1]] = value
		else:
			nested_dict[key] = value
	return nested_dict
