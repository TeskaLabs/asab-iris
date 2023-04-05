import logging

#

L = logging.getLogger(__name__)


#


class SMSOrchestrator(object):

	def __init__(self, app):
		# Output service
		self.SMSOutput = app.get_service("SMSOutputService")

	async def send_sms(self, sms_dict):
		"""
		Sends an SMS message using the `SMSOutput` object.

		Args:
			sms_dict (dict): A dictionary containing the SMS message details, including the recipient's phone number
				and the message body.

		Returns:
			bool: A boolean indicating whether the message was sent successfully.
		"""
		return await self.SMSOutput.send(sms_dict)
