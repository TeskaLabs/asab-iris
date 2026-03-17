import json
import logging
import configparser

import aiohttp
import asab

from ...errors import ASABIrisError, ErrorCode
from ...output_abc import OutputABC

L = logging.getLogger(__name__)


def check_config(config, section, parameter):
	try:
		return config.get(section, parameter)
	except (configparser.NoOptionError, configparser.NoSectionError) as e:
		L.warning("Configuration parameter '{}' is missing in section '{}': {}".format(parameter, section, e))
		return None


class MattermostOutputService(asab.Service, OutputABC):

	def __init__(self, app, service_name="MattermostOutputService"):
		super().__init__(app, service_name)

		self.Url = check_config(asab.Config, "mattermost", "url")
		self.Token = check_config(asab.Config, "mattermost", "token")
		self.BotUsername = check_config(asab.Config, "mattermost", "bot_username")
		self.SecurityChannelId = check_config(asab.Config, "mattermost", "security_channel_id")
		self.Timeout = int(asab.Config.get("mattermost", "timeout", fallback="10") or "10")
		self.ConfigService = app.get_service("TenantConfigExtractionService")

		self.IsConfigured = bool(self.Url and self.Token)
		if not self.IsConfigured:
			L.warning("Mattermost output service is not properly configured. Disabling Mattermost service.")

	def _resolve_config(self, tenant=None):
		config = {
			"url": self.Url,
			"token": self.Token,
			"bot_username": self.BotUsername,
			"security_channel_id": self.SecurityChannelId,
		}

		if tenant and self.ConfigService is not None:
			try:
				tenant_config = self.ConfigService.get_mattermost_config(tenant)
			except KeyError:
				L.warning("Tenant-specific Mattermost configuration not found for '%s'. Using global config.", tenant)
			else:
				for key, value in tenant_config.items():
					if value:
						config[key] = value

		return config

	async def send(self, payload, channel_id=None, username=None):
		if channel_id and username:
			raise ASABIrisError(
				ErrorCode.INVALID_REQUEST,
				tech_message="Provide either 'channel_id' or 'username', not both.",
				error_i18n_key="Invalid Mattermost destination.",
			)

		try:
			effective_tenant = asab.contextvars.Tenant.get()
		except LookupError:
			effective_tenant = None

		config = self._resolve_config(effective_tenant)
		if not config["url"] or not config["token"]:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="Mattermost URL or token is missing.",
				error_i18n_key="Mattermost service is not configured.",
			)

		if username:
			if not config["bot_username"]:
				raise ASABIrisError(
					ErrorCode.INVALID_SERVICE_CONFIGURATION,
					tech_message="Mattermost bot_username is required for direct messages.",
					error_i18n_key="Mattermost bot username is not configured.",
				)
			bot_user_id, target_user_id = await self.get_user_ids(config, config["bot_username"], username)
			channel_id = await self.get_direct_channel(config, bot_user_id, target_user_id)
		elif not channel_id:
			channel_id = config["security_channel_id"]

		if not channel_id:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="No Mattermost destination provided. Set 'channel_id', 'username', or configure 'security_channel_id'.",
				error_i18n_key="Mattermost destination is missing.",
			)

		post_payload = dict(payload)
		post_payload["channel_id"] = channel_id

		L.log(
			asab.LOG_NOTICE,
			"MattermostOutputService.send -> channel_id=%s, username=%s, payload=%r",
			struct_data={
				"channel_id": channel_id,
				"username": username,
				"payload": post_payload,
			}
		)

		return await self._post_json(config, "/api/v4/posts", post_payload)

	async def get_user_ids(self, config, bot_username, target_username):
		users = await self._post_json(
			config,
			"/api/v4/users/usernames",
			[bot_username, target_username],
		)

		if not isinstance(users, list):
			raise ASABIrisError(
				ErrorCode.SERVER_ERROR,
				tech_message="Mattermost returned an invalid response while resolving usernames.",
				error_i18n_key="Mattermost API returned an invalid response.",
			)

		user_map = {
			user.get("username"): user.get("id")
			for user in users
			if isinstance(user, dict)
		}

		bot_user_id = user_map.get(bot_username)
		target_user_id = user_map.get(target_username)
		missing = [name for name, value in ((bot_username, bot_user_id), (target_username, target_user_id)) if not value]
		if missing:
			raise ASABIrisError(
				ErrorCode.INVALID_REQUEST,
				tech_message="Mattermost user(s) not found: {}.".format(", ".join(missing)),
				error_i18n_key="Mattermost user was not found.",
				error_dict={"usernames": ", ".join(missing)},
			)

		return bot_user_id, target_user_id

	async def get_direct_channel(self, config, bot_user_id, target_user_id):
		channel = await self._post_json(
			config,
			"/api/v4/channels/direct",
			[bot_user_id, target_user_id],
		)
		channel_id = channel.get("id") if isinstance(channel, dict) else None
		if not channel_id:
			raise ASABIrisError(
				ErrorCode.SERVER_ERROR,
				tech_message="Mattermost did not return a direct channel id.",
				error_i18n_key="Mattermost API returned an invalid response.",
			)

		return channel_id

	async def _post_json(self, config, path, payload):
		url = "{}/{}".format(config["url"].rstrip("/"), path.lstrip("/"))
		headers = {
			"Authorization": "Bearer {}".format(config["token"]),
			"Content-Type": "application/json",
		}
		timeout = aiohttp.ClientTimeout(total=self.Timeout)

		try:
			async with aiohttp.ClientSession(timeout=timeout) as session:
				async with session.post(url, headers=headers, json=payload) as resp:
					body = await resp.text()
		except aiohttp.ClientError as e:
			raise ASABIrisError(
				ErrorCode.SERVER_ERROR,
				tech_message="Mattermost request failed: {}".format(e),
				error_i18n_key="Error occurred while calling Mattermost. Reason: '{{error_message}}'.",
				error_dict={"error_message": str(e)},
			) from e

		if resp.status in (401, 403):
			raise ASABIrisError(
				ErrorCode.AUTHENTICATION_FAILED,
				tech_message="Mattermost authentication failed: {}".format(body),
				error_i18n_key="Mattermost authentication failed.",
				error_dict={"error_message": body},
			)

		if resp.status in (400, 404):
			raise ASABIrisError(
				ErrorCode.INVALID_REQUEST,
				tech_message="Mattermost rejected the request: {}".format(body),
				error_i18n_key="Mattermost rejected the request.",
				error_dict={"error_message": body},
			)

		if resp.status >= 500:
			raise ASABIrisError(
				ErrorCode.SERVER_ERROR,
				tech_message="Mattermost server error {}: {}".format(resp.status, body),
				error_i18n_key="Mattermost server error.",
				error_dict={"error_message": body},
			)

		if len(body.strip()) == 0:
			return {}

		try:
			return json.loads(body)
		except json.JSONDecodeError as e:
			raise ASABIrisError(
				ErrorCode.SERVER_ERROR,
				tech_message="Mattermost returned invalid JSON: {}".format(e),
				error_i18n_key="Mattermost API returned invalid JSON.",
				error_dict={"error_message": str(e)},
			) from e
