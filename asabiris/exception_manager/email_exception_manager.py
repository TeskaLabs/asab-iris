from asabiris.exception_manager.exception_manager_abc import ExceptionManager

import logging

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


    def __init__(self, _, email_failsafe_manager):
        self.EmailFailsafeManager = email_failsafe_manager

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
        if notification_params:
            # Extract 'from_email' and 'to_emails' from the context
            from_email = notification_params.get('from_email')
            to_emails = notification_params.get('to_emails')

            # Send error notification via Email Failsafe Manager
            if from_email and to_emails:
                await self.EmailFailsafeManager.send_error_notification(
                    str(exception), from_email, to_emails)
        else:
            L.error("Failed to send error notification")
