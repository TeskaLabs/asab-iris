class NotificationBuilderABC:

	def __init__(self, tenant, dest_type, dest_value, msg_body, msg_template):
		self.Tenant = tenant
		self.NotificationType = dest_type
		self.DestinationValue = dest_value
		self.MessageBody = msg_body
		self.MessageTemplate = msg_template
		# Some default file in Library with the same name for all notification types?
		self.DefaultTemplate = "Default"


	def build_template_path(self, folder):
		template_path = "/Templates{}{}.md"
		template_name = self.MessageTemplate.get("template")
		if template_name is None or len(template_name) == 0:
			return template_path.format(folder, self.DefaultTemplate)

		return template_path.format(folder, template_name)


	def build_notification_dict(self):
		raise NotImplementedError()