from .abc import NotificationBuilderABC


class NotificationBuilderEmail(NotificationBuilderABC):

	def __init__(self, tenant, dest_type, dest_value, msg_body, msg_template):
		super().__init__(tenant, dest_type, dest_value, msg_body, msg_template)
		self.DefaultTemplatesFolder = "/Email/"


	def set_destination(self):
		"""
		Normalize DestinationValue into a list of email addresses
		"""
		if not self.DestinationValue:
			return []

		if isinstance(self.DestinationValue, list):
			return self.DestinationValue

		if isinstance(self.DestinationValue, str):
			return [a.strip() for a in self.DestinationValue.split(",") if a.strip()]

		return list(self.DestinationValue)  # 1 & several as an array


	def build_notification_dict(self):
		"""
		Example of the message structure:
		{
			"type": "email",
			"to": ["example@gmail.com>"],
			"from": "info@teskalabs.com",
			"body":{
				"template":"/Templates/Email/XXXX.md",
				"params":{
					"tenant": "test",
					"name": "Ticket Notification",
					"ticket_id": "TEST-000001"
				}
			}
		}
		https://ndocs.teskalabs.com/logman.io/analyst/email-notifications/
		"""
		template_path = self.build_template_path(self.DefaultTemplatesFolder)
		email_notification = {
			"type": self.NotificationType,
			"to": self.set_destination(),
			"body": {
				"template": template_path,
				"params": self.MessageBody
			}
		}

		return email_notification
