import logging

from ..errors import ASABIrisError, ErrorCode

#

L = logging.getLogger(__name__)


#


class SendSMSOrchestrator(object):

	def __init__(self, app):
		self.JinjaService = app.get_service("JinjaService")
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
		body = sms_dict['body']
		template = body['template']
		tenant = sms_dict.get("tenant", None)

		if not template.startswith("/Templates/SMS/"):
			raise ASABIrisError(
				ErrorCode.INVALID_PATH,
				tech_message="Incorrect template path '{}'. Move templates to '/Templates/SMS/'.".format(template),
				error_i18n_key="Incorrect template path '{{incorrect_path}}'. Please move your templates to '/Templates/SMS/'.",
				error_dict={
					"incorrect_path": template,
				}
			)

		params = body.get("params", {})
		sms_dict['message_body'] = await self.JinjaService.format(template, params)
		return await self.SMSOutput.send(sms_dict, tenant)
