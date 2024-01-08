"""
Module to orchestrate the sending of emails.

This module provides functionality to orchestrate the sending of emails,
including rendering email templates, processing attachments, and sending
emails through an SMTP service.

Classes:
	SendEmailOrchestrator: Orchestrates the sending of emails.
"""
import os
import re
import datetime
import logging
from typing import List, Tuple, Dict

from ..exceptions import PathError, FormatError, Jinja2TemplateUndefinedError
from ..exception_handler import EmailExceptionHandlingStrategy
#

L = logging.getLogger(__name__)

#


class EmailFailsafeManager:
	def __init__(self, smtp_service):
		self.smtp_service = smtp_service

	async def send_error_notification(self, error, email_from, email_to):
		"""
		Send an error notification email.

		Args:
			error: The exception that was raised.
			original_recipients: List of recipients for the original email.
		"""
		error_message, error_subject = self._generate_error_message(str(error))

		await self.smtp_service.send(
			email_from=email_from,
			email_to=email_to,
			email_subject=error_subject,
			body=error_message
		)

	def _generate_error_message(self, specific_error: str) -> Tuple[str, str]:
		timestamp = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
		error_message = (
			"<p>Hello!</p>"
			"<p>We encountered an issue while processing your request:<br><b>{}</b></p>"
			"<p>Please review your input and try again.<p>"
			"<p>Time: {} UTC</p>"
			"<p>Best regards,<br>Your Team</p>").format(specific_error, timestamp)
		return error_message, "Error when generating email"


class SendEmailOrchestrator:
	"""
	A class to orchestrate the sending of emails.

	This class handles rendering email templates, processing attachments, and
	sending emails through an SMTP service.

	"""

	def __init__(self, app):
		"""
		Initialize the SendEmailOrchestrator with necessary services.

		Args:
			app: The application object, used to get services.
		"""
		self.JinjaService = app.get_service("JinjaService")
		self.MarkdownToHTMLService = app.get_service("MarkdownToHTMLService")
		self.AttachmentRenderingService = app.get_service("AttachmentRenderingService")

		self.SmtpService = app.get_service("SmtpService")
		self.EmailFailsafeManager = EmailFailsafeManager(self.SmtpService)
		# Our failsafe manager
		self.EmailExceptionHandlingStrategy = EmailExceptionHandlingStrategy(self.EmailFailsafeManager)


	async def send_email(
		self,
		email_to: List[str],
		body_template: str,
		body_params=None,
		email_from=None,
		email_cc=None,
		email_bcc=None,
		email_subject=None,
		attachments=None,
		caller_context='default'
	):
		"""
		Send an email using specified parameters.
		...
		"""
		try:
			body_params = body_params or {}
			attachments = attachments or []
			email_cc = email_cc or []
			email_bcc = email_bcc or []

			# Rendering the template
			body_html, email_subject_body = await self._render_template(body_template, body_params)

			# If email_subject is not provided or is empty use email_subject_body
			if email_subject is None or email_subject == '':
				email_subject = email_subject_body

			# Processing attachments
			atts_gen = self.AttachmentRenderingService.render_attachment(attachments)

			# Sending the email
			await self.SmtpService.send(
				email_from=email_from,
				email_to=email_to,
				email_cc=email_cc,
				email_bcc=email_bcc,
				email_subject=email_subject,
				body=body_html,
				attachments=atts_gen,
			)
			L.info("Email sent successfully to: {}".format(', '.join(email_to)))

		except Jinja2TemplateUndefinedError as e:
			context = {'context': caller_context,'from_email': email_from, 'to_emails': email_to}
			await self.EmailExceptionHandlingStrategy.handle_exception(e, context)
		except FormatError as e:
			context = {'context': caller_context,'from_email': email_from, 'to_emails': email_to}
			await self.EmailExceptionHandlingStrategy.handle_exception(e, context)
		except PathError as e:
			context = {'context': caller_context,'from_email': email_from, 'to_emails': email_to}
			await self.EmailExceptionHandlingStrategy.handle_exception(e, context)
		except Exception as e:
			L.exception("Error occurred when preparing the email")
			context = {'context': caller_context,'from_email': email_from, 'to_emails': email_to}
			await self.EmailExceptionHandlingStrategy.handle_exception(e, context)

	async def _render_template(self, template: str, params: Dict) -> Tuple[str, str]:
		if not template.startswith('/Templates/Email/'):
			raise PathError(use_case='Email', invalid_path=template)

		jinja_output = await self.JinjaService.format(template, params)

		ext = os.path.splitext(template)[1]
		if ext == '.html':
			return find_subject_in_html(jinja_output)

		elif ext == '.md':
			body, subject = find_subject_in_md(jinja_output)
			body = self.MarkdownToHTMLService.format(body)
			return body, subject

		else:
			raise FormatError(format=ext)


def find_subject_in_html(body):
	regex = r"(<title>(.*)</title>)"
	match = re.search(regex, body)
	if match is None:
		return body, None
	_, subject = match.groups()
	return body, subject


def find_subject_in_md(body):
	if not body.startswith("SUBJECT:"):
		return body, None
	subject = body.split("\n")[0].replace("SUBJECT:", "").lstrip()
	body = "\n".join(body.split("\n")[1:])
	return body, subject
