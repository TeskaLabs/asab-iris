import asab
import logging
import email
import aiosmtplib
import email.message
import sys

from ...output_abc import OutputABC

#

L = logging.getLogger(__name__)

#
asab.Config.add_defaults(
	{
		'smtp': {
			"from": "",
			"host": "localhost",
			"port": "",
			"user": "",
			"password": "",
			"ssl": "no",  # Use TLS/SSL for connection
			"starttls": "yes",  # Use STARTTLS protocol
			"subject": "ASAB Iris email",
			"message_body": "",
			"file_size": 50 * 1024 * 1024  # 50 MB
		}
	})


class EmailOutputService(asab.Service, OutputABC):
	def __init__(self, app, service_name="SmtpService", config_section_name='smtp'):
		super().__init__(app, service_name)

		self.Sender = asab.Config.get(config_section_name, "from")
		self.SSL = asab.Config.getboolean(config_section_name, "ssl")
		self.StartTLS = asab.Config.getboolean(config_section_name, "starttls")
		self.Host = asab.Config.get(config_section_name, "host")
		self.User = asab.Config.get(config_section_name, "user")
		self.Password = asab.Config.get(config_section_name, "password")
		self.Subject = asab.Config.get(config_section_name, "subject")

		# file size.
		self.FileSize = int(asab.Config.get(config_section_name, "file_size"))

		if len(self.User) == 0:
			self.User = None
			self.Password = None

	async def send(
		self, *,
		email_to,
		body,
		email_cc=[],
		email_bcc=[],
		email_subject=None,
		email_from=None,
		attachments=[]
	):
		"""
		Send an outgoing email with the given parameters.

		:param to: To whom the email is being sent
		:type to: list of strings (email addresses)

		:param body_html: The text of the email.
		:type body_html: str

		Optional Parameters:
		:param attachment:
		:param cc: A list of Cc email addresses.
		:param bcc: A list of Bcc email addresses.
		"""

		# Prepare Message

		msg = email.message.EmailMessage()
		msg.set_content(body, subtype='html')

		if email_to is not None:
			assert (isinstance(email_to, list))
			msg['To'] = ', '.join(email_to)

		if len(email_cc) != 0:
			assert (isinstance(email_cc, list))
			msg['Cc'] = ', '.join(email_cc)

		if email_subject is not None and len(email_subject) > 0:
			msg['Subject'] = email_subject
		else:
			msg['Subject'] = self.Subject

		if email_from is not None and len(email_from) > 0:
			msg['From'] = sender = email_from
		else:
			msg['From'] = sender = self.Sender

		for a in attachments:
			# unpack tuple
			(content, content_type, file_name) = a

			if content_type == "text/html":
				# attach html file
				msg.add_attachment(content, subtype=content_type, filename=file_name)
				# attach text
				msg.add_attachment("Please see the HTML part of this email.", filename="readme.txt")

			elif content_type == "application/pdf":
				# read the whole pdf content
				data = content.read(int(self.FileSize))

				if len(data) > (self.FileSize):
					L.error("PDF size is too large to be sent over email.")
					raise Exception("PDF size is too large to be sent over email.")
				else:
					msg.add_attachment(data, maintype='application', subtype='pdf', filename=file_name)

			elif content_type == "application/octet-stream":
				f_size = sys.getsizeof(a)
				if f_size > int(self.FileSize):
					L.warning("Failed to send email with attachment: file size is too large.")
			else:
				msg.add_attachment(content, maintype='application', subtype='zip', filename=file_name)

		result = await aiosmtplib.send(
			msg,
			sender=sender,
			recipients=email_to + email_cc + email_bcc,
			hostname=self.Host,
			username=self.User,
			password=self.Password,
			use_tls=self.SSL,
			start_tls=self.StartTLS
		)

		L.log(asab.LOG_NOTICE, "Email sent", struct_data={'result': result[1], "host": self.Host})
