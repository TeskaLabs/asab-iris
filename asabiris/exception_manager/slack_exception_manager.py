from asabiris.exception_manager.exception_manager_abc import ExceptionManager

import logging

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

    def __init__(self, _, slack_failsafe_manager):
        self.SlackFailsafeManager = slack_failsafe_manager

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
        await self.SlackFailsafeManager.send_error_notification(str(exception), notification_params)
