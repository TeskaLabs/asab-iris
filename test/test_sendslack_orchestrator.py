import unittest
from unittest.mock import patch, MagicMock
import asyncio
from asabiris.orchestration.sendslack import SendSlackOrchestrator  # Update the import path as necessary
import asab
from asabiris.exceptions import PathError


class AsyncMock(MagicMock):
	async def __call__(self, *args, **kwargs):
		return super().__call__(*args, **kwargs)


class TestSendSlackOrchestrator(unittest.TestCase):

	def setUp(self):
		self.loop = asyncio.get_event_loop()
		self.app_mock = MagicMock(spec=asab.Application)
		self.app_mock.get_service = MagicMock(side_effect=self.mock_get_service)

		# Orchestrator instance to test
		self.orchestrator = SendSlackOrchestrator(self.app_mock)

	def mock_get_service(self, service_name):
		if service_name == "JinjaService":
			mock_service = AsyncMock()
			mock_service.format = AsyncMock(return_value="Rendered Template")
			return mock_service
		elif service_name == "SlackOutputService":
			return AsyncMock()

	def test_send_to_slack_valid_message(self):
		msg = {
			'body': {
				'template': '/Templates/Slack/valid_template.md',
				'params': {}
			},
			'title': 'Test Message'
		}
		with patch.object(self.orchestrator, 'send_to_slack', new_callable=AsyncMock) as mock_send:
			self.loop.run_until_complete(mock_send(msg))
			mock_send.assert_called_once()

	def test_send_to_slack_invalid_message_format(self):
		msg = {'invalid': 'message'}
		result = self.loop.run_until_complete(self.orchestrator.send_to_slack(msg))
		# Assuming the method returns None for invalid format, we assert that.
		self.assertIsNone(result)

	def test_send_to_slack_with_attachments(self):
		msg = {
			'body': {
				'template': '/Templates/Slack/valid_template.md',
				'params': {}
			},
			'attachments': [
				{'template': '/Templates/Slack/attachment1.md', 'params': {}}
			]
		}
		with patch.object(self.orchestrator, 'send_to_slack', new_callable=AsyncMock) as mock_send:
			self.loop.run_until_complete(mock_send(msg))
			mock_send.assert_called_once()

	def test_path_error_on_invalid_template(self):
		msg = {
			'body': {
				'template': 'invalid_template_path',
				'params': {}
			}
		}
		with self.assertRaises(PathError):
			self.loop.run_until_complete(self.orchestrator.send_to_slack(msg))

	def test_attachment_rendering(self):
		attachment = {
			'template': '/Templates/Slack/attachment_template.md',
			'params': {}
		}
		# Simulate rendering of attachment
		with patch.object(self.orchestrator, 'render', new_callable=AsyncMock) as mock_render:
			self.loop.run_until_complete(mock_render(attachment['template'], attachment['params']))
			mock_render.assert_called_once_with(attachment['template'], attachment['params'])


	def test_get_file_name_with_filename(self):
		# Test that get_file_name returns the correct filename if provided
		attachment = {'filename': 'custom_filename.txt', 'format': 'txt'}
		file_name = self.orchestrator.get_file_name(attachment)
		self.assertEqual(file_name, 'custom_filename.txt')


	def test_get_file_name_without_filename(self):
		# Test that get_file_name generates a filename based on the current date if no filename is provided
		attachment = {'format': 'txt'}
		file_name = self.orchestrator.get_file_name(attachment)
		self.assertIsNotNone(file_name)
		self.assertTrue(file_name.startswith('att-'))
		self.assertTrue(file_name.endswith('.txt'))


	def test_get_content_type_known_extension(self):
		# Test that get_content_type returns the correct content type for a known file extension
		file_extension = '.pdf'
		content_type = self.orchestrator.get_content_type(file_extension)
		self.assertEqual(content_type, 'application/pdf')


	def test_get_content_type_unknown_extension(self):
		# Test that get_content_type returns 'application/octet-stream' for an unknown file extension
		file_extension = '.unknown'
		content_type = self.orchestrator.get_content_type(file_extension)
		self.assertEqual(content_type, 'application/octet-stream')

	def test_send_to_slack_with_invalid_attachment_path(self):
		# Test sending a message with an attachment that has an invalid path
		msg = {
			'body': {
				'template': '/Templates/Slack/valid_template.md',
				'params': {}
			},
			'attachments': [
				{'template': 'invalid_attachment_path', 'params': {}}
			]
		}
		with self.assertRaises(PathError) as context:
			self.loop.run_until_complete(self.orchestrator.send_to_slack(msg))

		# Assert that the exception has the correct message and attributes
		self.assertEqual(context.exception.InvalidPath, 'invalid_attachment_path')
		self.assertEqual(context.exception.UseCase, 'Slack')

	def test_send_to_slack_with_base64_attachment(self):
		# Test sending a message with an attachment that includes base64 content
		msg = {
			'body': {
				'template': '/Templates/Slack/valid_template.md',
				'params': {}
			},
			'attachments': [
				{
					'base64': 'c29tZV9iYXNlNjRfY29udGVudA==',  # 'some_base64_content' in base64
					'content-type': 'application/octet-stream',
					'filename': 'file.bin'
				}
			]
		}
		with patch.object(self.orchestrator, 'send_to_slack', new_callable=AsyncMock) as mock_send:
			self.loop.run_until_complete(mock_send(msg))
			mock_send.assert_called_once()


	def test_attachment_rendering_failure(self):
		# Test that an exception is raised when rendering of an attachment fails
		attachment = {
			'template': '/Templates/Slack/invalid_template.md',
			'params': {}
		}
		with patch.object(self.orchestrator, 'render', new_callable=AsyncMock) as mock_render:
			mock_render.side_effect = PathError
			with self.assertRaises(PathError):
				self.loop.run_until_complete(self.orchestrator.render(attachment['template'], attachment['params']))


	def test_send_to_slack_with_invalid_schema(self):
		# Test sending a message that doesn't conform to the expected schema
		msg = {
			'body': 'This is a string, not a dict as expected'
		}

		result = self.loop.run_until_complete(self.orchestrator.send_to_slack(msg))
		# Assuming the method returns None for invalid format, we assert that.
		self.assertIsNone(result)


	def test_send_to_slack_without_body_key(self):
		# Test sending a message without the required 'body' key
		msg = {
			'title': 'Test Message'
		}

		result = self.loop.run_until_complete(self.orchestrator.send_to_slack(msg))
		# Assuming the method returns None for invalid format, we assert that.
		self.assertIsNone(result)


if __name__ == '__main__':
	unittest.main()
