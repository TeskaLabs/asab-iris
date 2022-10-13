import unittest
import logging
import asab.abc.singleton
import asab
import asab.proactor

from asabiris.output_abc import OutputABC


class TestCase(unittest.TestCase):

	def setUp(self) -> None:
		self.App = asab.Application(args=[])
		self.App.add_module(asab.proactor.Module)

		self.App.SMTPOutputService = MockSMTPOutputService(self.App)

	def tearDown(self):
		asab.abc.singleton.Singleton.delete(self.App.__class__)
		self.App = None
		root_logger = logging.getLogger()
		root_logger.handlers = []




class MockSMTPOutputService(asab.Service, OutputABC):

	def __init__(
		self, app, service_name="asab.SmtpService", config_section_name='smtp'
	):
		super().__init__(app, service_name)
		self.Output = []


	async def send(self, **kwargs):
		self.Output.append(kwargs)
