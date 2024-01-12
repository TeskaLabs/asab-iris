from asabiris.exception_strategy.exception_strategy_abc import ExceptionStrategy

import logging
import datetime

L = logging.getLogger(__name__)


class SlackExceptionStrategy(ExceptionStrategy):
    """
    A subclass of ExceptionStrategy for handling exceptions by sending notifications through Slack.

    This class extends ExceptionStrategy to implement a specific mechanism for dealing with
    exceptions by notifying stakeholders via Slack. It uses a service, identified as SlackOutputService,
    to send these notifications.

    Attributes:
        SlackOutputService: An instance responsible for managing Slack notifications.
        It is expected to provide a method for sending messages to a Slack channel.

    Methods:
        __init__: Initializes the strategy with a reference to a SlackOutputService.
        handle_exception: Asynchronously handles exceptions by posting notifications to Slack.
    """
    def __init__(self, app):
        self.SlackOutputService = app.get_service("SlackOutputService")

    async def handle_exception(self, exception, notification_params=None):
        """
        Generates a formatted error message suitable for Slack.

        This internal method formats an error message with the provided exception details,
        including a timestamp. The message is styled for Slack with markdown-like syntax.

        Args:
            exception (str): The specific exception message.

        Returns:
            str: The formatted error message for Slack.
        """
        L.warning("Exception occurred: {}".format(exception))
        error_message = self._generate_error_message_slack(str(exception))
        await self.SlackOutputService.send_message(str(error_message), notification_params)

    def _generate_error_message_slack(self, exception: str) -> str:
        """
        Generates a formatted error message suitable for Slack.

        This internal method formats an error message with the provided exception details,
        including a timestamp. The message is styled appropriately for Slack.

        Args:
            exception (str): The specific exception message.

        Returns:
            str: The formatted error message for Slack.
        """
        timestamp = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        error_message = (
            ":warning: *Hello!*\n\n"
            "We encountered an issue while processing your request:\n`{}`\n\n"
            "Please review your input and try again.\n\n"
            "*Time:* `{}` UTC\n\n"
            "Best regards,\nASAB Iris :robot_face:"
        ).format(
            exception,
            timestamp
        )
        return error_message
