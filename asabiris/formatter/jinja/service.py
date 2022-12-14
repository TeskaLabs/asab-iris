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
		return template.render(**template_params)
