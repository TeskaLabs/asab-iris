import os
import re
import datetime
import logging
from typing import Dict, Tuple

import asab

from ..errors import ASABIrisError, ErrorCode

L = logging.getLogger(__name__)


class SendMS365EmailOrchestrator:
	"""
		Prepares email templates (HTML/MD/TXT), extracts subject, applies optional wrappers,
		and delegates sending via the M365EmailOutputService.
	"""

	def __init__(self, app):
		self._jinja_service = app.get_service("JinjaService")
		self._md_to_html = app.get_service("MarkdownToHTMLService")
		self._email_service = app.get_service("M365EmailOutputService")

		# Optional wrapper template
		if "email" in asab.Config.sections() and asab.Config.get("email", "markdown_wrapper"):
			self._wrapper_template = asab.Config.get("email", "markdown_wrapper")
		else:
			self._wrapper_template = None

	async def send_to_m365_email(self, message: Dict) -> Dict:
		"""
		Sends an email via MS365.

		Args:
			message: {
				"from": str,
				"to": str or [str,...],
				"subject": Optional[str],
				"body": {"template": str, "params": Dict}
			}

		Returns:
			{"result": "OK"|"PARTIAL_FAILURE"|"FAILED",
				"sent_to": List[str], "failed_to": List[str]}
		"""
		# Normalize recipients
		raw_recipients = message.get("to")
		if isinstance(raw_recipients, str):
			recipients = [raw_recipients]
		elif isinstance(raw_recipients, (list, tuple)):
			recipients = list(raw_recipients)
		else:
			L.error("Invalid 'to' type: %r", type(raw_recipients))
			return {"result": "FAILED", "error": "'to' must be str or list"}

		if not recipients:
			L.error("No recipients provided")
			return {"result": "FAILED", "error": "No recipients"}

		# Extract message fields
		sender = message.get("from")
		subject = message.get("subject")
		body_info = message.get("body", {})
		template = body_info.get("template")
		params = body_info.get("params", {})

		# Prepare HTML body and subject
		html_body, auto_subject = await self._prepare_body_and_subject(template, params)

		# Send emails
		failed_recipients = []
		for recipient in recipients:
			try:
				await self._email_service.send_email(sender, recipient, subject, html_body)
			except Exception as e:
				L.error("Send to %s failed: %s", recipient, e)
				failed_recipients.append(recipient)

		sent_recipients = [r for r in recipients if r not in failed_recipients]

		# Determine result
		if not failed_recipients:
			result = "OK"
		elif sent_recipients:
			result = "PARTIAL_FAILURE"
		else:
			result = "FAILED"

		return {
			"result": result,
			"sent_to": sent_recipients,
			"failed_to": failed_recipients
		}

	async def _prepare_body_and_subject(self, template: str, params: Dict) -> Tuple[str, str]:
		"""
		Renders the template, treats .md/.txt as Markdown, applies wrapper,
		extracts subject.

		Returns:
			(html_body, subject)
		"""
		if not template.startswith("/Templates/Email/"):
			raise ASABIrisError(
				ErrorCode.INVALID_PATH,
				tech_message="Template path invalid: {}".format(template),
				error_i18n_key="Invalid template path",
				error_dict={"path": template}
			)

		rendered = await self._jinja_service.format(template, params)
		ext = os.path.splitext(template)[1].lower()

		if ext == ".html":
			body, subject = _extract_subject_html(rendered)
		elif ext in (".md", ".txt"):
			# Convert both Markdown and text templates via MarkdownToHTML
			if ext == ".md":
				text_body, subject = _extract_subject_md(rendered)
			else:
				text_body, subject = _extract_subject_txt(rendered)
			body = self._md_to_html.format(text_body)
		else:
			raise ASABIrisError(
				ErrorCode.INVALID_FORMAT,
				tech_message="Unsupported format: {}".format(ext),
				error_i18n_key="Unsupported format",
				error_dict={"format": ext}
			)

		# Apply wrapper or default HTML wrapping
		if self._wrapper_template:
			body = await self._jinja_service.format(self._wrapper_template, {"content": body})
		else:
			body = _convert_to_full_html(body)

		return body, subject


def _extract_subject_html(html: str) -> Tuple[str, str]:
	match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)
	if match:
		return html, match.group(1)
	return html, None


def _extract_subject_md(text: str) -> Tuple[str, str]:
	if text.startswith("SUBJECT:"):
		parts = text.split("\n", 1)
		subject = parts[0].split(":", 1)[1].strip()
		body = parts[1] if len(parts) > 1 else ""
		return body, subject
	return text, None


def _extract_subject_txt(text: str) -> Tuple[str, str]:
	if text.lower().startswith("subject:"):
		parts = text.split("\n", 1)
		subject = parts[0].split(":", 1)[1].strip()
		body = parts[1] if len(parts) > 1 else ""
		return body, subject
	return text, None


def _convert_to_full_html(inner: str) -> str:
	ts = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
	return (
		"<!DOCTYPE html>\n"
		"<html><head><meta charset=\"utf-8\">\n"
		"<title>{title}</title></head>\n"
		"<body>{content}</body></html>"
	).format(title="Message {}".format(ts), content=inner)
