from asabiris.exception_manager.exception_manager_abc import ExceptionManager

import logging

L = logging.getLogger(__name__)


class MSTeamsExceptionManager(ExceptionManager):

    def __init__(self, _, msteams_failsafe_manager):
        self.MSTeamsFailsafeManager = msteams_failsafe_manager

    async def handle_exception(self, exception, notification_params=None):
        """
        Asynchronously handles an exception by sending a notification to MSteams.

        This method overrides the abstract method from ExceptionManager. It sends a MSTeams
        notification regarding the exception using the MSteamsFailsafeManager. The notification
        includes the exception details and any additional parameters provided for notification.

        Args:
            exception (Exception): The exception that needs to be handled.
            notification_params (Optional[dict]): Additional parameters used for the MSTeams notification.
                This could include details like channel, user mentions, etc.

        """
        await self.MSTeamsFailsafeManager.send(str(exception), notification_params)
