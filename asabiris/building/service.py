import asyncio
import copy
import logging

import asab
from asab.contextvars import Tenant

from .builders.email import NotificationBuilderEmail
from .builders.slack import NotificationBuilderSlack
from .builders.sms import NotificationBuilderSMS
from .builders.push import NotificationBuilderPush
from .builders.msteams import NotificationBuilderMSTeams
from .builders.mattermost import NotificationBuilderMattermost

from ..utils import read_yaml
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

		self.ReloadLock = asyncio.Lock()
		self.LibraryReloadPaths = (
			"/Notifications/Groups/",
		)
		self.Groups = {}

		app.PubSub.subscribe("Tenants.ready!", self.reload_tenants)
		app.PubSub.subscribe("Library.ready!", self._on_library_changed)
		app.PubSub.subscribe("Library.change!", self._on_library_changed)


	async def initialize(self, app):
		await self.reload_groups()


	def _on_library_changed(self, event_type=None, library_provider=None, path=None):
		if path is None or path.startswith(self.LibraryReloadPaths):
			self.App.TaskService.schedule(self.reload_groups())


	async def reload_tenants(self, _, message_type=None):
		self.App.TaskService.schedule(self.reload_groups())


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
			L.warning("Missing destination data in message or wrong format")
			return notifications

		msg_body = msg.get("body")
		msg_template = msg.get("template")

		for destination in msg_destination:
			dest_type = destination.get("type")
			dest_value = destination.get("value")

			if dest_type is None or len(dest_type) == 0:
				continue

			try:
				builder_objs = await self.get_notification_builders(
					tenant,
					dest_type,
					dest_value,
					msg_body,
					msg_template,
				)

			except Exception as e:
				L.error(
					"Failed to build notification",
					struct_data={
						"class": e.__class__.__name__.__str__(),
						"reason": str(e),
						"type": dest_type,
						"tenant": tenant
					}
				)
				continue

			for builder_obj in builder_objs:
				try:
					notification = builder_obj.build_notification_dict()
				except Exception as e:
					L.error(
						"Failed to build notification",
						struct_data={
							"class": e.__class__.__name__.__str__(),
							"reason": str(e),
							"type": dest_type,
							"tenant": tenant
						}
					)
					continue
				notifications.append(notification)

		return notifications


	async def get_notification_builders(self, tenant, dest_type, dest_value, msg_body, msg_template, visited=None):
		"""
		Resolve destination into one or more notification builders
		Groups are expanded recursively (members may themselves be groups)
		"""
		if visited is None:
			visited = set()  # groups currently being expanded, to stop cycles

		builder_cls = BUILDERS.get(dest_type)
		if builder_cls is not None:
			return [builder_cls(
				tenant, dest_type, dest_value,
				copy.deepcopy(msg_body),
				copy.deepcopy(msg_template),
			)]

		if dest_type == DESTINATION_USER:
			return await self._get_builders_for_user(
				tenant, dest_value, msg_body, msg_template
			)

		if dest_type == DESTINATION_GROUP:
			return await self._get_builders_for_group(
				tenant, dest_value, msg_body, msg_template, visited
			)

		L.warning(
			"Message has unsupported destination type and was discarded.",
			struct_data={"message_type": dest_type, "tenant": tenant},
		)
		return []


	async def _get_builders_for_user(self, tenant, dest_value, msg_body, msg_template):
		user_info = await self._get_credentials_info(dest_value)
		# Prefer email, then phone; pass the resolved contact as dest_value
		# Later should be indicated in account as prefered channel for user
		email = user_info.get("email")
		if email:
			return [NotificationBuilderEmail(
				tenant, DESTINATION_EMAIL, email,
				copy.deepcopy(msg_body),
				copy.deepcopy(msg_template),
			)]

		phone = user_info.get("phone")
		if phone:
			return [NotificationBuilderSMS(
				tenant, DESTINATION_SMS, phone,
				copy.deepcopy(msg_body),
				copy.deepcopy(msg_template),
			)]

		L.warning(
			"User has neither email nor phone setup; skipping notification",
			struct_data={"tenant": tenant, "cred_id": dest_value}
		)
		return []


	async def _get_builders_for_group(self, tenant, dest_value, msg_body, msg_template, visited):
		builders = []
		visit_key = (tenant, dest_value)
		if visit_key in visited:
			L.warning(
				"Circular group reference, skipping",
				struct_data={"group": dest_value, "tenant": tenant},
			)
			return builders
		visited.add(visit_key)

		try:
			group = self.Groups.get(tenant, {}).get(dest_value)
			if group is None:
				L.warning(
					"Group not found",
					struct_data={"group": dest_value, "tenant": tenant},
				)
				return builders

			for member in group.get("members") or []:
				member_type = member.get("type")
				member_value = member.get("value")
				if member_type is None or len(member_type) == 0:
					continue
				builders.extend(
					await self.get_notification_builders(
						tenant,
						member_type,
						member_value,
						msg_body,
						msg_template,
						visited,
					)
				)
			return builders

		finally:
			visited.discard(visit_key)


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


	async def _get_credentials_info(self, credentials_id):
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

			except asab.api.discovery.NotDiscoveredError:
				raise RuntimeError("SeaCat could not be reached on url: {}".format(self.SeacatAuthUrl))

		return credentials


	async def reload_groups(self, event_type=None, library_provider=None, path=None):
		"""
		Loads groups settings from Library

		{
			{'tenant':
				{'SOC L1':
					{
						'define': {
							'type': 'iris/notifications'
						},
						'members': [
							{'type': 'user', 'value': 'XXXXXXXXXXXX'},
							{'type': 'email', 'value': 'tester@teskalabs.com'},
							{'type': 'group', 'value': 'SOC L2'},
							...
						]
					}
				}
			}
		"""
		# Tenants loaded before Library is ready / Library is not available
		if not self.App.Library.is_ready():
			return

		# Get the latest version of Tenants List
		tenants = self.App.TenantService.get_tenants()

		# Tenants list is not read yet
		if tenants is None:
			return

		# TenantsService hasn't updated tenants list yet
		if len(tenants) == 0:
			return

		if self.ReloadLock.locked():
			return

		async with self.ReloadLock:

			# Load Groups / store them as tenant-specific items
			for tenant in tenants:

				# Context variable specifies current tenant context
				# Tenant-layered Library works through context variable
				tenant_context = Tenant.set(tenant)

				if tenant not in self.Groups:
					self.Groups[tenant] = {}

				try:
					library_items = await self.App.Library.list("/Notifications/Groups/")
					active_groups = set()

					for library_item in library_items:
						group_path = library_item.name

						# Item path must end with an extension
						if library_item.type == "dir":
							continue

						group_name = group_path.replace(".yaml", "").split('/')[-1]
						if library_item.disabled is True:
							continue

						active_groups.add(group_name)

						try:
							declaration = await self.read_group(tenant, group_path)
							# If declaration is reloaded correctly => update in storage
							# If not => the existing data will be used
							self.Groups[tenant][group_name] = declaration

						except ASABIrisError as e:
							L.error(
								e.ErrorCode.get_i18n_name(),
								struct_data=(e.ErrorDict or {}) | {
									"tech_message": e.TechMessage,
									"tenant": tenant,
									"path": group_path
								}
							)

						except Exception as e:
							L.exception(
								"Exception occurred while loading Groups",
								struct_data={
									"class": e.__class__.__name__.__str__(),
									"reason": str(e),
									"tenant": tenant,
									"path": group_path
								}
							)

					# Prune groups removed from Library & disabled
					for cached_name in list(self.Groups[tenant].keys()):
						if cached_name not in active_groups:
							self.Groups[tenant].pop(cached_name, None)

				# For each tenant set there must be a tenant reset
				finally:
					Tenant.reset(tenant_context)

		L.log(asab.LOG_NOTICE, "Groups loaded")


	async def read_group(self, tenant, path):
		declaration = await read_yaml(self.App.Library, path)
		L.debug(
			"Group for a tenant loaded",
			struct_data={"tenant": tenant, "path": path}
		)
		return declaration
