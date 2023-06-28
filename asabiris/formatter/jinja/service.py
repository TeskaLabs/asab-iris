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
		Create a nested dictionary from a dictionary with keys containing dots.

		This function takes an input dictionary `data` that may contain keys with dots, indicating nested levels of dictionaries.
		It splits the keys containing dots and constructs a nested dictionary structure accordingly.

		:param data: The input dictionary that may contain keys with dots in them.
		:return: A nested dictionary where keys containing dots have been split into sub-dictionaries.

		Example:
		input: {'alert.event.id': 1, 'alert2': {'event': {'id': 2}}}
		output: {'alert': {'event': {'id': 1}}, 'alert2': {'event': {'id': 2}}}
		"""
		nested_dict = {}  # Initialize the nested dictionary
		stack = [(nested_dict, data)]  # Use a stack to keep track of dictionaries and their corresponding data
		keys_to_process = list(data.keys())  # Store the keys to process separately

		while stack:
			current_dict, current_data = stack.pop()

			for key in keys_to_process:
				value = current_data[key]

				parts = key.split('.')  # Split the key by dot ('.') delimiter
				nested = current_dict

				# Traverse the nested dictionary structure and create nested dictionaries as needed
				for part in parts[:-1]:
					if part not in nested:
						nested[part] = {}
					nested = nested[part]

				nested[parts[-1]] = value  # Assign the value to the last part of the key in the nested dictionary

				if isinstance(value, dict):
					stack.append(
						(nested[parts[-1]], value))  # Add nested dictionaries to the stack for further processing

			keys_to_process.clear()  # Clear the processed keys

		return nested_dict
