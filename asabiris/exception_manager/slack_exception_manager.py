from asabiris.exception_manager.exception_manager_abc import ExceptionManager

import logging
import datetime

L = logging.getLogger(__name__)


class SlackExceptionManager(ExceptionManager):
    """
    A subclass of ExceptionManager for handling exceptions by sending notifications through Slack.

    This class provides an implementation of the abstract methods defined in the ExceptionManager class.
    Its focus is on managing exceptions by notifying relevant stakeholders via Slack messages. It utilizes
    a Slack failsafe manager for sending these notifications.

    Attributes:
        SlackFailsafeManager: An instance of a manager class responsible for sending Slack notifications.

    Methods:
        __init__: Initializes a new instance of SlackExceptionManager.
        handle_exception: Asynchronously handles exceptions by sending Slack notifications.
    """

    def __init__(self, app):
        self.SlackOutputService = app.get_service("SlackOutputService")

    async def handle_exception(self, exception, notification_params=None):
        """
        Asynchronously handles an exception by sending a notification to Slack.

        This method overrides the abstract method from ExceptionManager. It sends a Slack
        notification regarding the exception using the SlackFailsafeManager. The notification
        includes the exception details and any additional parameters provided for notification.

        Args:
            exception (Exception): The exception that needs to be handled.
            notification_params (Optional[dict]): Additional parameters used for the Slack notification.
                This could include details like channel, user mentions, etc.

        """
        L.warning("Exception occurred: {}".format(exception))
        error_message = self._generate_error_message_slack(str(exception))
        await self.SlackOutputService.send_message(str(error_message), notification_params)

    def _generate_error_message_slack(self, exception: str) -> str:
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

