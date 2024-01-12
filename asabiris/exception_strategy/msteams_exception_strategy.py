from asabiris.exception_strategy.exception_strategy_abc import ExceptionStrategy

import logging
import datetime

L = logging.getLogger(__name__)


class ExceptionMSTeamsNotifierStrategy(ExceptionStrategy):

    def __init__(self, app):
        self.MSTeamsOutputService = app.get_service("MSTeamsOutputService")

    async def handle_exception(self, exception, notification_params=None):
        """
        Asynchronously handles an exception by sending a notification to Microsoft Teams.

        Overrides the abstract method from ExceptionStrategy. It formats and sends a message
        to Microsoft Teams about the exception using the MSTeamsOutputService. The notification
        can include additional context or parameters specified in notification_params.

        Args:
            exception (Exception): The exception to handle.
            notification_params (Optional[dict]): Additional parameters for the Microsoft Teams
                notification, such as channel, user mentions, etc.
        """
        L.warning("Exception occurred: {}".format(exception))

        error_message = self._generate_error_message_msteams(str(exception))
        await self.MSTeamsOutputService.send(error_message)

    def _generate_error_message_msteams(self, exception: str) -> str:
        """
        Generates a formatted error message suitable for Microsoft Teams.

        This internal method formats an error message with the provided exception details,
        including a timestamp. The message is styled appropriately for Microsoft Teams.

        Args:
            exception (str): The specific exception message.

        Returns:
            str: The formatted error message for Microsoft Teams.
        """
        timestamp = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        error_message = (
            "Warning: *Hello!\n\n"
            "We encountered an issue while processing your request:\n`{}`\n\n"
            "Please review your input and try again.\n\n"
            "Time: `{}` UTC\n\n"
            "Best regards,\nASAB Iris"
        ).format(
            exception,
            timestamp
        )
        return error_message
