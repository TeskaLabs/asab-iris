import os
import base64
import datetime
import logging
import jinja2.exceptions
import asab

from typing import List, Tuple, Dict, Union
from .. import utils
from ..exceptions import PathError, FormatError

L = logging.getLogger(__name__)


class SendEmailOrchestrator:

    def __init__(self, app):
        self.services = {
            name: app.get_service(name) for name in [
                "JinjaService", "HtmlToPdfService", "MarkdownToHTMLService", "SmtpService"
            ]
        }

    async def send_email(self, email_to: List[str], body_template: str, **kwargs):
        body_html, email_subject_body = await self._render_template(body_template, kwargs.get('body_params', {}), email_to)
        atts = self._process_attachments(kwargs.get('attachments', []), email_to) if not asab.Config.get("jinja", "failsafe") else []
        await self.services['SmtpService'].send(
            email_from=kwargs.get('email_from'),
            email_to=email_to,
            email_cc=kwargs.get('email_cc', []),
            email_bcc=kwargs.get('email_bcc', []),
            email_subject=kwargs.get('email_subject', email_subject_body),
            body=body_html,
            attachments=atts
        )

    async def _render_template(self, template: str, params: Dict, email_to: List[str]) -> Tuple[str, str]:
        try:
            if not template.startswith("/Templates/Email/"):
                raise PathError(use_case='Email', invalid_path=template)
            jinja_output = await self.services['JinjaService'].format(template, params)
            ext = os.path.splitext(template)[1]
            if ext not in ['.html', '.md']:
                raise FormatError(format=ext)
            return {
                '.html': utils.find_subject_in_html,
                '.md': lambda x: (self.services['MarkdownToHTMLService'].format(utils.find_subject_in_md(x)[0]), utils.find_subject_in_md(x)[1])
            }[ext](jinja_output)
        except (jinja2.exceptions.TemplateError, Exception) as e:
            if asab.Config.get("jinja", "failsafe"):
                error_message = (
                    "Hello!<br><br>"
                    "We encountered an issue while processing your request. "
                    "Please review your input and try again.<br><br>"
                    "Thank you!<br><br>Error Details:<br><pre style='font-family: monospace;'>Timestamp: {}\nRecipients: {}\nError Message: {}\n</pre>"
                    "<br>Best regards,<br>LogMan.io".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ', '.join(email_to), str(e))
                )
                return error_message, "Error Processing Request"
            raise

    def _process_attachments(self, attachments: List[Dict], email_to: List[str]) -> List[Tuple[Union[str, bytes], str, str]]:
        processed_attachments = []
        for a in attachments:
            if 'base64' in a:
                processed_attachments.append((base64.b64decode(a['base64']), a.get('content-type', "application/octet-stream"), self._determine_file_name(a)))
            elif 'template' in a:
                jinja_output, _ = self._render_template(a['template'], a.get('params', {}), email_to)
                fmt = a.get('format', 'html')
                if fmt == 'pdf':
                    result = self.services['HtmlToPdfService'].format(jinja_output).read()
                    content_type = "application/pdf"
                elif fmt == 'html':
                    result = jinja_output.encode("utf-8")
                    content_type = "text/html"
                else:
                    raise FormatError(format=fmt)
                processed_attachments.append((result, content_type, self._determine_file_name(a)))
            else:
                L.warning("Unknown/invalid attachment.")
        return processed_attachments

    def _determine_file_name(self, a: Dict) -> str:
        return a.get('filename', "att-{}.{}".format(datetime.datetime.now().strftime('%Y%m%d-%H%M%S'), a.get('format')))
