import copy
import logging

import asab

from .builders.email import NotificationBuilderEmail
from .builders.slack import NotificationBuilderSlack
from .builders.sms import NotificationBuilderSMS
from .builders.push import NotificationBuilderPush
from .builders.msteams import NotificationBuilderMSTeams
from .builders.mattermost import NotificationBuilderMattermost

from ..errors import ASABIrisError, ErrorCode


DESTINATION_EMAIL = "email"
DESTINATION_SLACK = "slack"
DESTINATION_SMS = "sms"
DESTINATION_PUSH = "push"
DESTINATION_MSTEAMS = "msteams"
DESTINATION_MATTERMOST = "mattermost"
DESTINATION_USER = "user"
DESTINATION_GROUP = "group"

#

L = logging.getLogger(__name__)

#


BUILDERS = {
	DESTINATION_EMAIL: NotificationBuilderEmail,
	DESTINATION_SLACK: NotificationBuilderSlack,
	DESTINATION_SMS: NotificationBuilderSMS,
	DESTINATION_PUSH: NotificationBuilderPush,
	DESTINATION_MSTEAMS: NotificationBuilderMSTeams,
	DESTINATION_MATTERMOST: NotificationBuilderMattermost,
}


class NotificationBuildingService(asab.Service):

	def __init__(self, app, service_name="NotificationBuildingService"):
		super().__init__(app, service_name)
		self.SeacatAuthUrl = asab.Config.get("seacat_auth", "url", fallback=None)


	async def build_messages(self, tenant, msg):
		"""
		Unified incoming message structure:

		{
			"destination": [
				{"type": "email", "value": "tester@teskalabs.com"},
				{"type": "user", "value": "mongodb:default:XXXXXXXXXXXXXX"},
				{"type": "slack", "value": "my-channel"},
				{"type": "sms", "value": 7777777777},
				{}, {}, {}
			],
			"body": {
					"tenant": "plus",
					"name": "Ticket Updated",
					"description": "Ticket was recently updated.",
					"ticket_id": "TEST-083",
					"ticket_updated": {
						"new_events": 22
					}
				},
			"template": {
				template: "Ticket Updated",
				wrapper: "Ticket Updated Wrapper"
			}
		}
		"""
		notifications = []

		# Backward compatibility: notifications already created by producer
		if msg.get("type") is not None:
			notifications.append(msg)
			return notifications

		# New format: one unified generic message as a simple json map
		msg_destination = msg.pop("destination")
		if msg_destination is None or not isinstance(msg_destination, list):
			# Log that no notification will be built based on this msg
			return notifications

		msg_body = msg.get("body")
		msg_template = msg.get("template")

		for destination in msg_destination:
			dest_type = destination.get("type")
			dest_value = destination.get("value")

			if dest_type is None or len(dest_type) == 0:
				continue

			try:
				builder_obj = await self.get_notification_builder(
					tenant,
					dest_type,
					dest_value,
					copy.deepcopy(msg_body),
					copy.deepcopy(msg_template)
				)

			except Exception as s:
				continue

			if builder_obj is None:
				continue
			
			notification = builder_obj.build_notification_dict()
			notifications.append(notification)

		return notifications


	async def get_notification_builder(self, tenant, dest_type, dest_value, msg_body, msg_template):
		builder_cls = BUILDERS.get(dest_type)
		if builder_cls is not None:
			return builder_cls(tenant, dest_type, dest_value, msg_body, msg_template)

		if dest_type == DESTINATION_USER:
			user_info = await self._get_credentials_info(dest_value)
			# Prefer email, then phone; pass the resolved contact as dest_value
			# Later should be indicated in account as prefered channel for user
			email = user_info.get("email")
			if email:
				return NotificationBuilderEmail(
					tenant, DESTINATION_EMAIL, email, msg_body, msg_template
				)
			phone = user_info.get("phone")
			if phone:
				return NotificationBuilderSMS(
					tenant, DESTINATION_SMS, phone, msg_body, msg_template
				)

		L.warning(
			"Message has unsupported destination type and was discarded.",
			struct_data={"message_type": dest_type, "tenant": tenant},
		)


	def _get_credentials_url(self, credentials_id):
		"""
		Builds request path for a given credentilas_id
		"""
		if self.SeacatAuthUrl is None or len(self.SeacatAuthUrl) == 0:
			# No url set in configuration or url is empty
			raise ASABIrisError(
				ErrorCode.NO_URL_CONFIGURED,
				tech_message="Empty url or no url in [seacat_auth] section",
				error_i18n_key="No URL has been provided for SeaCat. Please check configuration of the application."
			)

		url = "{seacat_private_api}/credentials/{credentials_id}".format(
			seacat_private_api=self.SeacatAuthUrl,
			credentials_id=credentials_id,
		)

		return url


	async def _get_credentials_info(self, credentials_id, internal_auth=False):
		"""
		Requests info for a given credentilas_id
		"""
		try:
			url = self._get_credentials_url(credentials_id)
		except ASABIrisError as e:
			L.warning(
				e.ErrorCode.get_i18n_name(),
				struct_data={"tech_message": e.TechMessage}
			)
			return {}

		# asab.web.WebContainer stores every incoming request in asab.contextvars.Request
		# DiscoveryService.session uses the Authorization header from the Request context by default
		if internal_auth is False:
			discovery_session = self.App.DiscoveryService.session()
		else:
			discovery_session = self.App.DiscoveryService.session(auth="internal")

		async with discovery_session as session:
			try:
				async with session.get(url) as resp:
					if resp.status == 404:
						raise ASABIrisError(
							ErrorCode.CREDENTIALS_NOT_FOUND,
							error_dict={"credentials_id": credentials_id},
							tech_message="Credentials not found",
							error_i18n_key="Credentials not found."
						)
					if resp.status != 200:
						reason = await resp.text()
						raise ASABIrisError(
							ErrorCode.SERVER_ERROR,
							error_dict={"credentials_id": credentials_id},
							tech_message=reason,
							error_i18n_key="Failed to get credentials."
						)

					credentials = await resp.json()

			except ASABIrisError as e:
				L.warning(
					e.ErrorCode.get_i18n_name(),
					struct_data=e.ErrorDict | {"tech_message": e.TechMessage}
				)
				return {}

			except asab.api.discovery.NotDiscoveredError:
				raise RuntimeError("SeaCat could not be reached on url: {}".format(self.SeacatAuthUrl))

		return credentials
