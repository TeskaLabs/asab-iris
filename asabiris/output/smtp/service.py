import email
import email.message
import logging
import re

import asab
import aiosmtplib

from ...output_abc import OutputABC
from ...exceptions import SMTPDeliverError

#

L = logging.getLogger(__name__)

#
asab.Config.add_defaults(
	{
		'smtp': {
			"from": "asab.iris@example.com",
			"host": "",
			"port": "",
			"user": "",
			"password": "",
			"ssl": "no",  # Use TLS/SSL for connection
			"starttls": "yes",  # Use STARTTLS protocol
			"subject": "ASAB Iris email",
			"message_body": "",
		}
	})


class EmailOutputService(asab.Service, OutputABC):
	def __init__(self, app, service_name="SmtpService", config_section_name='smtp'):
		super().__init__(app, service_name)

		self.Host = asab.Config.get(config_section_name, "host")
		if self.Host == "":
			L.warning("SMTP server is not configured, the `host` entry is empty")
		self.Port = asab.Config.get(config_section_name, "port")

		self.SSL = asab.Config.getboolean(config_section_name, "ssl")
		self.StartTLS = asab.Config.getboolean(config_section_name, "starttls")

		self.User = asab.Config.get(config_section_name, "user")
		self.Password = asab.Config.get(config_section_name, "password")

		self.Sender = asab.Config.get(config_section_name, "from")
		self.Subject = asab.Config.get(config_section_name, "subject")

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

		msg['From'] = self.format_sender_info(msg['From'])

		# Add attachments
		for content, content_type, file_name in attachments:
			maintype, subtype = content_type.split('/', 1)
			msg.add_attachment(
				content,
				maintype=maintype,
				subtype=subtype,
				filename=file_name
			)

		# Send the result over SMTP
		try:
			result = await aiosmtplib.send(
				msg,
				sender=sender,
				recipients=email_to + email_cc + email_bcc,
				hostname=self.Host,
				port=int(self.Port) if self.Port != "" else None,
				username=self.User,
				password=self.Password,
				use_tls=self.SSL,
				start_tls=self.StartTLS
			)
		except aiosmtplib.errors.SMTPConnectError as e:
			L.error("Connection failed: {}".format(e), struct_data={"host": self.Host, "port": self.Port})
			raise SMTPDeliverError("SMTP delivery failed")

		except aiosmtplib.errors.SMTPAuthenticationError as e:
			L.exception("Generic error: {}".format(e), struct_data={"host": self.Host})
			raise SMTPDeliverError("SMTP delivery failed")

		except aiosmtplib.errors.SMTPResponseException as e:
			L.error("SMTP Error", struct_data={"message": e.message, "code": e.code, "host": self.Host})
			raise SMTPDeliverError("SMTP delivery failed")

		except aiosmtplib.errors.SMTPServerDisconnected as e:
			L.error("Server disconnected: {}; check the SMTP credentials".format(e), struct_data={"host": self.Host})
			raise SMTPDeliverError("SMTP delivery failed")

		except Exception as e:
			L.error("Generic error: {}; check credentials".format(e), struct_data={"host": self.Host})
			raise SMTPDeliverError("SMTP delivery failed")

		L.log(asab.LOG_NOTICE, "Email sent", struct_data={'result': result[1], "host": self.Host})


	def format_sender_info(self, email_info):
		"""
		Formats the sender's name and email address from the given email_info string.

		Args:
			email_info (str): The email_info string containing the sender's name and email address.

		Returns:
			str: The formatted sender's name and email address, or the email address alone if the sender's name is empty
				or if the input is already in the format "<example@gmail.com>".

		Examples:
			>>> format_sender_info("<John Doe> johndoe@example.com")
			'John Doe <johndoe@example.com>'
			>>> format_sender_info("John Doe <johndoe@example.com>")
			'John Doe <johndoe@example.com>'
			>>> format_sender_info("johndoe@example.com")
			'johndoe@example.com'
		"""
		match = re.match(r"<([^<>]*)>\s*([^<>]*)", email_info)
		if match:
			senders_name = match.group(1).strip()
			senders_email = match.group(2).strip()
			return f"{senders_name} <{senders_email}>"

		if re.match(r".*<.*>.*", email_info):
			return email_info

		if email_info.startswith("<") and email_info.endswith(">"):
			return email_info[1:-1].strip()

		senders = re.split(r'<|>', email_info)
		if len(senders) > 1:
			senders_name = senders[0].strip()
			senders_email = senders[1].strip()
			return f"{senders_name} <{senders_email}>"
		else:
			return senders[0].strip()
