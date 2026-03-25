import asyncio
import unittest
from unittest.mock import MagicMock

import asab

from asabiris.errors import ASABIrisError
from asabiris.orchestration.sendmattermost import SendMattermostOrchestrator


class AsyncMock(MagicMock):
	async def __call__(self, *args, **kwargs):
		return super().__call__(*args, **kwargs)


class TestSendMattermostOrchestrator(unittest.TestCase):

	def setUp(self):
		self.loop = asyncio.get_event_loop()
		self.app_mock = MagicMock(spec=asab.Application)
		self.output_service = AsyncMock()
		self.jinja_service = AsyncMock()
		self.jinja_service.format = AsyncMock(return_value="Rendered Mattermost message")
		self.jinja_service.Environment = MagicMock()
		self.jinja_service.Environment.from_string.side_effect = lambda value: MagicMock(render=MagicMock(return_value=value.replace("{{ user }}", "alice")))
		self.jinja_service.Variables = {}
		self.app_mock.get_service = MagicMock(side_effect=self.mock_get_service)
		self.orchestrator = SendMattermostOrchestrator(self.app_mock)

	def mock_get_service(self, service_name):
		if service_name == "JinjaService":
			return self.jinja_service
		if service_name == "MattermostOutputService":
			return self.output_service
		raise KeyError(service_name)

	def test_send_to_mattermost_channel_message(self):
		msg = {
			"body": {
				"template": "/Templates/Mattermost/message.md",
				"params": {"user": "alice"},
			},
			"channel_id": "channel-123",
		}

		self.loop.run_until_complete(self.orchestrator.send_to_mattermost(msg))

		self.output_service.send.assert_called_once_with(
			{"message": "Rendered Mattermost message"},
			channel_id="channel-123",
			username=None,
		)

	def test_send_to_mattermost_dm(self):
		msg = {
			"body": {
				"template": "/Templates/Mattermost/message.md",
				"params": {"user": "alice"},
			},
			"username": "alice",
		}

		self.loop.run_until_complete(self.orchestrator.send_to_mattermost(msg))

		self.output_service.send.assert_called_once_with(
			{"message": "Rendered Mattermost message"},
			channel_id=None,
			username="alice",
		)

	def test_send_to_mattermost_invalid_message_format(self):
		result = self.loop.run_until_complete(self.orchestrator.send_to_mattermost({"invalid": "message"}))
		self.assertIsNone(result)

	def test_send_to_mattermost_invalid_template_path(self):
		msg = {
			"body": {
				"template": "/Templates/Slack/message.md",
				"params": {},
			},
		}

		with self.assertRaises(ASABIrisError):
			self.loop.run_until_complete(self.orchestrator.send_to_mattermost(msg))

	def test_send_to_mattermost_renders_props(self):
		msg = {
			"body": {
				"template": "/Templates/Mattermost/message.md",
				"params": {"user": "alice"},
				"props": {
					"attachments": [
						{
							"title": "Alert for {{ user }}",
						}
					]
				},
			},
		}

		self.loop.run_until_complete(self.orchestrator.send_to_mattermost(msg))

		self.output_service.send.assert_called_once_with(
			{
				"message": "Rendered Mattermost message",
				"props": {
					"attachments": [
						{
							"title": "Alert for alice",
						}
					]
				},
			},
			channel_id=None,
			username=None,
		)
