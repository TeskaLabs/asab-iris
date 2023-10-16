"""
Module to orchestrate the sending of emails.

This module provides functionality to orchestrate the sending of emails,
including rendering email templates, processing attachments, and sending
emails through an SMTP service.

Classes:
    SendEmailOrchestrator: Orchestrates the sending of emails.
"""

import os
import base64
import datetime
import logging
import jinja2.exceptions
from typing import List, Tuple, Dict, Union
from .. import utils
from ..exceptions import PathError, FormatError

L = logging.getLogger(__name__)

# Constants for easier management and clarity
TEMPLATE_PREFIX = "/Templates/Email/"
ERROR_MESSAGE_PREFIX = "Hello!<br><br>We encountered an issue"
LOG_MSG_INIT = "Initializing SendEmailOrchestrator"


class SendEmailOrchestrator:
    """
    A class to orchestrate the sending of emails.

    This class handles rendering email templates, processing attachments, and
    sending emails through an SMTP service.

    Attributes:
        ValidExtensions (set): A set of valid file extensions for templates.
        Services (dict): A dictionary of services used for email processing.

    Methods:
        send_email(...): Send an email using specified parameters.
        _render_template(...): Render the specified email template.
        _process_template_output(...): Process the output from a rendered template.
        _process_attachments(...): Process email attachments.
        _determine_file_name(...): Determine the file name for an attachment.
        _generate_error_message(...): Generate an error message for email sending.
    """

    ValidExtensions = {'.html', '.md'}

    def __init__(self, app):
        """
        Initialize the SendEmailOrchestrator with necessary services.

        Args:
            app: The application object, used to get services.
        """
        self.Services = {
            name: app.get_service(name) for name in [
                "JinjaService", "HtmlToPdfService", "MarkdownToHTMLService",
                "SmtpService"
            ]
        }
        L.info(LOG_MSG_INIT, {"services": list(self.Services.keys())})

    async def send_email(
            self, email_to: List[str], body_template: str,
            email_from=None, email_cc=None, email_bcc=None,
            email_subject=None, body_params=None, attachments=None
    ):
        """
        Send an email using specified parameters.
        ...
        """
        L.debug("Attempting to send email to: {}".format(', '.join(email_to)))
        body_params = body_params or {}
        attachments = attachments or []
        email_cc = email_cc or []
        email_bcc = email_bcc or []

        # Rendering the template
        body_html, email_subject_body = await self._render_template(
            body_template, body_params)

        # If an error occurs during rendering, set the body and subject to the error message and subject
        if body_html.startswith(ERROR_MESSAGE_PREFIX):
            L.warning("Error encountered in {}. Clearing attachments.".format(body_template))
            atts = []
            email_subject = email_subject_body
        else:
            # If email_subject is not provided or is empty, and no error occurred during rendering, use email_subject_body
            if email_subject is None or email_subject == '':
                email_subject = email_subject_body

            # Processing attachments
            atts, att_error_message, att_error_subject = await self._process_attachments(attachments)

            # If an error occurs during attachment processing, set the body and subject to the error message and subject
            if att_error_message and att_error_subject:
                body_html, email_subject = att_error_message, att_error_subject
                atts = []
            # Note: Removed the redundant else block

        # Sending the email
        await self.Services['SmtpService'].send(
            email_from=email_from,
            email_to=email_to,
            email_cc=email_cc,
            email_bcc=email_bcc,
            email_subject=email_subject,
            body=body_html,
            attachments=atts
        )
        L.info("Email sent successfully to: {}".format(', '.join(email_to)))

    async def _render_template(self, template: str, params: Dict) -> Tuple[str, str]:
        L.debug("Rendering template: {}".format(template))
        try:
            if not template.startswith(TEMPLATE_PREFIX):
                raise PathError(use_case='Email', invalid_path=template)

            jinja_output = await self.Services['JinjaService'].format(template, params)
            return self._process_template_output(jinja_output, os.path.splitext(template)[1])
        except (PathError, jinja2.TemplateNotFound, jinja2.TemplateSyntaxError, jinja2.UndefinedError, Exception) as e:
            L.exception("Exception occurred while rendering template {}: {}".format(template, str(e)))
            error_message, error_subject = self._generate_error_message(str(e))
            return error_message, error_subject

    def _process_template_output(self, output: str, ext: str) -> Tuple[str, str]:
        if ext not in self.ValidExtensions:
            raise FormatError(format=ext)

        processors = {
            '.html': utils.find_subject_in_html,
            '.md': lambda x: (
                self.Services['MarkdownToHTMLService'].format(utils.find_subject_in_md(x)[0]),
                utils.find_subject_in_md(x)[1]
            )
        }
        return processors[ext](output)

    async def _process_attachments(
            self, attachments: List[Dict]) -> Tuple[
        List[Tuple[Union[str, bytes], str, str]], str, str]:
        L.debug("Processing {} attachments".format(len(attachments)))
        processed_attachments = []
        error_message = error_subject = None

        for a in attachments:
            try:
                if 'base64' in a:
                    processed_attachments.append(
                        (
                            base64.b64decode(a['base64']),
                            a.get('content-type', "application/octet-stream"),
                            self._determine_file_name(a)
                        )
                    )
                elif 'template' in a:
                    rendered_output, rendered_subject = await self._render_template(a['template'], a.get('params', {}))

                    if rendered_output.startswith(ERROR_MESSAGE_PREFIX):
                        error_message, error_subject = rendered_output, rendered_subject
                        break

                    fmt = a.get('format', 'html')
                    if fmt == 'pdf':
                        result = self.Services['HtmlToPdfService'].format(rendered_output).read()
                        content_type = "application/pdf"
                    elif fmt == 'html':
                        result = rendered_output.encode("utf-8")
                        content_type = "text/html"
                    else:
                        raise FormatError(format=fmt)
                    processed_attachments.append((result, content_type, self._determine_file_name(a)))

            except Exception as e:
                error_message, error_subject = self._generate_error_message(str(e))
                break

        return processed_attachments, error_message, error_subject

    def _determine_file_name(self, a: Dict) -> str:
        return a.get('filename', "att-{}.{}".format(datetime.datetime.now().strftime('%Y%m%d-%H%M%S'), a.get('format')))

    def _generate_error_message(self, specific_error: str) -> Tuple[str, str]:
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        except Exception as date_err:
            L.exception("Error generating timestamp: {}".format(date_err))
            timestamp = "Unknown"

        try:
            error_message = (
                "Hello!<br><br>"
                "We encountered an issue while processing your request: <b>{}</b><br>"
                "Please review your input and try again.<br><br>"
                "Thank you!<br><br>Error Details:<br><pre style='font-family: monospace;'>"
                "Timestamp: {}\n</pre>"
                "<br>Best regards,<br>Your Team"
            ).format(specific_error, timestamp)
        except Exception as format_err:
            L.exception("Error formatting the error message: {}".format(format_err))
            error_message = (
                "Hello!<br><br>"
                "We encountered an issue while processing your request. "
                "Please review your input and try again.<br><br>"
                "Thank you!<br><br>"
                "<br>Best regards,<br>Your Team"
            )

        return error_message, "Error Processing Request"
