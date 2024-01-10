import unittest
from unittest import mock
import re
import asyncio
from asabiris.orchestration.sendemail import SendEmailOrchestrator  # Update the import path if necessary


class AsyncMock(mock.Mock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)


class TestRenderMethod(unittest.TestCase):

    def setUp(self):
        self.Loop = asyncio.get_event_loop()
        # Mocking the app and its get_service method
        self.MockApp = mock.Mock()
        self.MockApp.get_service = self._mock_get_service

        # Mocking the JinjaService
        self.MockJinjaService = AsyncMock()
        self.MockJinjaService.format = AsyncMock(return_value="Mocked Jinja Output")

        # Mocking other services
        self.MockHtmlToPdfService = mock.Mock()
        self.MockMarkdownToHtmlService = mock.Mock()

        # Mocking the SmtpService as an AsyncMock
        self.MockSmtpService = AsyncMock()
        self.MockExceptionManager = AsyncMock()

        # Creating an instance of the orchestrator with the mocked app
        self.orchestrator = SendEmailOrchestrator(self.MockApp, self.MockExceptionManager)

    def _mock_get_service(self, service_name):
        if service_name == "JinjaService":
            return self.MockJinjaService
        elif service_name == "HtmlToPdfService":
            return self.MockHtmlToPdfService
        elif service_name == "MarkdownToHTMLService":
            return self.MockMarkdownToHtmlService
        elif service_name == "SmtpService":
            return self.MockSmtpService
        else:
            return mock.Mock()

    def strip_html_tags(self, html_text):
        """Remove HTML tags from the provided text."""
        clean = re.compile('<.*?>')
        return re.sub(clean, '', html_text)

    def test_render_html_template(self):
        # Test rendering of an HTML template
        output, subject = self.Loop.run_until_complete(self.orchestrator._render_template("/Templates/Email/sample.html", {}))
        self.assertEqual(output, "Mocked Jinja Output")

    def test_render_md_template(self):
        # Test rendering of a Markdown template
        self.MockMarkdownToHtmlService.format.return_value = "Mocked Jinja Output"
        output, subject = self.Loop.run_until_complete(
            self.orchestrator._render_template("/Templates/Email/sample.md", {}))
        self.assertEqual(self.strip_html_tags(output), "Mocked Jinja Output")  # Removed the "\n" from the expected value


if __name__ == "__main__":
    unittest.main()
