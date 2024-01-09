from asabiris.exception_handler.exception_handler import ExceptionHandlingStrategy

import logging

L = logging.getLogger(__name__)


class EmailExceptionHandlingStrategy(ExceptionHandlingStrategy):
    def __init__(self, failsafe_manager):
        self.EmailFailsafeManager = failsafe_manager

    async def handle_exception(self, exception, context_strategy):

        if context_strategy == 'kafka':
            # Extract 'from_email' and 'to_emails' from the context
            from_email = context_strategy.get('from_email')
            to_emails = context_strategy.get('to_emails')

            # Send error notification via Email Failsafe Manager
            if from_email and to_emails:
                await self.EmailFailsafeManager.send_error_notification(
                    str(exception), from_email, to_emails)
            else:
                L.error("Failed to send error notification")
        else:
            # we assume it's default
            raise exception
