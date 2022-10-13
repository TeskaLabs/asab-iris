import logging
import tempfile
import asab
import xhtml2pdf.pisa

from asabiris.formater_abc import FormatterABC


#

L = logging.getLogger(__name__)

#


class PdfFormatterService(asab.Service, FormatterABC):


	def __init__(self, app, service_name="HtmlToPdfService"):
		super().__init__(app, service_name)


	def format(self, html_content):
		# obtain temporary file
		pdf_content = tempfile.TemporaryFile()
		# convert HTML to PDF
		xhtml2pdf.pisa.CreatePDF(
			src=html_content,  # the HTML to convert
			dest=pdf_content)  # file handle to receive result
		pdf_content.seek(0)

		return pdf_content
