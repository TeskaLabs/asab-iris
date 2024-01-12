from asabiris.exception_strategy.exception_strategy_abc import ExceptionStrategy

import logging
import datetime

from typing import Tuple

L = logging.getLogger(__name__)


class ExceptionEmailNotifierStrategy(ExceptionStrategy):
    """
    A subclass of ExceptionStrategy designed for handling exceptions by sending email notifications.

    This class provides a concrete implementation of `handle_exception` from ExceptionStrategy,
    specifically handling exceptions by notifying relevant parties through emails using an
    EmailOutputService instance.

    Attributes:
        EmailOutputService: An instance responsible for sending email notifications.

    Methods:
        __init__: Initializes a new instance with a reference to an EmailOutputService.
        handle_exception: Overrides the abstract method to handle exceptions via email notifications.
    """

    def __init__(self, app):
        self.EmailOutputService = app.get_service("SmtpService")

    async def handle_exception(self, exception, notification_params=None):
        """
        Asynchronously handles an exception by sending an email notification.

        Overrides the abstract method from ExceptionStrategy. It sends an email using the
        EmailOutputService if 'from_email' and 'to_emails' are provided in notification_params.
        Logs an error message if the necessary parameters are missing.

        Args:
            exception (Exception): The exception to handle.
            notification_params (Optional[dict]): Parameters for the email notification,
                including 'from_email' and 'to_emails'.

        Raises:
            KeyError: If 'from_email' or 'to_emails' are missing in notification_params.
        """
        L.warning("Exception occurred: {}".format(exception))

        if notification_params:
            # Extract 'from_email' and 'to_emails' from the context
            email_from = notification_params.get('from_email')
            email_to = notification_params.get('to_emails')

        else:
            L.error("Failed to send error notification to email. Missing To/From email address or both.")
            raise KeyError("Failed to send error notification to email. Missing To/From email address or both.")

        error_message, error_subject = self._generate_error_message(str(exception))

        # Send the email
        await self.EmailOutputService.send(
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
