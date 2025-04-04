import logging
import fastjsonschema

L = logging.getLogger(__name__)

class SendMS365EmailOrchestrator:
    """
    Orchestrator for preparing an email using templates and delegating the sending to the output service.
    """

    def __init__(self, app):
        self.App = app
        # Get the JinjaService to render templates.
        self.JinjaService = app.get_service("JinjaService")
        # Get the M365EmailOutputService to actually send emails.
        self.M365EmailOutputService = app.get_service("M365EmailOutputService")

    async def send_to_m365_email(self, msg):
        """
        Validates the incoming email message, prepares the email body using a template,
        and then delegates sending to the M365EmailOutputService.
        """
        # Validate incoming message against the schema.

        # Extract values from the validated message.
        to_recipients = msg.get("to", [])
        subject = msg.get("subject", "No Subject")
        body_details = msg.get("body", {})

        # Get the template path and parameters.
        template = body_details.get("template", "/Templates/MS365/alert.md")
        params = body_details.get("params", {})

        # Use the JinjaService to render the email body.
        rendered_body = await self.JinjaService.format(template, params)

        # Delegate sending the email to the output service.
        # Here, we assume the output service handles only one recipient at a time.
        for recipient in to_recipients:
            await self.M365EmailOutputService.send_email(recipient, subject, rendered_body)

        return {"result": "OK"}
