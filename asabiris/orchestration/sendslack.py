"""
SendSlackOrchestrator Module
-----------------------------
This module provides the SendSlackOrchestrator class to handle sending messages to Slack.
It ensures that the messages are formatted correctly and handles errors gracefully.
"""

import datetime
import logging
import mimetypes
import fastjsonschema
import os
import base64
import jinja2

from .. exceptions import PathError
from ..schemas import slack_schema

L = logging.getLogger(__name__)

TEMPLATE_PREFIX = "/Templates/Slack/"
ERROR_MESSAGE_PREFIX = "Hello!\n\nWe encountered an issue"
LOG_MSG_INIT = "Initializing SendSlackOrchestrator"

class SendSlackOrchestrator(object):
    """
    SendSlackOrchestrator handles the orchestration of sending messages to Slack.
    It validates the message format, processes the message body and attachments,
    and sends the message.
    """

    ValidationSchemaSlack = fastjsonschema.compile(slack_schema)

    def __init__(self, app):
        """
        Initialize the SendSlackOrchestrator with necessary services.

        Args:
            app: The application instance.
        """
        L.info(LOG_MSG_INIT)
        self.JinjaService = app.get_service("JinjaService")
        self.SlackOutputService = app.get_service("SlackOutputService")

    async def send_to_slack(self, msg):
        """
        Send a message to Slack.

        Args:
            msg (dict): The message to be sent.

        Returns:
            None
        """
        if not self.validate_msg_format(msg):
            error_msg = self._generate_error_message("Invalid message format.")
            await self.SlackOutputService.send(error_msg)
            return

        body, attachments = self.process_msg(msg)
        if not body:
            error_msg = self._generate_error_message("Invalid message body.")
            await self.SlackOutputService.send(error_msg)
            return

        # Send the message to Slack
        body["params"] = body.get("params", {})
        output = await self.JinjaService.format(body["template"], body["params"])
        await self.SlackOutputService.send(output, attachments)

    def validate_msg_format(self, msg):
        """
        Validate the format of the message against the Slack schema.

        Args:
            msg (dict): The message to be validated.

        Returns:
            bool: True if valid, False otherwise.
        """
        try:
            SendSlackOrchestrator.ValidationSchemaSlack(msg)
            return True
        except fastjsonschema.exceptions.JsonSchemaException:
            return False

    def process_msg(self, msg):
        """
        Process the message body and attachments.

        Args:
            msg (dict): The message to be processed.

        Returns:
            tuple: Processed body and list of attachments.
        """
        body = msg.get('body', {})
        if not body.get('template', '').startswith(TEMPLATE_PREFIX):
            return None, []

        attachments = msg.get("attachments", [])
        atts = self.process_attachments(attachments)
        if not atts:
            error_msg = self._generate_error_message("Error processing attachments.")
            self.SlackOutputService.send(error_msg)
            return body, []

        return body, atts

    def process_attachments(self, attachments):
        """
        Process the attachments in the message.

        Args:
            attachments (list): List of attachments to be processed.

        Returns:
            list: List of processed attachments.
        """
        atts = []
        for a in attachments:
            template = a.get('template', None)
            if template and template.startswith(TEMPLATE_PREFIX):
                params = a.get('params', {})
                file_name = self.get_file_name(a)
                jinja_output = self._render_template(template, params)
                if not jinja_output:
                    return []
                _, node_extension = os.path.splitext(template)
                content_type = self.get_content_type(node_extension)
                atts.append((jinja_output, content_type, file_name))
            else:
                base64cnt = a.get('base64', None)
                if base64cnt:
                    content_type = a.get('content-type', "application/octet-stream")
                    file_name = self.get_file_name(a)
                    result = base64.b64decode(base64cnt)
                    atts.append((result, content_type, file_name))
        return atts

    async def _render_template(self, template, params):
        """
        Render the template with the given parameters.

        Args:
            template (str): The template to be rendered.
            params (dict): Parameters for the template.

        Returns:
            str: Rendered template.
        """
        L.debug("Rendering template: {}".format(template))
        try:
            if not template.startswith(TEMPLATE_PREFIX):
                raise PathError(use_case='Slack', invalid_path=template)

            jinja_output = await self.JinjaService.format(template, params)
            return jinja_output
        except (PathError, jinja2.TemplateNotFound, jinja2.TemplateSyntaxError, jinja2.UndefinedError, Exception) as e:
            L.warning("Exception occurred while rendering template {}: {}".format(template, str(e)))
            error_message = self._generate_error_message(str(e))
            return error_message

    def get_file_name(self, attachment):
        """
        Get the file name from the attachment.

        Args:
            attachment (dict): The attachment.

        Returns:
            str: File name.
        """
        if attachment.get('filename') is None:
            now = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            return "att-{}.{}".format(now, attachment.get('format'))
        else:
            return attachment.get('filename')

    def get_content_type(self, file_extension):
        """
        Get the content type based on the file extension.

        Args:
            file_extension (str): File extension.

        Returns:
            str: Content type.
        """
        content_type = mimetypes.guess_type('dummy{}'.format(file_extension))[0]
        return content_type or 'application/octet-stream'

    def _generate_error_message(self, specific_error: str) -> str:
        """
        Generate an error message for Slack based on a specific error.

        Args:
            specific_error (str): The specific error message.

        Returns:
            str: The formatted error message for Slack.
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        error_message = (
            "{} while processing your request: {}\n"
            "Please review your input and try again.\n\n"
            "Timestamp: {}\n\n"
            "Best regards,\nYour Team"
        ).format(ERROR_MESSAGE_PREFIX, specific_error, timestamp)
        return error_message
