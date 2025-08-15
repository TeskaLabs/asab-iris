import email
import email.message
import logging
import re

import asab
import asyncio
import aiosmtplib

from ...output_abc import OutputABC
from ...errors import ASABIrisError, ErrorCode

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
			"to": ""
		}
	})


class EmailOutputService(asab.Service, OutputABC):
	def __init__(self, app, service_name="SmtpService", config_section_name='smtp'):
		super().__init__(app, service_name)

		self.Host = asab.Config.get(config_section_name, "host")
		if self.Host == "":
			raise ValueError("SMTP server is not configured, the `host` entry is empty")
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

		# Compiled regular expressions as class variables
		self.SenderNameEmailRegex = re.compile(r"<([^<>]*)>\s*([^<>]*)")
		self.AngelBracketRegex = re.compile(r".*<.*>.*")

		# NEW: tenant config accessor (same pattern as SMSOutputService)
		self.ConfigService = app.get_service("TenantConfigExtractionService")

	async def send(
		self, *,
		email_to,
		body,
		email_cc=[],
		email_bcc=[],
		email_subject=None,
		email_from=None,
		attachments=None,
		tenant=None,  # make sure this arg exists
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
		if email_cc is None:
			email_cc = []
		if email_bcc is None:
			email_bcc = []

		# Normalize input body 'email_to' into a list
		if email_to is None:
			body_to = []
		elif isinstance(email_to, list):
			body_to = [str(x).strip() for x in email_to if str(x).strip()]
		else:
			_body_to = str(email_to).strip()
			body_to = [_body_to] if _body_to else []

		if tenant:
			tenant_email_cfg = self.ConfigService.get_email_config(tenant)
			tenant_to = tenant_email_cfg.get("to", []) if isinstance(tenant_email_cfg, dict) else []
			if len(tenant_to) > 0:
				to_list = tenant_to
			elif len(body_to) > 0:
				to_list = body_to
			else:
				to_list = self.DefaultTo
		else:
			# No tenant -> body > global
			to_list = body_to if len(body_to) > 0 else self.DefaultTo

		if len(to_list) == 0:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="No recipient emails available (tenant/body/global).",
				error_i18n_key="No default recipients configured for '{{tenant}}'.",
				error_dict={"tenant": tenant or "global"}
			)

		# Prepare Message
		msg = email.message.EmailMessage()
		msg.set_content(body, subtype='html')

		if email_to is not None:
			assert isinstance(email_to, list)
			formatted_email_to = []
			for email_address in email_to:
				formatted_sender, sender_email = self.format_sender_info(email_address)
				formatted_email_to.append(sender_email)
			msg['To'] = ', '.join(formatted_email_to)

		if email_cc is not None:
			assert isinstance(email_cc, list)
			formatted_email_cc = []
			for email_address in email_cc:
				formatted_sender, sender_email = self.format_sender_info(email_address)
				formatted_email_cc.append(sender_email)
			msg['Cc'] = ', '.join(formatted_email_cc)

		if email_subject is not None and len(email_subject) > 0:
			msg['Subject'] = email_subject
		else:
			msg['Subject'] = self.Subject

		if email_from is not None and len(email_from) > 0:
			formatted_sender, _ = self.format_sender_info(email_from)
			msg['From'] = sender = formatted_sender
		else:
			formatted_sender, _ = self.format_sender_info(self.Sender)
			msg['From'] = sender = formatted_sender

		# Add attachments
		if attachments is not None:
			async for attachment in attachments:
				maintype, subtype = attachment.ContentType.split('/', 1)
				msg.add_attachment(
					attachment.Content.read(),
					maintype=maintype,
					subtype=subtype,
					filename=attachment.FileName
				)

		# Send the email with retry logic
		retry_attempts = 3
		delay = 5  # seconds

		for attempt in range(retry_attempts):
			try:
				result = await aiosmtplib.send(
					msg,
					sender=sender,
					recipients=to_list + (email_cc or []) + (email_bcc or []),
					hostname=self.Host,
					port=int(self.Port) if self.Port != "" else None,
					username=self.User,
					password=self.Password,
					use_tls=self.SSL,
					start_tls=self.StartTLS
				)
				L.log(asab.LOG_NOTICE, "Email sent", struct_data={'result': result[1], "host": self.Host})
				break  # Email sent successfully, exit the retry loop

			except aiosmtplib.errors.SMTPConnectError as e:
				L.warning("Connection failed: {}".format(e), struct_data={"host": self.Host, "port": self.Port})
				if attempt < retry_attempts - 1:
					L.info("Retrying email send after connection failure, attempt {}".format(attempt + 1))
					await asyncio.sleep(delay)
					continue  # Retry the email sending
				raise ASABIrisError(
					ErrorCode.SMTP_CONNECTION_ERROR,
					tech_message="SMTP connection failed: {}.".format(str(e)),
					error_i18n_key="Could not connect to SMTP for host '{{host}}'.",
					error_dict={
						"host": self.Host,
					}
				)
			except aiosmtplib.errors.SMTPAuthenticationError as e:
				L.warning("SMTP error: {}".format(e), struct_data={"host": self.Host})
				raise ASABIrisError(
					ErrorCode.SMTP_AUTHENTICATION_ERROR,
					tech_message="SMTP authentication error: {}.".format(str(e)),
					error_i18n_key="SMTP authentication failed for host '{{host}}'.",
					error_dict={
						"host": self.Host
					}
				)
			except aiosmtplib.errors.SMTPResponseException as e:
				L.warning("SMTP Error", struct_data={"message": e.message, "code": e.code, "host": self.Host})
				if attempt < retry_attempts - 1:
					L.info("Retrying email send after connection failure, attempt {}".format(attempt + 1))
					await asyncio.sleep(delay)
					continue  # Retry the email sending
				raise ASABIrisError(
					ErrorCode.SMTP_RESPONSE_ERROR,
					tech_message="SMTP response exception: Code {}, Message '{}'.".format(e.code, e.message),
					error_i18n_key="SMTP response issue encountered for '{{host}}': Code '{{code}}', Message '{{message}}'.",
					error_dict={
						"message": e.message,
						"code": e.code,
						"host": self.Host
					}
				)
			except aiosmtplib.errors.SMTPServerDisconnected as e:
				L.warning("Server disconnected: {}; check the SMTP credentials".format(e), struct_data={"host": self.Host})
				if attempt < retry_attempts - 1:
					L.info("Retrying email send after connection failure, attempt {}".format(attempt + 1))
					await asyncio.sleep(delay)
					continue  # Retry the email sending
				raise ASABIrisError(
					ErrorCode.SMTP_SERVER_DISCONNECTED,
					tech_message="SMTP server disconnected: {}.".format(str(e)),
					error_i18n_key="The SMTP server for '{{host}}' disconnected unexpectedly.",
					error_dict={
						"host": self.Host
					}
				)
			except aiosmtplib.errors.SMTPTimeoutError as e:
				L.warning("SMTP timeout encountered: {}; check network connectivity or SMTP server status".format(e), struct_data={"host": self.Host})
				if attempt < retry_attempts - 1:
					L.info("Retrying email send after connection failure, attempt {}".format(attempt + 1))
					await asyncio.sleep(delay)
					continue  # Retry the email sending
				raise ASABIrisError(
					ErrorCode.SMTP_TIMEOUT,
					tech_message="SMTP timeout encountered: {}.".format(str(e)),
					error_i18n_key="The SMTP server for '{{host}}' timed out unexpectedly.",
					error_dict={
						"host": self.Host
					}
				)
			except Exception as e:
				L.warning("SMTP error: {}; check credentials".format(e), struct_data={"host": self.Host})
				if attempt < retry_attempts - 1:
					L.info("Retrying email send after connection failure, attempt {}".format(attempt + 1))
					await asyncio.sleep(delay)
					continue  # Retry the email sending
				raise ASABIrisError(
					ErrorCode.SMTP_GENERIC_ERROR,
					tech_message="Generic error occurred: {}.".format(str(e)),
					error_i18n_key="A generic SMTP error occurred for host '{{host}}'.",
					error_dict={
						"host": self.Host
					}
				)

	def format_sender_info(self, email_info):
		"""
		Formats the sender's name and email address from the given email_info string.

		Args:
			email_info (str): The email_info string containing the sender's name and email address.

		Returns:
			tuple: A tuple containing the formatted sender's name and email address, and the email address alone
				if the sender's name is empty or if the input is already in the format "<example@gmail.com>".

		Examples:
			>>> format_sender_info("<John Doe> johndoe@example.com")
			('John Doe <johndoe@example.com>', 'johndoe@example.com')
			>>> format_sender_info("John Doe <johndoe@example.com>")
			('John Doe <johndoe@example.com>', 'johndoe@example.com')
			>>> format_sender_info("johndoe@example.com")
			('johndoe@example.com', 'johndoe@example.com')
		"""
		match = self.SenderNameEmailRegex.match(email_info)
		if match:
			# Case: "<John Doe> johndoe@example.com"
			# Extract sender's name and email address using regex match groups
			senders_name = match.group(1).strip()
			senders_email = match.group(2).strip()
			formatted_sender = "{} <{}>".format(senders_name, senders_email)
			return formatted_sender, senders_email

		if self.AngelBracketRegex.match(email_info):
			# Case: "John Doe <johndoe@example.com>"
			# Split the string using '<' and '>' as delimiters
			senders = re.split(r'<|>', email_info)
			senders_email = senders[1].strip()
			return email_info, senders_email

		if email_info.startswith("<") and email_info.endswith(">"):
			# Case: "<johndoe@example.com>"
			# Remove the enclosing '<' and '>' characters
			email_address = email_info[1:-1].strip()
			return email_address, email_address

		senders = re.split(r'<|>', email_info)
		if len(senders) > 1:
			# Case: "John Doe <johndoe@example.com>"
			senders_name = senders[0].strip()
			senders_email = senders[1].strip()
			formatted_sender = "{} <{}>".format(senders_name, senders_email)
			return formatted_sender, senders_email
		else:
			# Case: "johndoe@example.com"
			email_address = senders[0].strip()
			return email_address, email_address
