import logging

import asab
import jinja2

from ...formater_abc import FormatterABC

#

L = logging.getLogger(__name__)


#


class JinjaFormatterService(asab.Service, FormatterABC):

	def __init__(self, app, service_name="JinjaService"):
		super().__init__(app, service_name)

	async def format(self, template_path, template_params):
		template_io = await self.App.LibraryService.read(template_path)
		if template_io is None:
			raise KeyError("Template '{}' not found".format(template_path))

		template = jinja2.Template(template_io.read().decode('utf-8'))

		# This creates nested dictionary from keys with dot notation
		template_params = create_nested_dict_from_dots_in_keys(template_params)
		return template.render(**template_params)


def create_nested_dict_from_dots_in_keys(data):
	"""
	This function creates a nested dictionary from a dictionary with keys containing dots.

	:param data: The input dictionary that may contain keys with dots in them, indicating nested levels
	of dictionaries
	:return: A nested dictionary where keys containing dots (".") have been split into sub-dictionaries.
	"""
	nested_dict = {}  # Initialize an empty nested dictionary
	stack = [(nested_dict, key, value) for key, value in data.items()]  # Create a stack of (dictionary, key, value) tuples

	while stack:
		current_dict, key, value = stack.pop()  # Pop the top (dictionary, key, value) tuple from the stack

		if '.' in key:  # If the key contains a dot, indicating nested levels
			parts = key.split('.')  # Split the key into parts using dot as the separator

			# Traverse the nested levels of dictionaries
			for part in parts[:-1]:
				current_dict = current_dict.setdefault(part, {})  # Create or get the nested dictionary
			current_dict[parts[-1]] = value  # Assign the value to the final nested level
		else:
			current_dict[key] = value  # If no dot in the key, assign the value directly to the current dictionary

	return nested_dict  # Return the resulting nested dictionary
