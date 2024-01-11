import datetime
import logging

from asabiris.failsafe.failsafe_abc import FailsafeManager
#

L = logging.getLogger(__name__)

#


class MSTeamsFailsafeManager(FailsafeManager):
	"""
	A manager class responsible for handling errors and executing fallback mechanisms for MSTeams notifications.

	This class provides functionality to send error notifications via email when an issue occurs in processing
	MSTeams-related requests. It acts as a failsafe mechanism to ensure that errors are communicated effectively.

	Attributes:
		MSTeamsOutputService: A service used to send MSTeams messages.
	"""
	def __init__(self, app):
		"""
		Initialize the MSteamsFailsafeManager with the necessary SMTP service.

		Args:
			MSTeamsOutputService: A service used to send MSteams messages.
		"""
		self.App = app

	async def send_error_notification(self, error, _):
		"""
		Send an error notification as a fallback mechanism.

		This method is invoked when there is an error in processing MSteams requests. It sends a MSteams
		notification detailing the error encountered.

		Args:
			error: The exception that was raised, indicating the nature of the error.
		"""
		error_message = self._generate_error_message_msteams(str(error))
		await self.App.MSTeamsOutputService.send(error_message)

	def _generate_error_message_msteams(self, specific_error: str) -> str:
		timestamp = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
		error_message = (
			"Warning: *Hello!\n\n"
			"We encountered an issue while processing your request:\n`{}`\n\n"
			"Please review your input and try again.\n\n"
			"Time: `{}` UTC\n\n"
			"Best regards,\nASAB Iris"
		).format(
			specific_error,
			timestamp
		)
		return error_message
