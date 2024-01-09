import datetime
import logging

from asabiris.failsafe.failsafe_abc import FailsafeHandler
#

L = logging.getLogger(__name__)

#


class SlackFailsafeManager(FailsafeHandler):
	"""
	A manager class responsible for handling errors and executing fallback mechanisms for Slack notifications.

	This class provides functionality to send error notifications via email when an issue occurs in processing
	Slack-related requests. It acts as a failsafe mechanism to ensure that errors are communicated effectively.

	Attributes:
		SlackService: A service used to send slack messages.
	"""
	def __init__(self, app):
		"""
		Initialize the SlackFailsafeManager with the necessary SMTP service.

		Args:
			SlackService: A service used to send Slack messages.
		"""
		self.App = app

	async def send_error_notification(self, error, _):
		"""
		Send an error notification as a fallback mechanism.

		This method is invoked when there is an error in processing Slack requests. It sends a Slack
		notification detailing the error encountered.

		Args:
			error: The exception that was raised, indicating the nature of the error.
		"""
		error_message = self._generate_error_message_slack(str(error))
		await self.App.SlackOutputService.send_message(None, error_message)

	def _generate_error_message_slack(self, specific_error: str) -> str:
		timestamp = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
		error_message = (
			":warning: *Hello!*\n\n"
			"We encountered an issue while processing your request:\n`{}`\n\n"
			"Please review your input and try again.\n\n"
			"*Time:* `{}` UTC\n\n"
			"Best regards,\nASAB Iris :robot_face:"
		).format(
			specific_error,
			timestamp
		)
		return error_message
