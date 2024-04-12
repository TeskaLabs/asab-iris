import io
import os
import base64
import datetime
import dataclasses

import asab

from ..errors import ASABIrisError, ErrorCode
from ..utils import normalize_body


@dataclasses.dataclass
class Attachment:
	Content: object
	ContentType: str
	FileName: str
	Position: int


class AttachmentRenderingService(asab.Service):


	def __init__(self, app, service_name="AttachmentRenderingService"):
		super().__init__(app, service_name)

		self.JinjaService = app.get_service("JinjaService")
		self.HtmlToPdfService = app.get_service("HtmlToPdfService")
		self.MarkdownToHTMLService = app.get_service("MarkdownToHTMLService")


	async def render_attachment(self, attachments, prefered_format='html'):
		'''
		This is asynchronous generator:

		Use:

		async for attachment in atts_gen:
			...

		'''

		for n, a in enumerate(attachments):

			if 'base64' in a:
				# The attachment came as Base64 content in the request
				yield Attachment(
					Content=io.BytesIO(base64.b64decode(a['base64'])),
					ContentType=a.get('content-type', "application/octet-stream"),
					FileName=self._determine_file_name(a),
					Position=n,
				)

			elif 'template' in a:
				# The attachment has to be rendered from the template
				template = a['template']
				rendered_output = await self._render_template(
					template,
					a.get('params', {})
				)

				template_ext = os.path.splitext(template)[1]

				fmt = a.get('format', prefered_format)
				if fmt == 'pdf':

					if template_ext == '.md':
						rendered_output = self.MarkdownToHTMLService.format(rendered_output)
						rendered_output = self.HtmlToPdfService.format(rendered_output)

					else:
						# Fallback
						rendered_output = self.HtmlToPdfService.format(rendered_output)

					yield Attachment(
						Content=rendered_output,
						ContentType="application/pdf",
						FileName=self._determine_file_name(a),
						Position=n,
					)

				elif fmt == 'html':
					if template_ext == '.md':
						rendered_output = self.MarkdownToHTMLService.format(rendered_output)
						rendered_output = normalize_body(rendered_output)

					yield Attachment(
						Content=io.BytesIO(rendered_output.encode('utf-8')),
						ContentType=a.get('content-type', "text/html"),
						FileName=self._determine_file_name(a),
						Position=n,
					)

				elif fmt == 'md':
					if template_ext == '.html':
						rendered_output = self.MarkdownToHTMLService.unformat(rendered_output)

					yield Attachment(
						Content=io.BytesIO(rendered_output.encode('utf-8')),
						ContentType=a.get('content-type', "text/markdown"),
						FileName=self._determine_file_name(a),
						Position=n,
					)

				else:
					raise ASABIrisError(
						ErrorCode.INVALID_FORMAT,
						tech_message="Unsupported attachment format '{}' for template '{}'".format(fmt, template),
						error_i18n_key="The format '{{invalid_format}}' is not supported for attachment. Supported formats are 'pdf', 'html', and 'md'.",
						error_dict={
							"invalid_format": fmt,
						}
					)

			else:
				raise RuntimeError("Unknown attachment in API call")


	def _determine_file_name(self, attachment) -> str:
		afname = attachment.get('filename')
		if afname is not None:
			return afname

		return "att-{}.{}".format(
			datetime.datetime.now().strftime('%Y%m%d-%H%M%S'),
			attachment['format']
		)


	async def _render_template(self, template, params):
		if not template.startswith('/Templates/Attachment/'):
			raise ASABIrisError(
				ErrorCode.INVALID_PATH,
				tech_message="Failed to render the attachment: The template path '{}' is not valid. Please ensure the template is located in the '/Templates/Attachment/' directory for proper processing.",
				error_i18n_key="Incorrect template path '{{incorrect_path}}'. Please move your templates to '/Templates/Attachment/'.",
				error_dict={
					"incorrect_path": template,
				}
			)

		return await self.JinjaService.format(template, params)
