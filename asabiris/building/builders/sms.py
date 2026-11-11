from .abc import NotificationBuilderABC


class NotificationBuilderSMS(NotificationBuilderABC):

	def __init__(self, tenant, dest_type, dest_value, msg_body, msg_template):
		super().__init__(tenant, dest_type, dest_value, msg_body, msg_template)
		self.DefaultTemplatesFolder = "/SMS/"


	def set_destination(self):
		"""
		Normalize DestinationValue into a single phone number string
		"""
		if not self.DestinationValue:
			return ""

		if isinstance(self.DestinationValue, int):
			return str(self.DestinationValue)

		# TODO: asab-iris can take ONE phone number => take the first configured; discard the rest
		if isinstance(self.DestinationValue, list):
			return self.DestinationValue[0]

		return self.DestinationValue.split(",")[0]  # 1 str item


	def build_notification_dict(self):
		"""
		Example of the message structure:
		{
			"type":"sms",
			"phone": "777666555",
			"body":{
				"template":"/Templates/SMS/XXXX.md",
				"params": {
					"name": "I am testing a template"
				}
			}
		}
		"""
		template_path = self.build_template_path(self.DefaultTemplatesFolder)
		sms_notification = {
			"type": self.NotificationType,
			"phone": self.set_destination(),
			"body": {
				"template": template_path,
				"params": self.MessageBody
			}
		}

		return sms_notification
