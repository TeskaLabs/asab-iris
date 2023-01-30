from ..basetestcase import TestCase

from asabiris.orchestration.sendemail import SendEmailOrchestrator
from asabiris.formatter.jinja import JinjaFormatterService
from asabiris.formatter.markdown import MarkdownFormatterService
from asabiris.formatter.pdf import PdfFormatterService


class TestSendMail(TestCase):

	def test_sendmail_01(self):
		self.App.Markdown2HTMLService = MarkdownFormatterService(self.App)
		self.App.PdfFormatterService = PdfFormatterService(self.App)
		self.App.JinjaPrintService = JinjaFormatterService(self.App)

		orch = SendEmailOrchestrator(self.App)

		self.App.Loop.run_until_complete(
			orch.send_mail(
				email_to="support@teskalabs.com",
				email_cc=["john@teskalabs.com", "bar@teskalabs.com"],
				body_template="alert.md",
				body_params={
					'message': "My message",
					'event': "My event",
				}
			)
		)

		self.assertEqual(len(self.App.EmailOutputService.Output), 1)
		output = self.App.EmailOutputService.Output[0]

		self.assertEqual(output, {
			'attachments': [],
			'body': '''<!DOCTYPE html>
				<html lang=EN><body><div><p>Ooops. Something wrong happened.</p>
				<p>My message  </p>
				<p>event:<br />
				My event</p>
				<p>Yours<br />
			LMIO  </p></div></body></html>''',
			'email_bcc': None,
			'email_cc': ['john@teskalabs.com', 'bar@teskalabs.com'],
			'email_from': None,
			'email_subject': None,
			'email_to': ['support@teskalabs.com']
		})
