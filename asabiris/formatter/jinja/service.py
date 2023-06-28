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

	def create_nested_dict_from_dots_in_keys_old(self, data):
		"""
		This function creates a nested dictionary from a dictionary with keys containing dots.

		Example:
		--------
		Input:
		data = {
			"name": "Alice",
			"age": 25,
			"address.city": "London",
		}

		nested_dict = {
			"name": "Alice",
			"age": 25,
			"address": {
				"city": "London",
			},
		}

		:param data: The input dictionary that may contain keys with dots in them, indicating nested levels
		of dictionaries
		:return: A nested dictionary where keys containing dots (".") have been split into sub-dictionaries.
		"""
		nested_dict = {}
		stack = [(nested_dict, data)]

		while stack:
			current_dict, current_data = stack.pop()

			for key, value in current_data.items():
				if '.' in key:
					parts = key.split('.')
					for i, part in enumerate(parts[:-1]):
						# Check if the current part of the key exists in the current dictionary
						# If not or if the existing value is not a dictionary, create a new dictionary at that key
						if part not in current_dict or not isinstance(current_dict[part], dict):
							current_dict[part] = {}
						current_dict = current_dict[part]

					# Handle the last part of the key separately
					last_part = parts[-1]
					if last_part not in current_dict or not isinstance(current_dict[last_part], dict):
						current_dict[last_part] = {}
					current_dict = current_dict[last_part]

					# Append the current dictionary and the last part of the key with its value as a new item to the stack
					stack.append((current_dict, {last_part: value}))
				elif isinstance(value, dict):
					# If the value is a dictionary, check if the key exists in the current dictionary
					# If not or if the existing value is not a dictionary, create a new dictionary at that key
					if key not in current_dict or not isinstance(current_dict[key], dict):
						current_dict[key] = {}
					# Append the current dictionary and the value as a new item to the stack
					stack.append((current_dict[key], value))
				else:
					# If the value is not a dictionary, simply assign it to the current key in the current dictionary
					current_dict[key] = value

		return nested_dict
