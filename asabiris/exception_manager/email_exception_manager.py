from asabiris.exception_manager.exception_manager_abc import ExceptionManager

import logging
import datetime

from typing import Tuple

L = logging.getLogger(__name__)


class EmailExceptionManager(ExceptionManager):
    """
    A subclass of ExceptionManager designed for handling exceptions by sending email notifications.

    This class implements the abstract methods of ExceptionManager, providing a specific strategy
    for dealing with exceptions by notifying relevant parties through email. It utilizes an
    email failsafe manager to send these notifications.

    Attributes:
        EmailFailsafeManager: An instance of a manager class responsible for sending email notifications.

    Methods:
        __init__: Initializes a new instance of EmailExceptionManager.
        handle_exception: Asynchronously handles exceptions by sending email notifications.
    """


    def __init__(self, app):
        self.EmailOutputService = app.get_service("SmtpService")

    async def handle_exception(self, exception, notification_params=None):
        """
        Asynchronously handles an exception by sending an email notification.

        This method overrides the abstract method from ExceptionManager. It checks for the presence
        of notification parameters to send an email. If 'from_email' and 'to_emails' are provided
        in the notification_params, it sends an email using the EmailFailsafeManager. If the
        notification parameters are missing or incomplete, it logs an error message.

        Args:
            exception (Exception): The exception that needs to be handled.
            notification_params (Optional[dict]): Additional parameters used for the email notification.
                This should include 'from_email' and 'to_emails' keys.

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
