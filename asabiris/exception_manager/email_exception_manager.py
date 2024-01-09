from asabiris.exception_manager_abc import ExceptionManager

import logging

L = logging.getLogger(__name__)


class EmailExceptionManager(ExceptionManager):
    def __init__(self, _, email_Service):
        self.EmailFailsafeManager = email_Service

    async def handle_exception(self, exception, notification_params):

        # Extract 'from_email' and 'to_emails' from the context
        from_email = notification_params.get('from_email')
        to_emails = notification_params.get('to_emails')

        # Send error notification via Email Failsafe Manager
        if from_email and to_emails:
            await self.EmailFailsafeManager.send_error_notification(
                str(exception), from_email, to_emails)
        else:
            L.error("Failed to send error notification")
