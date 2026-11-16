import re

from .abc import NotificationBuilderABC

CHANNEL_ID_RE = re.compile(r"^[a-z0-9]{26}$")
USERNAME_RE = re.compile(r"^[a-z][a-z0-9._-]{2,21}$")


class NotificationBuilderMattermost(NotificationBuilderABC):

	def __init__(self, tenant, dest_type, dest_data, msg_body, msg_template):
		super().__init__(tenant, dest_type, dest_data, msg_body, msg_template)
		self.DefaultTemplatesFolder = "/Mattermost/"


	def set_destination(self):
		"""
		Classify DestinationValue as either a Mattermost channel_id or username

		Channel ID:
		- Type: Channel
		- Exactly 26 characters
		- [a-z0-9] only
		- Starts with: any of those
		- Example: x64h4o7nubyf5dymu95pa3ci9c

		Bot Username:
		- Type: Direct message
		- 3 to 22 characters
		- Lowercase letters, digits, ., -, _
		- Starts with: must start with a letter
		- Example: my-alert-bot

		Valid shapes in incoming structure:
		{"type": "mattermost", "value": "x64h4o7nubyf5dymu95pa3ci9c"}
		{"type": "mattermost", "value": "alice"}
		{"type": "mattermost", "value": ["alice"]}
		"""
		if not self.DestinationValue:
			return None, None

		if isinstance(self.DestinationValue, list):
			value = self.DestinationValue[0]
		elif isinstance(self.DestinationValue, str):
			value = self.DestinationValue.split(",")[0].strip()
		else:
			return None, None

		if CHANNEL_ID_RE.fullmatch(value):
			return value, None

		if USERNAME_RE.fullmatch(value):
			return None, value

		return None, None


	def build_notification_dict(self):
		"""
		Example of the message structure:
		{
			"channel_id": "optional-channel-id",
			"username": "optional-target-username-for-dm",
			"body": {
				"template": "/Templates/Mattermost/XXXX.md",
				"params": {...},
				"props": {...}
			}
		}
		"""
		template_path = self.build_template_path(self.DefaultTemplatesFolder)
		channel_id, username = self.set_destination()
		# TODO: decide how props should come in unified message
		mattermost_notification = {
			"type": self.NotificationType,
			"body": {
				"template": template_path,
				"params": self.MessageBody
			}
		}
		if channel_id is not None:
			mattermost_notification["channel_id"] = channel_id
		if username is not None:
			mattermost_notification["username"] = username

		return mattermost_notification
