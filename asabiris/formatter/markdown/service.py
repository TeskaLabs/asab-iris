import logging

import asab
import markdown

from ...formater_abc import FormatterABC

#

L = logging.getLogger(__name__)

#


class MarkdownFormatterService(asab.Service, FormatterABC):


	def __init__(self, app, service_name="MarkdownToHTMLService"):
		super().__init__(app, service_name)

	def format(self, markdown_str):
		md_to_html = markdown.markdown(markdown_str)
		return md_to_html
