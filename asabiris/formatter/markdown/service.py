import logging
import markdown
import asab
import io

from ...formater_abc import FormatterABC

L = logging.getLogger(__name__)


class MarkdownFormatterService(asab.Service, FormatterABC):
	"""
	Service to convert Markdown text to HTML or plain text. Extends
	asab.Service and implements FormatterABC.
	"""

	def __init__(self, app, service_name="MarkdownToHTMLService"):
		"""
		Initialize the service with the ability to convert Markdown to
		HTML or plain text.

		:param app: The application instance.
		:param service_name: The name of the service.
		"""
		super().__init__(app, service_name)
		self.ToHTML = markdown.Markdown()
		self.ToTXT = markdown.Markdown(output_format="plain")
		self.ToTXT.stripTopLevelTags = False

	def format(self, markdown_str):
		"""
		Convert Markdown to HTML.

		:param markdown_str: Markdown string to convert.
		:return: Converted HTML string.
		"""
		return self.ToHTML.convert(markdown_str)

	def wrap_html_content(self, content, header='', footer=''):
		"""
		Wrap HTML content in a basic HTML structure.

		:param content: HTML content to wrap.
		:param header: Optional HTML header content.
		:param footer: Optional HTML footer content.
		:return: Wrapped HTML content.
		"""
		html_template = """
		<html>
			<head>
				{header}
			</head>
			<body>
				{content}
				<footer>{footer}</footer>
			</body>
		</html>
		"""
		return html_template.format(content=content, header=header, footer=footer)

	def format_and_wrap(self, markdown_str, header='', footer=''):
		"""
		Convert Markdown to HTML and wrap it in a basic HTML structure.

		:param markdown_str: Markdown string to convert and wrap.
		:param header: Optional HTML header content.
		:param footer: Optional HTML footer content.
		:return: Wrapped HTML content.
		"""
		html_content = self.format(markdown_str)
		return self.wrap_html_content(html_content, header=header, footer=footer)


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
