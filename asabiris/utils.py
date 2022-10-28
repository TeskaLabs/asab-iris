import re
import logging

#

L = logging.getLogger(__name__)


#


def find_subject_in_html(body):
	regex = r"(<title>(.*)</title>)"
	match = re.search(regex, body)
	if match is None:
		return body, None
	subject_line, subject = match.groups()
	body = body.replace(subject_line, "")
	return body, subject


def find_subject_in_md(body):
	if not body.startswith("SUBJECT:"):
		return body, None
	subject = body.split("\n")[0].replace("SUBJECT:", "").lstrip()
	body = "\n".join(body.split("\n")[1:])
	return body, subject


def normalize_body(body):
	return "<!DOCTYPE html>\n<html lang="'EN'"><body><div>" + body + "</div></body></html>"
