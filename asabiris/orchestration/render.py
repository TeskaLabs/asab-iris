import os
import logging

from ..errors import ASABIrisError, ErrorCode
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
		if not template.startswith("/Templates/General/"):
			raise ASABIrisError(
				ErrorCode.INVALID_PATH,
				tech_message="Incorrect template path '{}'. Move templates to '/Templates/General/'.".format(template),
				error_i18n_key="Incorrect template path '{{incorrect_path}}'. Please move your templates to '/Templates/General/'.",
				error_dict={
					"incorrect_path": template,
				}
			)

		html = await self.JinjaService.format(template, params)
		_, extension = os.path.splitext(template)

		if extension == '.html':
			return html

		if extension == '.md':
			html = self.MarkdownToHTMLService.format(html)
			if not html.startswith("<!DOCTYPE html>"):
				html = utils.normalize_body(html)

			return html

		raise ASABIrisError(
			ErrorCode.INVALID_FORMAT,
			tech_message="Unsupported attachment format '{}' for template '{}'".format(extension, template),
			error_i18n_key="The format '{{invalid_format}}' is not supported for attachment",
			error_dict={
				"invalid_format": extension,
			}
		)
