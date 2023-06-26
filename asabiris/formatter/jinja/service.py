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
		template_params = self.create_nested_dict_from_dots_in_keys(template_params)
		return template.render(**template_params)

	def create_nested_dict_from_dots_in_keys(self, data):
		"""
		This function creates a nested dictionary from a dictionary with keys containing dots.

		:param data: The input dictionary that may contain keys with dots in them, indicating nested levels
		of dictionaries
		:return: A nested dictionary where keys containing dots (".") have been split into sub-dictionaries.
		"""
		nested_dict = {}  # Create an empty nested dictionary
		stack = [(nested_dict, data)]  # Initialize a stack with the root dictionary and the input data

		while stack:
			current_dict, current_data = stack.pop()  # Get the current dictionary and data from the stack

			for key, value in current_data.items():
				if isinstance(value, dict):
					current_dict[key] = {}  # Create a new empty sub-dictionary
					stack.append(
						(current_dict[key], value))  # Push the sub-dictionary and its corresponding data to the stack
				elif '.' in key:
					parts = key.split('.')
					temp_dict = current_dict
					for part in parts[:-1]:
						if part not in temp_dict:
							temp_dict[part] = {}  # Create a new empty sub-dictionary
						temp_dict = temp_dict[part]  # Move to the next level of nesting
					temp_dict[parts[-1]] = value  # Assign the value to the final key in the nested structure
				else:
					current_dict[key] = value  # Assign the value directly to the current dictionary

		return nested_dict
