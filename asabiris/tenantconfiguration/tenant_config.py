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
		self.zk = None

		# Try to read tenant config from asab.Config
		try:
			tenant_config_url = asab.Config.get("tenant_config", "url")
			# Parse the ZooKeeper URL
			url_parts = urllib.parse.urlparse(tenant_config_url)
			self.TenantConfigPath = url_parts.path

			# Initialize Kazoo client
			self.zk = app.ZooKeeperContainer.ZooKeeper.Client
			L.info("ZooKeeper client initialized for tenant configuration.")

		except (configparser.NoOptionError, configparser.NoSectionError):
			L.warning("Tenant configuration not provided. Proceeding without ZooKeeper integration.")


	def load_tenant_config(self, tenant):
		"""
		Loads tenant-specific configuration from ZooKeeper.
		"""
		path = "{}/{}".format(self.TenantConfigPath, tenant)
		if not self.zk.exists(path):
			raise KeyError("Tenant configuration not found at '{}'.".format(path))

		data, _ = self.zk.get(path)
		config = json.loads(data.decode("utf-8"))
		L.info("Loaded tenant configuration from '{}'.".format(path))
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
			L.info("Loaded Slack config for tenant '{}'.".format(tenant))
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
			L.info("Loaded MS Teams config for tenant '{}'.".format(tenant))
			return webhook_url
		except KeyError as e:
			raise KeyError("MS Teams configuration missing key: '{}'".format(e))

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

				# Ensure all values are present; otherwise, use global config
				if all([login, password, api_url]):
					L.info("Loaded complete SMS config for tenant '{}'.".format(tenant))
					return login, password, api_url
				else:
					L.warning("Tenant '{}' SMS config is incomplete. Using global config.".format(tenant))

			except (KeyError, TypeError) as e:
				L.warning("Tenant-specific SMS configuration error for '{}'. Using global config. Error: '{}'".format(tenant, e))

		return None, None, None
