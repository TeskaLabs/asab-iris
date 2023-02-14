import os
import logging

from .. exceptions import PathError, FormatError
from .. import utils

#

L = logging.getLogger(__name__)

#


class RenderReportOrchestrator(object):

	def __init__(self, app):
		# formatters
		self.JinjaService = app.get_service("JinjaService")
		self.MarkdownToHTMLService = app.get_service("MarkdownToHTMLService")

	async def render(self, template, params):
		"""
		This method renders templates based on the depending on the
		extension of template. Returns the html/pdf.
		"""
		# - primarily use absolute path - starts with "/"
		# - if absolute path is used, check it start with "/Templates"
		# - if it is not absolute path, it is file name - assume it's a file in Templates folder
		# templates must be stores in /Templates/General
		if not template.startswith("/Templates/General"):
			raise PathError(path=template)

		html = await self.JinjaService.format(template, params)
		_, extension = os.path.splitext(template)

		if extension == '.html':
			return html

		if extension == '.md':
			html = self.MarkdownToHTMLService.format(html)
			if not html.startswith("<!DOCTYPE html>"):
				html = utils.normalize_body(html)

			return html

		raise FormatError(format=extension)
