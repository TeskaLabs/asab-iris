import logging
import asab.api
import asab
import asab.web.rest
import asab.zookeeper
import asab.library
import asab.metrics

# formatters
from .formatter.jinja import JinjaFormatterService
from .formatter.markdown import MarkdownFormatterService
from .formatter.pdf import PdfFormatterService
from .formatter.attachments import AttachmentRenderingService

# output
from .output.smtp import EmailOutputService
from .output.slack import SlackOutputService
from .output.sms import SMSOutputService
from .output.msteams import MSTeamsOutputService

# orchestrators.
from .orchestration.sendemail import SendEmailOrchestrator
from .orchestration.render import RenderReportOrchestrator
from .orchestration.sendsms import SendSMSOrchestrator
from .orchestration.sendmsteams import SendMSTeamsOrchestrator

from .handlers.kafkahandler import KafkaHandler
from .handlers.webhandler import WebHandler
from .orchestration.sendslack import SendSlackOrchestrator

L = logging.getLogger(__name__)


asab.Config.add_defaults({
	"web": {
		"listen": 8896,  # Well-known port of asab iris
		"body_max_size": 31457280  # maximum size of the request body that the web server can handle.
	},
	"kafka": {
		"topic": "notifications",
		"group_id": "asab-iris",
	}
})


class ASABIRISApplication(asab.Application):

	def __init__(self, args=None):
		super().__init__(args=args)
		self.add_module(asab.web.Module)
		self.add_module(asab.zookeeper.Module)
		self.add_module(asab.metrics.Module)

		# Locate the web service
		self.WebService = self.get_service("asab.WebService")
		self.WebContainer = self.WebService.WebContainer
		self.WebContainer.WebApp.middlewares.append(
			asab.web.rest.JsonExceptionMiddleware

		)

		# Initialize Sentry.io
		if asab.Config.has_section("sentry"):
			import asab.sentry as asab_sentry
			self.SentryService = asab_sentry.SentryService(self)

		# Initialize library service
		self.LibraryService = asab.library.LibraryService(
			self,
			"LibraryService",
		)

		if 'zookeeper' in asab.Config.sections():
			self.ZooKeeperService = self.get_service("asab.ZooKeeperService")
			self.ZooKeeperContainer = asab.zookeeper.ZooKeeperContainer(self.ZooKeeperService, 'zookeeper')
		else:
			self.ZooKeeperContainer = None

		# Initialize API service
		self.ASABApiService = asab.api.ApiService(self)
		self.ASABApiService.initialize_web()
		if 'zookeeper' in asab.Config.sections():
			self.ASABApiService.initialize_zookeeper()

		# formatter
		self.MarkdownFormatterService = MarkdownFormatterService(self)
		self.PdfFormatterService = PdfFormatterService(self)
		self.JinjaFormatterService = JinjaFormatterService(self)
		self.AttachmentRenderingService = AttachmentRenderingService(self)

		# Initialize TenantConfigExtractionService if present
		if asab.Config.has_section("tenant_config"):
			from .tenantconfiguration.tenant_config import TenantConfigExtractionService
			self.TenantConfigExtractionService = TenantConfigExtractionService(self)
		else:
			self.TenantConfigExtractionService = None

		# output services
		self.EmailOutputService = EmailOutputService(self)

		if 'slack' in asab.Config.sections():
			# Initialize the SlackOutputService
			self.SlackOutputService = SlackOutputService(self)

			# Only initialize SendSlackOrchestrator if the SlackOutputService client is valid
			if self.SlackOutputService.Client is None:
				# If client is None, disable Slack orchestrator as well
				self.SendSlackOrchestrator = None
			else:
				# If the client is valid, initialize the orchestrator
				self.SendSlackOrchestrator = SendSlackOrchestrator(self)

		else:
			# If the slack section is not present in the config, set both services to None
			self.SlackOutputService = None
			self.SendSlackOrchestrator = None

		if 'msteams' in asab.Config.sections():
			# Initialize the MSTeamsOutputService
			self.MSTeamsOutputService = MSTeamsOutputService(self)
			if self.MSTeamsOutputService.TeamsWebhookUrl is None:
				# If client is None, disable MSTeams orchestrator as well
				self.SendMSTeamsOrchestrator = None
			else:
				# If the TeamsWebhookUrl is valid, initialize the orchestrator
				self.SendMSTeamsOrchestrator = SendMSTeamsOrchestrator(self)
		else:
			self.SendMSTeamsOrchestrator = None
			self.MSTeamsOutputService = None

		if 'sms' in asab.Config.sections():
			self.SMSOutputService = SMSOutputService(self)
			self.SendSMSOrchestrator = SendSMSOrchestrator(self)
		else:
			self.SendSMSOrchestrator = None


		# Orchestrators
		self.SendEmailOrchestrator = SendEmailOrchestrator(self)
		self.RenderReportOrchestrator = RenderReportOrchestrator(self)

		self.WebHandler = WebHandler(self)

		# Apache Kafka API is conditional
		if "kafka" in asab.Config.sections():
			self.KafkaHandler = KafkaHandler(self)
