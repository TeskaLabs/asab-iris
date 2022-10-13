import logging
import asab.api
import asab
import asab.web.rest
import asab.zookeeper
import asab.library

# formatters
from .formatter.jinja import JinjaFormatterService
from .formatter.markdown import MarkdownFormatterService
from .formatter.pdf import PdfFormatterService

# output
from .output.smtp import EmailOutputService
from .output.slack import SlackOutputService

# orchestrators.
from .orchestration.sendmail import SendMailOrchestrator
from .orchestration.sendmail import SendMailHandler

from .orchestration.render import RenderReportOrchestrator
from .orchestration.kafka import KafkaNotificationsOrchestrator

L = logging.getLogger(__name__)

asab.Config.add_defaults(
	{
		"web": {
		},
	}
)


class IRISApplication(asab.Application):

	def __init__(self, args=None):
		super().__init__(args=args)

		self.add_module(asab.web.Module)
		self.add_module(asab.zookeeper.Module)

		# Locate the web service
		self.WebService = self.get_service("asab.WebService")
		self.WebContainer = self.WebService.WebContainer
		self.WebContainer.WebApp.middlewares.append(
			asab.web.rest.JsonExceptionMiddleware

		)

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
		self.Markdown2HTMLService = MarkdownFormatterService(self)
		self.PdfFormatterService = PdfFormatterService(self)
		self.JinjaPrintService = JinjaFormatterService(self)

		# output services
		self.EmailOutputService = EmailOutputService(self)
		self.SlackOutputService = SlackOutputService(self)

		# Initialize our orchestrators
		self.SendMailOrchestrator = SendMailOrchestrator(self)
		self.SendMailHandler = SendMailHandler(self)
		self.RenderReportOrchestrator = RenderReportOrchestrator(self)

		# Apache Kafka API is conditional
		if "kafka" in asab.Config.sections():
			self.KafkaNotificationsOrchestrator = KafkaNotificationsOrchestrator(self)
