import os
import logging

import aiohttp.web
import aiohttp.payload_streamer

from .. import utils

#

L = logging.getLogger(__name__)

#


class RenderReportOrchestrator(object):
	def __init__(self, app):
		web_app = app.WebContainer.WebApp

		# formatters
		self.JinjaService = app.get_service("JinjaService")
		self.HtmlToPdfService = app.get_service("HtmlToPdfService")
		self.MarkdownToHTMLService = app.get_service("MarkdownToHTMLService")
		web_app.router.add_put(r"/render", self.format)

	async def format(self, request):
		"""
		This endpoint renders request body into template based on the format specified.
		Example:
		```
		localhost:8080/render?format=pdf&template=test.md

		format: pdf/html

		template : Location of template in the library (e.g. on the filesystem)
		```
		body example:
		```
		{
			"order_id":123,
			"order_creation_date":"2020-01-01 14:14:52",
			"company_name":"Test Company",
			"city":"Mumbai",
			"state":"MH"
		}
		```
		"""
		fmt = request.query.get("format")
		template = request.query.get("template", None)
		template_data = await request.json()

		# Render a body
		html = await self.render(template, template_data)
		# get pdf from html if present.
		if fmt == 'pdf':
			content_type = "application/pdf"
			pdf = self.HtmlToPdfService.format(html)
		else:
			content_type = "text/html"

		return aiohttp.web.Response(
			content_type=content_type,
			body=html if content_type == "text/html" else file_sender(pdf)
		)

	async def render(self, template, params):
		"""
		This method renders templates based on the depending on the
		extension of template. Returns the html/pdf.
		"""
		html = await self.JinjaService.format(template, params)
		_, extension = os.path.splitext(template)

		if extension == '.html':
			return html

		if extension == '.md':
			html = self.MarkdownToHTMLService.format(html)
			if not html.startswith("<!DOCTYPE html>"):
				html = utils.normalize_body(html)

			return html

		raise RuntimeError("Failed to render templates. Reason: Unknown extention '{}'".format(extension))


@aiohttp.payload_streamer.streamer
async def file_sender(writer, pdf_content):
	"""
	This function will read large file chunk by chunk and send it through HTTP
	without reading them into memory
	"""
	while True:
		chunk = pdf_content.read(2048)
		if chunk is None or len(chunk) == 0:
			break
		await writer.write(chunk)
