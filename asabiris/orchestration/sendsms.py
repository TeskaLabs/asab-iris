import logging


#

L = logging.getLogger(__name__)

#


class SMSOrchestrator(object):

	def __init__(self, app):
		# formatters
		self.SMSOutput = app.get_service("SMSOutputService")


	async def send_sms(self, sms_dict):
		"""
		This method renders templates based on the depending on the
		extension of template. Returns the html/pdf.
		"""
		return await self.SMSOutput.send(sms_dict)