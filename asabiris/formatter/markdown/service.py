import io
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
		self.ToHTML = markdown.Markdown()
		self.ToTXT = markdown.Markdown(output_format="plain")
		self.ToTXT.stripTopLevelTags = False

	def format(self, markdown_str):
		'''
		Convert Markdown to HTML
		'''
		return self.ToHTML.convert(markdown_str)

	def unformat(self, markdown_str):
		'''
		Convert markdown string into a plain text.
		'''
		return self.ToTXT.convert(markdown_str)



def unmark_element(element, stream=None):
	'''
	See https://stackoverflow.com/a/54923798/1640284
	'''
	if stream is None:
		stream = io.StringIO()
	if element.text:
		stream.write(element.text)
	for sub in element:
		unmark_element(sub, stream)
	if element.tail:
		stream.write(element.tail)
	return stream.getvalue()


markdown.Markdown.output_formats["plain"] = unmark_element
