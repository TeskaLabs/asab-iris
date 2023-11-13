import logging
import configparser

import asab
import jinja2

from ...exceptions import PathError
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


	async def format(self, template_path, template_params):

		# Load the template
		template_io = await self.App.LibraryService.read(template_path)
		if template_io is None:
			raise PathError("Template '{}' not found".format(template_path))
		template = self.Environment.from_string(template_io.read().decode('utf-8'))

		# Prepare template variables (aka context)
		context = construct_context(dict(), self.Variables, template_params)

		# Do the rendering
		return template.render(context)


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
