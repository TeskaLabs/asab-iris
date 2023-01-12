import os
import logging

from .. import utils

#

L = logging.getLogger(__name__)

#


class RenderReportOrchestrator(object):

	def __init__(self, app):
		# formatters
		self.JinjaService = app.get_service("JinjaService")
		self.HtmlToPdfService = app.get_service("HtmlToPdfService")
		self.MarkdownToHTMLService = app.get_service("MarkdownToHTMLService")
		self.TempPath = "/Templates/render"

	async def render(self, template, params):
		"""
		This method renders templates based on the depending on the
		extension of template. Returns the html/pdf.
		"""
		assert template == '/'
		template_path = self.TempPath + template
		html = await self.JinjaService.format(template_path, params)
		_, extension = os.path.splitext(template)

		if extension == '.html':
			return html

		if extension == '.md':
			html = self.MarkdownToHTMLService.format(html)
			if not html.startswith("<!DOCTYPE html>"):
				html = utils.normalize_body(html)

			return html

		raise RuntimeError("Failed to render templates. Reason: Unknown extention '{}'".format(extension))
