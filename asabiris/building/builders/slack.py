from .abc import NotificationBuilderABC


class NotificationBuilderSlack(NotificationBuilderABC):

	def __init__(self, tenant, dest_type, dest_value, msg_body, msg_template):
		super().__init__(tenant, dest_type, dest_value, msg_body, msg_template)
		self.DefaultTemplatesFolder = "/Slack/"


	def set_destination(self):
		"""
		Normalize DestinationValue into a single Slack channel
		"""
		if not self.DestinationValue:
			return

		if isinstance(self.DestinationValue, list):
			return self.DestinationValue[0]

		if not isinstance(self.DestinationValue, str):
			return

		return self.DestinationValue.split(",")[0]  # 1 str item


	def build_notification_dict(self):
		"""
		Example of the message structure:
		{
			"type":"slack",
			"body":{
				"template":"/Templates/Slack/XXXX.md",
				"params": {
					"name": "I am testing a template"
				}
			}
		}
		"""
		template_path = self.build_template_path(self.DefaultTemplatesFolder)
		slack_notification = {
			"type": self.NotificationType,
			"channel": self.set_destination(),
			"body": {
				"template": template_path,
				"params": self.MessageBody
			}
		}

		return slack_notification
