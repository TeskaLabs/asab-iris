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
from .orchestration.sendsms import SMSOrchestrator
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

		# output services
		self.EmailOutputService = EmailOutputService(self)

		if 'slack' in asab.Config.sections():
			self.SlackOutputService = SlackOutputService(self)
			self.SendSlackOrchestrator = SendSlackOrchestrator(self)
		else:
			self.SendSlackOrchestrator = None

		if 'msteams' in asab.Config.sections():
			self.MSTeamsOutputService = MSTeamsOutputService(self)
			self.SendMSTeamsOrchestrator = SendMSTeamsOrchestrator(self)
		else:
			self.SendMSTeamsOrchestrator = None

		if 'sms' in asab.Config.sections():
			self.SMSOutputService = SMSOutputService(self)
			self.SMSOrchestrator = SMSOrchestrator(self)
		else:
			self.SendMSTeamsOrchestrator = None


		# Orchestrators
		self.SendEmailOrchestrator = SendEmailOrchestrator(self)
		self.RenderReportOrchestrator = RenderReportOrchestrator(self)

		self.SMSOrchestrator = SMSOrchestrator(self)
		self.SendSlackOrchestrator = SendSlackOrchestrator(self)

		self.WebHandler = WebHandler(self)

		# Apache Kafka API is conditional
		# if "kafka" in asab.Config.sections():
		#	self.KafkaHandler = KafkaHandler(self)
