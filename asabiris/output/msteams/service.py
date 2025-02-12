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
		except configparser.NoOptionError:
			L.error("Please provide webhook_url in msteams configuration section.")
			exit()
		except configparser.NoSectionError:
			L.warning("Configuration section 'msteams' is not provided.")
			self.TeamsWebhookUrl = None

		# Initialize Tenant Config Service
		self.ConfigService = app.get_service("TenantConfigExtractionService")

	async def send(self, body, tenant):
		webhook_url = self.TeamsWebhookUrl

		if tenant:
			try:
				webhook_url = self.ConfigService.get_msteams_config(tenant)
			except KeyError:
				L.warning(
					"Tenant-specific MS Teams configuration not found for '{}'. Using global config.".format(tenant)
				)

		if webhook_url is None:
			L.error("MS Teams webhook URL is missing.")
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
								"type": "ColumnSet",
								"columns": [
									{
										"type": "Column",
										"width": "stretch",
										"items": [
											{
												"type": "TextBlock",
												"text": body,
												"wrap": True
											}
										]
									}
								]
							}
						]
					}
				}
			]
		}

		async with aiohttp.ClientSession() as session:
			async with session.post(webhook_url, json=adaptive_card) as resp:
				if resp.status == 200:
					L.log(asab.LOG_NOTICE, "MSTeams message sent successfully.")
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
						error_code = ErrorCode.SERVER_ERROR
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
