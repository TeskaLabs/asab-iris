from .abc import NotificationBuilderABC


class NotificationBuilderPush(NotificationBuilderABC):

	def __init__(self, tenant, dest_type, dest_value, msg_body, msg_template):
		super().__init__(tenant, dest_type, dest_value, msg_body, msg_template)
		self.DefaultTemplatesFolder = "/Push/"


	def set_destination(self):
		"""
		Normalize DestinationValue into a single push topic
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
			"type":"push",
			"topic": "tickets",
			"body":{
				"template":"/Templates/Push/XXXX.md",
				"params": {
					"name": "I am testing a template"
				}
			}
		}
		"""
		template_path = self.build_template_path(self.DefaultTemplatesFolder)
		push_notification = {
			"type": self.NotificationType,
			"topic": self.set_destination(),
			"body": {
				"template": template_path,
				"params": self.MessageBody
			}
		}

		return push_notification
