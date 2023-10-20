import unittest
from unittest import mock
import re
import asyncio
import jinja2.exceptions
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

        # Creating an instance of the orchestrator with the mocked app
        self.orchestrator = SendEmailOrchestrator(self.MockApp)

    def _mock_get_service(self, service_name):
        if service_name == "JinjaService":
            return self.MockJinjaService
        elif service_name == "HtmlToPdfService":
            return self.MockHtmlToPdfService
        elif service_name == "MarkdownToHTMLService":
            return self.MockMarkdownToHtmlService
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

    def test_render_jinja_exception(self):
        # Test handling of Jinja2 exceptions
        self.MockJinjaService.format.side_effect = jinja2.exceptions.TemplateError("Mocked Jinja Error")
        output, subject = self.Loop.run_until_complete(self.orchestrator._render_template("/Templates/Email/sample.html", {}))
        self.assertIn("We encountered an issue", output)


    def test_render_md_template(self):
        # Test rendering of a Markdown template
        self.MockMarkdownToHtmlService.format.return_value = "Mocked Jinja Output"
        output, subject = self.Loop.run_until_complete(
            self.orchestrator._render_template("/Templates/Email/sample.md", {}))
        self.assertEqual(self.strip_html_tags(output), "Mocked Jinja Output")  # Removed the "\n" from the expected value

    def test_jinja_template_not_found(self):
        self.MockJinjaService.format.side_effect = jinja2.TemplateNotFound
        error_message, _ = self.Loop.run_until_complete(self.orchestrator._render_template("/Templates/Email/sample.html", {}))
        self.assertIn("We encountered an issue", error_message)

    def test_jinja_template_syntax_error(self):
        self.MockJinjaService.format.side_effect = jinja2.TemplateSyntaxError
        error_message, _ = self.Loop.run_until_complete(self.orchestrator._render_template("/Templates/Email/sample.html", {}))
        self.assertIn("We encountered an issue", error_message)

    def test_jinja_undefined_error(self):
        self.MockJinjaService.format.side_effect = jinja2.UndefinedError
        error_message, _ = self.Loop.run_until_complete(self.orchestrator._render_template("/Templates/Email/sample.html", {}))
        self.assertIn("We encountered an issue", error_message)

    def test_general_exception(self):
        self.MockJinjaService.format.side_effect = Exception("General Exception")
        error_message, _ = self.Loop.run_until_complete(self.orchestrator._render_template("/Templates/Email/sample.html", {}))
        self.assertIn("We encountered an issue", error_message)


if __name__ == "__main__":
    unittest.main()
