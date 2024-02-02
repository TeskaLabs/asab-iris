import configparser
import logging

import aiohttp

import asab

from ...output_abc import OutputABC

from ...errors import ASABIrisError, ErrorCode

#

L = logging.getLogger(__name__)

#


class MSTeamsOutputService(asab.Service, OutputABC):

	def __init__(self, app, service_name="MSTeamsOutputService"):
		super().__init__(app, service_name)
		try:
			self.TeamsWebhookUrl = asab.Config.get("msteams", "webhook_url")
		except (configparser.NoOptionError, configparser.NoSectionError) as e:
			L.error("Please provide webhook_url in slack configuration section.")
			raise e


	async def send(self, body):
		if self.TeamsWebhookUrl is None:
			return

		adaptive_card = {
			"type": "message",
			"attachments": [
				{
					"contentType": "application/vnd.microsoft.card.adaptive",
					"contentUrl": None,
					"content": {
						"$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
						"type": "AdaptiveCard",
						"version": "1.2",
						"body": [
							{
								"type": "TextBlock",
								"text": body
							}
						]
					}
				}
			]
		}
		async with aiohttp.ClientSession() as session:
			async with session.post(self.TeamsWebhookUrl, json=adaptive_card) as resp:
				if resp.status == 200:
					return True
				else:
					error_message = await resp.text()
					L.warning(
						"Sending alert to Teams was NOT successful. Response status: {}, response: {}".format(
							resp.status, error_message)
					)

					# Mapping specific status codes to error codes
					if resp.status == 400:  # Bad Request
						error_code = ErrorCode.INVALID_SERVICE_CONFIGURATION
					elif resp.status == 404:  # Not Found
						error_code = ErrorCode.TEMPLATE_NOT_FOUND
					elif resp.status == 503:  # Service Unavailable
						error_code = ErrorCode.SERVER_ERROR  # You might create a specific error code for this if needed
					# Add more mappings as necessary for other status codes
					else:
						error_code = ErrorCode.SERVER_ERROR  # General server error for other cases

					raise ASABIrisError(
						error_code,
						tech_message="Error encountered sending message to MS Teams. Status: {}, Reason: {}".format(
							resp.status, error_message),
						error_i18n_key="Error occurred while sending message to MS Teams. Reason: '{{error_message}}'.",
						error_dict={
							"error_message": error_message,
						}
					)
