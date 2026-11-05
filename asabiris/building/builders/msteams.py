from .abc import NotificationBuilderABC


class NotificationBuilderMSTeams(NotificationBuilderABC):

	def __init__(self, tenant, dest_type, dest_data, msg_body, msg_template):
		super().__init__(tenant, dest_type, dest_data, msg_body, msg_template)
		self.DefaultTemplatesFolder = "/MSTeams/"


	def build_notification_dict(self):
		"""
		Example of the message structure:
		{
			"type": "msteams",
			"body": {
				"template": "/Templates/MSTeams/XXXX.md",
				"params": {
					"message": "I am testing a template",
					"event": "Iris-Event"
				}
			}
		}
		"""
		template_path = self.build_template_path(self.DefaultTemplatesFolder)
		msteams_notification = {
			"type": self.NotificationType,
			"body": {
				"template": template_path,
				"params": self.MessageBody
			}
		}

		return msteams_notification