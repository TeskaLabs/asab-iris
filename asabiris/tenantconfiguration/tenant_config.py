import logging
import json
import configparser
import urllib.parse
import kazoo.client
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
			self.zk_hosts = url_parts.netloc

			# Initialize Kazoo client
			self.zk = kazoo.client.KazooClient(hosts=self.zk_hosts)
			self.zk.start()
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
