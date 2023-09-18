import os
import base64
import datetime
import logging
import jinja2.exceptions
import asab

from typing import List, Tuple, Optional, Dict, Union

from .. import utils
from ..exceptions import PathError, FormatError

L = logging.getLogger(__name__)


class SendEmailOrchestrator:

    def __init__(self, app) -> None:
        """Initializes the SendEmailOrchestrator with necessary services."""
        self.JinjaService = app.get_service("JinjaService")
        self.HtmlToPdfService = app.get_service("HtmlToPdfService")
        self.MarkdownToHTMLService = app.get_service("MarkdownToHTMLService")
        self.SmtpService = app.get_service("SmtpService")

    async def send_email(self, email_to: List[str], body_template: str,
                         email_from: Optional[str] = None,
                         email_cc: Optional[List[str]] = None,
                         email_bcc: Optional[List[str]] = None,
                         email_subject: Optional[str] = None,
                         body_params: Optional[Dict] = None,
                         attachments: Optional[List[Dict]] = None) -> None:
        """Sends an email with the provided details."""
        email_cc = email_cc or []
        email_bcc = email_bcc or []
        body_params = body_params or {}
        attachments = attachments or []

        body_html, email_subject_body = await self._render_template(body_template, body_params, email_to)
        email_subject = email_subject or email_subject_body

        if asab.Config.get("jinja", "failsafe"):
            attachments = []

        atts = self._process_attachments(attachments, email_to)

        await self.SmtpService.send(
            email_from=email_from,
            email_to=email_to,
            email_cc=email_cc,
            email_bcc=email_bcc,
            email_subject=email_subject,
            body=body_html,
            attachments=atts
        )

    async def _render_template(self, template: str, params: Dict, email_to: List[str]) -> Tuple[str, str]:
        """Renders the provided template with the given parameters."""
        try:
            self._validate_template_path(template)
            jinja_output = await self.JinjaService.format(template, params)
            _, extension = os.path.splitext(template)

            if extension == '.html':
                return utils.find_subject_in_html(jinja_output)
            elif extension == '.md':
                jinja_output, subject = utils.find_subject_in_md(jinja_output)
                html_output = self.MarkdownToHTMLService.format(jinja_output)
                if not html_output.startswith("<!DOCTYPE html>"):
                    html_output = utils.normalize_body(html_output)
                return html_output, subject
            else:
                raise FormatError(format=extension)
        except (jinja2.exceptions.TemplateError, Exception) as e:
            return self._handle_render_error(e, email_to)

    def _process_attachments(self, attachments: List[Dict], email_to: List[str]) -> List[Tuple[Union[str, bytes], str, str]]:
        """Processes the provided attachments and returns them in the required format."""
        atts = []

        for attachment in attachments:
            template = attachment.get('template')

            if template:
                self._validate_template_path(template)
                params = attachment.get('params', {})
                jinja_output, _ = await self._render_template(template, params, email_to)
                file_name = self._determine_file_name(attachment)
                fmt = attachment.get('format', 'html')

                if fmt == 'pdf':
                    result = self.HtmlToPdfService.format(jinja_output).read()
                    content_type = "application/pdf"
                elif fmt == 'html':
                    result = jinja_output.encode("utf-8")
                    content_type = "text/html"
                else:
                    raise FormatError(format=fmt)

                atts.append((result, content_type, file_name))
            else:
                base64_content = attachment.get('base64')
                if base64_content:
                    content_type = attachment.get('content-type', "application/octet-stream")
                    file_name = self._determine_file_name(attachment)
                    result = base64.b64decode(base64_content)
                    atts.append((result, content_type, file_name))
                else:
                    L.warning("Unknown/invalid attachment.")

        return atts

    def _determine_file_name(self, attachment: Dict) -> str:
        """Determines the file name for the attachment."""
        return attachment.get('filename') or "att-{}.{}".format(datetime.datetime.now().strftime('%Y%m%d-%H%M%S'),
                                                                attachment.get('format'))

    def _validate_template_path(self, template: str) -> None:
        """Validates the path of the provided template."""
        if not template.startswith("/Templates/Email/"):
            raise PathError(use_case='Email', invalid_path=template)

    def _handle_render_error(self, error: Exception, email_to: List[str]) -> Tuple[str, str]:
        """Handles errors that occur during template rendering."""
        L.warning("Jinja2 Rendering Error: {}".format(str(error)))

        if asab.Config.get("jinja", "failsafe"):
            current_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            email_addresses = [recipient.split('<')[1].strip('>') for recipient in email_to]
            error_details = "Timestamp: {}\nRecipients: {}\nError Message: {}\n".format(current_timestamp,
                                                                                        email_addresses,
                                                                                        str(error))
            error_message = (
                "Hello!<br><br>"
                "We encountered an issue while processing your request. "
                "Please review your input and try again.<br><br>"
                "Thank you!<br><br>Error Details:<br><pre style='font-family: monospace;'>{}</pre>"
                "<br>Best regards,<br>LogMan.io".format(error_details)
            )
            return error_message, "Error Processing Request"
