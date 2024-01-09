import datetime
import logging
from typing import Tuple

from asabiris.failsafe.failsafe_abc import FailsafeHandler

#

L = logging.getLogger(__name__)

#


class EmailFailsafeManager(FailsafeHandler):
    def __init__(self, app):
        self.App = app

    async def send_error_notification(self, error, notification_params):
        """
        Send an error notification email.

        Args:
            error: The exception that was raised.
            notification_params: Dictionary containing notification parameters.
        """
        # Extract 'email_from' and 'email_to' from notification parameters
        email_from = notification_params.get('from_email')
        email_to = notification_params.get('to_emails')

        # Generate error message and subject
        error_message, error_subject = self._generate_error_message(str(error))

        # Send the email
        await self.App.EmailOutputService.send(
            email_from=email_from,
            email_to=email_to,
            email_subject=error_subject,
            body=error_message
        )

    def _generate_error_message(self, specific_error: str) -> Tuple[str, str]:
        """
        Generates an error message and subject for the email.

        Args:
            specific_error: The specific error message.

        Returns:
            Tuple containing the error message and subject.
        """
        timestamp = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        error_message = (
            "<p>Hello!</p>"
            "<p>We encountered an issue while processing your request:<br><b>{}</b></p>"
            "<p>Please review your input and try again.<p>"
            "<p>Time: {} UTC</p>"
            "<p>Best regards,<br>Your Team</p>").format(specific_error, timestamp)
        return error_message, "Error when generating email"
