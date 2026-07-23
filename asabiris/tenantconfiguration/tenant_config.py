import logging
import json
import configparser
import urllib.parse
import asab

L = logging.getLogger(__name__)


class TenantConfigExtractionService(asab.Service):

	def __init__(self, app, service_name="TenantConfigExtractionService"):
		super().__init__(app, service_name)

		# Initialize ZooKeeper client only if configuration exists
		self.TenantConfigPath = None
		self.ZK = None

		# Try to read tenant config from asab.Config
		try:
			tenant_config_url = asab.Config.get("tenant_config", "url")
			# Parse the ZooKeeper URL
			url_parts = urllib.parse.urlparse(tenant_config_url)
			self.TenantConfigPath = url_parts.path

			# Initialize Kazoo client
			self.ZK = app.ZooKeeperContainer.ZooKeeper.Client
			L.info(
				"Tenant configuration ZooKeeper client initialized.",
				struct_data={"tenant_config_path": self.TenantConfigPath},
			)

		except (configparser.NoOptionError, configparser.NoSectionError):
			L.warning(
				"Tenant configuration URL is not set in [tenant_config]; per-tenant output settings will not be loaded from ZooKeeper.",
			)


	def load_tenant_config(self, tenant):
		"""
		Loads tenant-specific configuration from ZooKeeper.
		"""
		path = "{}/{}".format(self.TenantConfigPath, tenant)
		if not self.ZK.exists(path):
			raise KeyError("Tenant configuration not found at '{}'.".format(path))

		data, _ = self.ZK.get(path)
		config = json.loads(data.decode("utf-8"))
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
		try:
			slack_config = config["slack"]
			token = slack_config["token"]
			channel = slack_config["channel"]
			L.info(
				"Loaded Slack configuration for tenant.",
				struct_data={"tenant": tenant},
			)
			return token, channel
		except KeyError as e:
			raise KeyError("Slack configuration missing key: '{}'".format(e))

	def get_msteams_config(self, tenant):
		"""
		Retrieves MS Teams-specific configuration.
		"""
		config = self.load_tenant_config(tenant)
		try:
			webhook_url = config["msteams"]["webhook_url"]
			L.info(
				"Loaded Microsoft Teams configuration for tenant.",
				struct_data={"tenant": tenant},
			)
			return webhook_url
		except KeyError as e:
			raise KeyError("MS Teams configuration missing key: '{}'".format(e))

	def get_mattermost_config(self, tenant):
		"""
		Retrieves Mattermost-specific configuration.
		"""
		config = self.load_tenant_config(tenant)
		try:
			mattermost_config = config["mattermost"]
		except KeyError as e:
			raise KeyError("Mattermost configuration missing key: '{}'".format(e))

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
		push_cfg = cfg.get("push") if isinstance(cfg, dict) else None
		if not isinstance(push_cfg, dict):
			raise KeyError("Push configuration missing for tenant '{}'.".format(tenant))

		topic = push_cfg.get("topic")
		if topic is None or len(str(topic).strip()) == 0:
			raise KeyError("Push topic missing for tenant '{}'.".format(tenant))

		return str(topic).strip()
