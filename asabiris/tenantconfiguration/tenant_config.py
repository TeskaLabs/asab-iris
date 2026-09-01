import logging
import json
import configparser
import re
import urllib.parse
import asab

from ..exceptions import (
	TenantConfigNotFoundError,
	TenantConfigReadError,
	TenantConfigValidationError,
)

L = logging.getLogger(__name__)
TENANT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class TenantConfigExtractionService(asab.Service):

	def __init__(self, app, service_name="TenantConfigExtractionService"):
		super().__init__(app, service_name)

		# Initialize ZooKeeper client only if configuration exists
		self.TenantConfigPath = None
		self.ZK = None

		# Read and validate tenant configuration before exposing the service.
		try:
			tenant_config_url = asab.Config.get("tenant_config", "url")
		except (configparser.NoOptionError, configparser.NoSectionError) as e:
			raise TenantConfigValidationError(
				"Tenant configuration URL is not set in [tenant_config]."
			) from e

		url_parts = urllib.parse.urlparse(tenant_config_url)
		self.TenantConfigPath = self._validate_base_path(url_parts.path)

		if app.ZooKeeperContainer is None:
			raise TenantConfigReadError("ZooKeeper is unavailable for tenant configuration.")

		self.ZK = app.ZooKeeperContainer.ZooKeeper.Client
		if self.ZK is None:
			raise TenantConfigReadError("ZooKeeper client is unavailable for tenant configuration.")

		L.info(
			"Tenant configuration ZooKeeper client initialized.",
			struct_data={"tenant_config_path": self.TenantConfigPath},
		)

	@staticmethod
	def _validate_base_path(path):
		if not isinstance(path, str) or not path.startswith("/"):
			raise TenantConfigValidationError(
				"Tenant configuration URL must contain an absolute ZooKeeper path."
			)
		path = path.rstrip("/")
		if not path:
			raise TenantConfigValidationError(
				"Tenant configuration base path must not be the ZooKeeper root."
			)
		return path

	@staticmethod
	def _validate_tenant(tenant):
		if not isinstance(tenant, str) or TENANT_ID_RE.fullmatch(tenant) is None:
			raise TenantConfigValidationError(
				"Tenant identifier must contain only letters, digits, dots, underscores, and hyphens."
			)
		return tenant


	def load_tenant_config(self, tenant):
		"""
		Loads tenant-specific configuration from ZooKeeper.
		"""
		if self.ZK is None:
			raise TenantConfigReadError("Tenant configuration service is not ready.")

		base_path = self._validate_base_path(self.TenantConfigPath)
		tenant = self._validate_tenant(tenant)
		path = "{}/{}".format(base_path, tenant)

		try:
			exists = self.ZK.exists(path)
		except Exception as e:
			raise TenantConfigReadError(
				"Could not check tenant configuration in ZooKeeper."
			) from e
		if not exists:
			raise TenantConfigNotFoundError(
				"Tenant configuration not found at '{}'.".format(path)
			)

		try:
			data, _ = self.ZK.get(path)
		except Exception as e:
			raise TenantConfigReadError(
				"Could not read tenant configuration from ZooKeeper."
			) from e

		if not isinstance(data, bytes):
			raise TenantConfigValidationError("Tenant configuration payload must be bytes.")
		try:
			payload = data.decode("utf-8")
		except UnicodeDecodeError as e:
			raise TenantConfigValidationError(
				"Tenant configuration payload must be valid UTF-8."
			) from e
		try:
			config = json.loads(payload)
		except json.JSONDecodeError as e:
			raise TenantConfigValidationError(
				"Tenant configuration payload must be valid JSON."
			) from e
		if not isinstance(config, dict):
			raise TenantConfigValidationError("Tenant configuration payload must be a JSON object.")
		L.info(
			"Loaded tenant configuration from ZooKeeper.",
			struct_data={"tenant": tenant, "path": path},
		)
		return config

	def get_slack_config(self, tenant):
		"""
		Retrieves Slack-specific configuration.
		"""
		config = self.load_tenant_config(tenant)
		slack_config = config.get("slack")
		if not isinstance(slack_config, dict):
			raise TenantConfigValidationError("Tenant Slack configuration must be a JSON object.")
		token = slack_config.get("token")
		channel = slack_config.get("channel")
		if not isinstance(token, str) or not token.strip():
			raise TenantConfigValidationError("Tenant Slack configuration requires a string token.")
		if not isinstance(channel, str) or not channel.strip():
			raise TenantConfigValidationError("Tenant Slack configuration requires a string channel.")
		L.info(
			"Loaded Slack configuration for tenant.",
			struct_data={"tenant": tenant},
		)
		return token.strip(), channel.strip()

	def get_msteams_config(self, tenant):
		"""
		Retrieves MS Teams-specific configuration.
		"""
		config = self.load_tenant_config(tenant)
		teams_config = config.get("msteams")
		if not isinstance(teams_config, dict):
			raise TenantConfigValidationError("Tenant Microsoft Teams configuration must be a JSON object.")
		webhook_url = teams_config.get("webhook_url")
		if not isinstance(webhook_url, str) or not webhook_url.strip():
			raise TenantConfigValidationError(
				"Tenant Microsoft Teams configuration requires a string webhook_url."
			)
		L.info(
			"Loaded Microsoft Teams configuration for tenant.",
			struct_data={"tenant": tenant},
		)
		return webhook_url.strip()

	def get_mattermost_config(self, tenant):
		"""
		Retrieves Mattermost-specific configuration.
		"""
		config = self.load_tenant_config(tenant)
		mattermost_config = config.get("mattermost")
		if not isinstance(mattermost_config, dict):
			raise TenantConfigValidationError("Tenant Mattermost configuration must be a JSON object.")
		for key in ("url", "token", "bot_username", "security_channel_id"):
			value = mattermost_config.get(key)
			if value is not None and not isinstance(value, str):
				raise TenantConfigValidationError(
					"Tenant Mattermost configuration value '{}' must be a string.".format(key)
				)

		return {
			"url": mattermost_config.get("url"),
			"token": mattermost_config.get("token"),
			"bot_username": mattermost_config.get("bot_username"),
			"security_channel_id": mattermost_config.get("security_channel_id"),
		}

	def get_sms_config(self, tenant):
		"""
		Retrieves SMS-specific configuration for a given tenant.
		Falls back to global configuration if tenant-specific config is missing or incomplete.
		Returns None if any required value is missing.
		"""
		if tenant:
			try:
				tenant_config = self.load_tenant_config(tenant)
				tenant_sms_config = tenant_config.get("sms", {})

				login = tenant_sms_config.get("login")
				password = tenant_sms_config.get("password")
				api_url = tenant_sms_config.get("api_url")
				phone = tenant_sms_config.get("phone")

				# Ensure all values are present; otherwise, use global config
				if all([login, password, api_url]):
					L.info(
						"Loaded complete SMS configuration for tenant.",
						struct_data={"tenant": tenant},
					)
					return login, password, api_url, phone
				else:
					L.warning(
						"Tenant SMS configuration is incomplete; global [sms] credentials will be used.",
						struct_data={"tenant": tenant},
					)

			except (KeyError, TypeError) as e:
				L.warning(
					"Failed to load tenant SMS configuration; global [sms] credentials will be used.",
					struct_data={"tenant": tenant, "error_type": type(e).__name__},
				)

		return None, None, None


	def _normalize_recipients(self, recipients):
		"""
		Accepts list|tuple|str (comma-separated or single).
		Returns list[str] trimmed; empty entries removed.
		"""
		if recipients is None:
			return []
		if isinstance(recipients, (list, tuple)):
			return [str(x).strip() for x in recipients if str(x).strip()]
		s = str(recipients).strip()
		if len(s) == 0:
			return []
		return [p.strip() for p in s.split(",") if p.strip()]

	def get_email_config(self, tenant):
		"""
		Future-proof email config fetcher.

		Returns a dict with keys:
			- 'to': list[str]          (required for your current use)
			- 'cc': list[str]          (optional; defaults to [])
			- 'bcc': list[str]         (optional; defaults to [])
			- 'from': str or None      (optional)
			- 'subject': str or None   (optional)

		Source: config['email'].
		"""
		if not tenant:
			return {"to": [], "cc": [], "bcc": [], "from": None, "subject": None}

		try:
			cfg = self.load_tenant_config(tenant)
			email_cfg = cfg.get("email", {}) if isinstance(cfg, dict) else {}
			if not isinstance(email_cfg, dict):
				# Legacy case: a plain string under "email" means it's 'to'
				to_list = self._normalize_recipients(email_cfg)
				return {"to": to_list, "cc": [], "bcc": [], "from": None, "subject": None}

			to_list = self._normalize_recipients(email_cfg.get("to"))
			cc_list = self._normalize_recipients(email_cfg.get("cc"))
			bcc_list = self._normalize_recipients(email_cfg.get("bcc"))
			from_addr = email_cfg.get("from")
			subject = email_cfg.get("subject")

			if to_list:
				L.info(
					"Loaded tenant email recipients from ZooKeeper.",
					struct_data={"tenant": tenant, "recipient_count": len(to_list)},
				)
			else:
				L.warning(
					"No email.to recipients configured for tenant; configure email.to in tenant ZooKeeper config.",
					struct_data={"tenant": tenant},
				)

			return {
				"to": to_list,
				"cc": cc_list,
				"bcc": bcc_list,
				"from": from_addr if isinstance(from_addr, str) and len(from_addr.strip()) > 0 else None,
				"subject": subject if isinstance(subject, str) and len(subject.strip()) > 0 else None,
			}

		except Exception as e:
			L.warning(
				"Failed to load tenant email configuration from ZooKeeper; email delivery may use request body recipients only.",
				struct_data={"tenant": tenant, "error_type": type(e).__name__},
			)
			return {"to": [], "cc": [], "bcc": [], "from": None, "subject": None}

	def get_push_topic(self, tenant):
		cfg = self.load_tenant_config(tenant)
		push_cfg = cfg.get("push")
		if not isinstance(push_cfg, dict):
			raise TenantConfigValidationError("Tenant push configuration must be a JSON object.")

		topic = push_cfg.get("topic")
		if not isinstance(topic, str) or not topic.strip():
			raise TenantConfigValidationError("Tenant push configuration requires a string topic.")

		return topic.strip()
