from asabiris.exception_manager.exception_manager_abc import ExceptionManager

import logging

L = logging.getLogger(__name__)


class SlackExceptionManager(ExceptionManager):
    def __init__(self, _, slack_failsafe_manager):
        self.SlackFailsafeManager = slack_failsafe_manager

    async def handle_exception(self, exception, notification_params=None):
        await self.SlackFailsafeManager.send_error_notification(str(exception), notification_params)
