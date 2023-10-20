import logging

import asab
import configparser
import collections
import jinja2

from ...exceptions import PathError
from ...formater_abc import FormatterABC
from ... import utils

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
		jinja_variables = collections.ChainMap(template_params, self.Variables)
		template_io = await self.App.LibraryService.read(template_path)
		if template_io is None:
			raise PathError("Template '{}' not found".format(template_path))

		template = jinja2.Template(template_io.read().decode('utf-8'))

		# This creates nested dictionary from keys with dot notation
		template_params = utils.create_nested_dict_from_dots_in_keys(jinja_variables)
		return template.render(**template_params)
