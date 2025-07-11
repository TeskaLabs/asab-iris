import os
import re
import datetime
import logging
from typing import List, Tuple, Dict

import asab
from ..errors import ASABIrisError, ErrorCode

L = logging.getLogger(__name__)


class SendEmailOrchestrator:
	"""
	Orchestrates sending emails via SMTP or MS365 based on configuration.
	"""
	def __init__(self, app):
		# Services for templating and attachments
		self.JinjaService = app.get_service("JinjaService")
		self.MarkdownToHTMLService = app.get_service("MarkdownToHTMLService")
		self.AttachmentRenderingService = app.get_service("AttachmentRenderingService")

		# Output services
		self.SmtpService = app.get_service("SmtpService")
		# Use MS365 only if configured on the app
		m365 = getattr(app, "M365EmailOutputService", None)
		self.M365Service = m365 if (m365 and getattr(m365, "is_configured", False)) else None

		# Optional markdown wrapper
		cfg = asab.Config
		if cfg.has_section("email") and cfg.get("email", "markdown_wrapper"):
			self.MarkdownWrapper = cfg.get("email", "markdown_wrapper")
		else:
			self.MarkdownWrapper = None

	async def send_email(
		self,
		email_to: List[str],
		body_template: str,
		body_template_wrapper=None,
		body_params=None,
		email_from=None,
		email_cc=None,
		email_bcc=None,
		email_subject=None,
		attachments=None
	):
		body_params = body_params or {}
		attachments = attachments or []
		email_cc = email_cc or []
		email_bcc = email_bcc or []

		# Render the body and subject
		body_html, rendered_subject = await self._render_template(
			body_template,
			body_params,
			body_template_wrapper or self.MarkdownWrapper
		)
		if not email_subject:
			email_subject = rendered_subject

		# PREFER SMTP if available; only fall back to MS365
		if self.SmtpService is not None:
			atts_gen = self.AttachmentRenderingService.render_attachment(attachments)
			await self.SmtpService.send(
				email_from,
				email_to=email_to,
				email_cc=email_cc,
				email_bcc=email_bcc,
				email_subject=email_subject,
				body=body_html,
				attachments=atts_gen
			)
			L.info("Email sent via SMTP to: {}".format(', '.join(email_to)))

		elif self.M365Service is not None:
			# MS365 path: use same async Attachment generator
			atts_gen = self.AttachmentRenderingService.render_attachment(attachments)
			await self.M365Service.send_email(
				email_from,  # maps to from_recipient
				email_to,  # maps to recipient
				email_subject,  # maps to subject
				body_html,  # maps to body
				"HTML",  # content_type
				atts_gen  # attachments
			)
			L.info("Email sent via MS365 to: {}".format(', '.join(email_to)))


	async def _render_template(
		self,
		template: str,
		params: Dict,
		wrapper=None
	) -> Tuple[str, str]:
		"""
		Render the template (HTML/MD/TXT), apply wrapper, extract subject.

		Returns:
			(html_body, subject)
		"""
		# Ensure correct template location
		if not template.startswith('/Templates/Email/'):
			raise ASABIrisError(
				ErrorCode.INVALID_PATH,
				tech_message="Incorrect template path '{}'. Move templates to '/Templates/Email/'.".format(template),
				error_i18n_key="Incorrect template path '{{incorrect_path}}'. Please move your templates to '/Templates/Email/'.",
				error_dict={"incorrect_path": template}
			)

		rendered = await self.JinjaService.format(template, params)
		ext = os.path.splitext(template)[1].lower()

		if ext == '.html':
			return _extract_subject_html(rendered)
		if ext == '.md':
			body, subject = _extract_subject_md(rendered)
			html_body = self.MarkdownToHTMLService.format(body)
			if wrapper:
				html_body = await self.JinjaService.format(
					wrapper, {"content": html_body}
				)
			else:
				html_body = convert_markdown_to_full_html(html_body)
			return html_body, subject
		if ext == ".txt":
			# 1) Extract raw Markdown + subject
			raw_md, subject = _extract_subject_txt(rendered)

			if wrapper:
				# 2) Convert the Markdown → HTML
				html_inner = self.MarkdownToHTMLService.format(raw_md)

				# 3) Now inject valid HTML into your wrapper
				body = await self.JinjaService.format(
					wrapper,
					{"content": html_inner}
				)
				return body, subject

			# If there is no wrapper, just return plain text (no HTML conversion)
			return raw_md, subject

		raise ASABIrisError(
			ErrorCode.INVALID_FORMAT,
			tech_message="Unsupported template format '{}'".format(ext),
			error_i18n_key="unsupported_format",
			error_dict={"format": ext}
		)


	def _generate_error_message(self, specific_error: str) -> Tuple[str, str]:
		timestamp = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
		error_message = (
			"<p>Hello!</p>"
			"<p>We encountered an issue while processing your request:<br><b>{}</b></p>"
			"<p>Please review your input and try again.<p>"
			"<p>Time: {} UTC</p>"  # Added a <br> here for a new line in HTML
			"<p>Best regards,<br>ASAB Iris</p>"
		).format(
			specific_error,
			timestamp
		)
		return error_message, "Error when generating email"


def _extract_subject_html(html: str) -> Tuple[str, str]:
	match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)
	if match:
		return html, match.group(1)
	return html, None


def _extract_subject_md(text: str) -> Tuple[str, str]:
	if text.startswith("SUBJECT:"):
		parts = text.split("\n", 1)
		subject = parts[0].split(":", 1)[1].strip()
		return (parts[1] if len(parts) > 1 else ""), subject
	return text, None


def _extract_subject_txt(text: str) -> Tuple[str, str]:
	if text.lower().startswith("subject:"):
		parts = text.split("\n", 1)
		subject = parts[0].split(":", 1)[1].strip()
		return (parts[1] if len(parts) > 1 else ""), subject
	return text, None


def convert_markdown_to_full_html(html_text: str) -> str:
	"""
	Convert Markdown text to a full HTML document.

	Args:
		markdown_text (str): Markdown formatted text to be converted.

	Returns:
		str: A complete HTML document string.
	"""
	full_html_document = """
<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="UTF-8">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>Document</title>
</head>
<body>
{content}
</body>
</html>
""".format(content=html_text)
	return full_html_document
