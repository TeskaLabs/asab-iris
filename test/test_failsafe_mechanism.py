import unittest
from unittest import mock
import re
import asyncio
import jinja2.exceptions
from asabiris.orchestration.sendemail import SendEmailOrchestrator


class AsyncMock(mock.Mock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)


class TestRenderMethod(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.get_event_loop()

        # Mocking the app and its get_service method
        self.mock_app = mock.Mock()
        self.mock_app.get_service = self._mock_get_service

        # Mocking the JinjaService
        self.mock_jinja_service = AsyncMock()
        self.mock_jinja_service.format = AsyncMock(return_value="Mocked Jinja Output")

        # Mocking other services
        self.mock_html_to_pdf_service = mock.Mock()
        self.mock_markdown_to_html_service = mock.Mock()

        # Creating an instance of the orchestrator with the mocked app
        self.orchestrator = SendEmailOrchestrator(self.mock_app)

    def _mock_get_service(self, service_name):
        if service_name == "JinjaService":
            return self.mock_jinja_service
        elif service_name == "HtmlToPdfService":
            return self.mock_html_to_pdf_service
        elif service_name == "MarkdownToHTMLService":
            return self.mock_markdown_to_html_service
        else:
            return mock.Mock()

    def strip_html_tags(self, html_text):
        """Remove HTML tags from the provided text."""
        clean = re.compile('<.*?>')
        return re.sub(clean, '', html_text)

    def test_render_html_template(self):
        # Test rendering of an HTML template
        output, subject, _ = self.loop.run_until_complete(self.orchestrator.render("/Templates/Email/sample.html", {}, ["Tester@example.com"], False))
        self.assertEqual(output, "Mocked Jinja Output")

    def test_render_jinja_exception(self):
        # Test handling of Jinja2 exceptions
        self.mock_jinja_service.format.side_effect = jinja2.exceptions.TemplateError("Mocked Jinja Error")
        output, subject, _ = self.loop.run_until_complete(self.orchestrator.render("/Templates/Email/sample.html", {}, ["Tester@example.com"], False))
        self.assertIn("Error Details:", output)

    def test_render_md_template(self):
        # Test rendering of a Markdown template
        self.mock_markdown_to_html_service.format.return_value = "Mocked Jinja Output"
        output, subject, _ = self.loop.run_until_complete(self.orchestrator.render("/Templates/Email/sample.md", {}, ["Tester@example.com"], False))
        self.assertEqual(self.strip_html_tags(output), "\nMocked Jinja Output")


if __name__ == "__main__":
    unittest.main()
