import email
import email.message
import base64
import logging
import re
import socket

import asab
import asab.contextvars
import asyncio
import aiosmtplib

from ...output_abc import OutputABC
from ...errors import ASABIrisError, ErrorCode

#

L = logging.getLogger(__name__)


class ProxyConnectError(Exception):
	pass


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
			"validate_certs": "true",  # NEW
			"cert_bundle": "",  # NEW
			"proxy_host": "",
			"proxy_port": "",
			"proxy_user": "",
			"proxy_password": "",
			"proxy_connect_timeout": "10",
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
		self.ValidateCerts = asab.Config.getboolean(config_section_name, "validate_certs", fallback=True)
		self.Cert = asab.Config.get(config_section_name, "cert_bundle", fallback="").strip()
		self.ProxyHost = asab.Config.get(config_section_name, "proxy_host", fallback="").strip()
		self.ProxyPort = asab.Config.get(config_section_name, "proxy_port", fallback="").strip()
		self.ProxyUser = asab.Config.get(config_section_name, "proxy_user", fallback="").strip()
		self.ProxyPassword = asab.Config.get(config_section_name, "proxy_password", fallback="")
		self.ProxyConnectTimeout = asab.Config.getint(config_section_name, "proxy_connect_timeout", fallback=10)
		self.ProxyPortInt = None

		if self.ProxyHost and not self.ProxyPort:
			raise ValueError("SMTP proxy is configured but `proxy_port` is empty")
		if self.ProxyPort and not self.ProxyHost:
			raise ValueError("SMTP proxy is configured but `proxy_host` is empty")
		if self.ProxyPort:
			try:
				self.ProxyPortInt = int(self.ProxyPort)
			except ValueError as e:
				raise ValueError("SMTP proxy `proxy_port` must be an integer: {}".format(str(e)))
			if self.ProxyPortInt < 1 or self.ProxyPortInt > 65535:
				raise ValueError("SMTP proxy `proxy_port` must be in range 1..65535")
		if self.ProxyConnectTimeout <= 0:
			raise ValueError("SMTP proxy `proxy_connect_timeout` must be greater than 0")

		if len(self.User) == 0:
			self.User = None
			self.Password = None

		# Compiled regular expressions as class variables
		self.SenderNameEmailRegex = re.compile(r"<([^<>]*)>\s*([^<>]*)")
		self.AngelBracketRegex = re.compile(r".*<.*>.*")

		# NEW: tenant config accessor (same pattern as SMSOutputService)
		self.TenantConfigService = app.get_service("TenantConfigExtractionService")

	async def send(
		self, *,
		email_to,
		body,
		email_cc=None,
		email_bcc=None,
		email_subject=None,
		email_from=None,
		attachments=None,
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
		try:
			effective_tenant = asab.contextvars.Tenant.get()
		except LookupError:
			effective_tenant = None

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

		# Resolve tenant recipients (no global/default fallback)
		to_list = []
		if effective_tenant:
			tenant_email_cfg = self.TenantConfigService.get_email_config(effective_tenant)
			if isinstance(tenant_email_cfg, dict):
				tenant_to = tenant_email_cfg.get("to") or []
				if isinstance(tenant_to, list):
					to_list = [str(x).strip() for x in tenant_to if str(x).strip()]

		# Prefer tenant list, else body list
		if not to_list:
			to_list = body_to

		# Enforce "no default to"
		if not to_list:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="No recipient emails available (tenant/body).",
				error_i18n_key="No recipients configured for '{{tenant}}'.",
				error_dict={"tenant": effective_tenant or "unspecified"}
			)

		# Parse/normalize resolved recipients once and use for both header and envelope.
		to_recipients = []
		for email_address in to_list:
			_, sender_email = self.format_sender_info(str(email_address))
			if sender_email:
				to_recipients.append(sender_email)

		if not to_recipients:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="No valid recipient emails after normalization.",
				error_i18n_key="No recipients configured for '{{tenant}}'.",
				error_dict={"tenant": effective_tenant or "unspecified"}
			)

		# Prepare Message
		msg = email.message.EmailMessage()
		msg.set_content(body, subtype='html')
		msg['To'] = ', '.join(to_recipients)
		cc_recipients = []
		bcc_recipients = []

		if email_cc:
			assert isinstance(email_cc, list)
			formatted_email_cc = []
			for email_address in email_cc:
				_, sender_email = self.format_sender_info(str(email_address))
				if sender_email:
					formatted_email_cc.append(sender_email)
					cc_recipients.append(sender_email)
			if formatted_email_cc:
				msg['Cc'] = ', '.join(formatted_email_cc)

		if email_bcc is not None:
			assert isinstance(email_bcc, list)
			for email_address in email_bcc:
				_, sender_email = self.format_sender_info(str(email_address))
				if sender_email:
					bcc_recipients.append(sender_email)

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
			proxy_socket = None
			try:
				if self.ProxyHost:
					result = await self._send_via_proxy_smtp_client(
						msg=msg,
						sender=sender,
						recipients=to_recipients + cc_recipients + bcc_recipients
					)
				else:
					result = await aiosmtplib.send(
						msg,
						sender=sender,
						recipients=to_recipients + cc_recipients + bcc_recipients,
						hostname=self.Host,
						port=int(self.Port) if self.Port != "" else None,
						username=self.User,
						password=self.Password,
						use_tls=self.SSL,
						start_tls=self.StartTLS,
						cert_bundle=self.Cert or None,
						validate_certs=self.ValidateCerts
					)
				L.log(asab.LOG_NOTICE, "Email sent", struct_data={'result': result[1], "host": self.Host})
				break  # Email sent successfully, exit the retry loop

			except ProxyConnectError as e:
				L.warning(
					"Proxy connection failed: {}".format(e),
					struct_data={"proxy_host": self.ProxyHost, "proxy_port": self.ProxyPort, "host": self.Host}
				)
				if attempt < retry_attempts - 1:
					L.info("Retrying email send after proxy connection failure, attempt {}".format(attempt + 1))
					await asyncio.sleep(delay)
					continue
				raise ASABIrisError(
					ErrorCode.SMTP_CONNECTION_ERROR,
					tech_message="SMTP proxy connection failed: {}.".format(str(e)),
					error_i18n_key="Could not connect to SMTP for host '{{host}}'.",
					error_dict={
						"host": self.Host,
					}
				)
			except ASABIrisError:
				raise
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
			finally:
				if proxy_socket is not None:
					try:
						proxy_socket.close()
					except OSError:
						pass

	async def _send_via_proxy_smtp_client(self, *, msg, sender, recipients):
		if self.SSL and self.ValidateCerts:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message=(
					"Proxy with implicit TLS and certificate validation is not supported with current SMTP client "
					"version. Use STARTTLS or disable certificate validation."
				),
				error_i18n_key="Unsupported SMTP proxy TLS configuration."
			)

		proxy_socket = await self._connect_via_http_proxy()
		client = None
		try:
			client = aiosmtplib.SMTP(
				sock=proxy_socket,
				hostname=None,
				port=None,
				use_tls=self.SSL,
				start_tls=False,
				validate_certs=self.ValidateCerts,
				cert_bundle=self.Cert or None,
				timeout=self.ProxyConnectTimeout
			)
			await client.connect()

			if self.StartTLS:
				await client.starttls(server_hostname=self.Host)

			if self.User is not None:
				await client.login(self.User, self.Password or "")

			return await client.send_message(msg, sender=sender, recipients=recipients)
		finally:
			if client is not None:
				try:
					await client.quit()
				except Exception:
					pass
			try:
				proxy_socket.close()
			except Exception:
				pass

	def _effective_smtp_port(self):
		if self.Port != "":
			return int(self.Port)
		if self.SSL:
			return 465
		if self.StartTLS:
			return 587
		return 25

	def _proxy_connect_headers(self, target_host, target_port):
		headers = [
			"CONNECT {}:{} HTTP/1.1".format(target_host, target_port),
			"Host: {}:{}".format(target_host, target_port),
		]
		if self.ProxyUser:
			auth_string = "{}:{}".format(self.ProxyUser, self.ProxyPassword)
			encoded = base64.b64encode(auth_string.encode("utf-8")).decode("ascii")
			headers.append("Proxy-Authorization: Basic {}".format(encoded))
		return "\r\n".join(headers) + "\r\n\r\n"

	async def _read_http_headers(self, sock_obj):
		loop = asyncio.get_running_loop()
		buffer = b""
		max_headers_size = 65536
		while b"\r\n\r\n" not in buffer:
			# Read byte-by-byte to avoid consuming bytes from the next protocol (SMTP)
			# that may already be available in the socket buffer after CONNECT headers.
			chunk = await loop.sock_recv(sock_obj, 1)
			if not chunk:
				raise ProxyConnectError("Proxy closed connection before CONNECT response")
			buffer += chunk
			if len(buffer) > max_headers_size:
				raise ProxyConnectError("Proxy CONNECT response headers are too large")
		return buffer.split(b"\r\n\r\n", 1)[0]

	async def _connect_via_http_proxy(self):
		target_host = self.Host
		target_port = self._effective_smtp_port()
		proxy_port = self.ProxyPortInt if self.ProxyPortInt is not None else 0

		sock_obj = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock_obj.setblocking(False)
		loop = asyncio.get_running_loop()

		try:
			await asyncio.wait_for(
				loop.sock_connect(sock_obj, (self.ProxyHost, proxy_port)),
				timeout=self.ProxyConnectTimeout
			)
			request = self._proxy_connect_headers(target_host, target_port).encode("ascii")
			await asyncio.wait_for(
				loop.sock_sendall(sock_obj, request),
				timeout=self.ProxyConnectTimeout
			)
			header_bytes = await asyncio.wait_for(
				self._read_http_headers(sock_obj),
				timeout=self.ProxyConnectTimeout
			)
		except asyncio.TimeoutError:
			sock_obj.close()
			raise ProxyConnectError("Timeout while connecting to proxy {}:{}".format(self.ProxyHost, proxy_port))
		except Exception as e:
			sock_obj.close()
			raise ProxyConnectError(str(e))

		try:
			status_line = header_bytes.split(b"\r\n", 1)[0].decode("iso-8859-1")
			status_code = int(status_line.split(" ", 2)[1])
		except Exception as e:
			sock_obj.close()
			raise ProxyConnectError("Malformed proxy CONNECT response: {}".format(str(e)))

		if status_code != 200:
			sock_obj.close()
			raise ProxyConnectError("Proxy CONNECT failed with status {}".format(status_code))

		return sock_obj

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
