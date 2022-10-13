import re
import logging

#

L = logging.getLogger(__name__)


#


def find_subject_in_html(body):
	regex = r"(<title>(.*)</title>)"
	match = re.search(regex, body)
	if match is None:
		return None, body
	subject_line, subject = match.groups()
	body = body.replace(subject_line, "")
	return subject, body


def find_subject_in_md(body):
	if not body.startswith("SUBJECT:"):
		return None, body
	subject = body.split("\n")[0].replace("SUBJECT:", "")
	body = "\n".join(body.split("\n")[1:])
	return subject, body


def normalize_body(body):
	return "<!DOCTYPE html>\n<html lang="'EN'"><body><div>" + body + "</div></body></html>"
