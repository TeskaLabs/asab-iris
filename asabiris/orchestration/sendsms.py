import os
import logging

from .. import utils

#

L = logging.getLogger(__name__)

#


class RenderReportOrchestrator(object):

	def __init__(self, app):
		# formatters
		self.SMSOutput = app.get_service("SMSOutputService")


	async def send_sms(self, sms_dict):
		"""
		This method renders templates based on the depending on the
		extension of template. Returns the html/pdf.
		"""
		html = await self.SMSOutput.send(sms_dict)

