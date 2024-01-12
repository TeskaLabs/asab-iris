from asabiris.exception_manager.exception_manager_abc import ExceptionManager

import logging
import datetime

L = logging.getLogger(__name__)


class MSTeamsExceptionManager(ExceptionManager):

    def __init__(self, app):
        self.MSTeamsOutputService = app.get_service("MSTeamsOutputService")

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
        L.warning("Exception occurred: {}".format(exception))

        error_message = self._generate_error_message_msteams(str(exception))
        await self.MSTeamsOutputService.send(error_message)

    def _generate_error_message_msteams(self, exception: str) -> str:
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
