import base64
import io

from ..formatter.attachments import Attachment


async def prepare_attachments(attachments):
	prepared = []
	async for attachment in attachments:
		content = attachment.Content
		if hasattr(content, "getvalue"):
			content = content.getvalue()
		elif hasattr(content, "read"):
			position = content.tell()
			content.seek(0)
			content = content.read()
			attachment.Content.seek(position)
		prepared.append({
			"content": base64.b64encode(content).decode("ascii"),
			"content_type": attachment.ContentType,
			"filename": attachment.FileName,
			"position": attachment.Position,
		})
	return prepared


async def prepared_attachments(attachments):
	for attachment in attachments:
		yield Attachment(
			Content=io.BytesIO(base64.b64decode(attachment["content"])),
			ContentType=attachment["content_type"],
			FileName=attachment["filename"],
			Position=attachment["position"],
		)
