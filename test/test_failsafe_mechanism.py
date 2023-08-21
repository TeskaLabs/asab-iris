import pytest
import jinja2
from asabiris.orchestration.sendemail import SendEmailOrchestrator
from asabiris.exceptions import PathError, FormatError

# Mocks
class MockJinjaService:

    async def format(self, template, params):
        if template == "/Templates/Email/fail_template.html":
            raise jinja2.exceptions.TemplateError("Jinja2 Error")
        return "<html><head><title>Test</title></head><body>Test Body</body></html>"


class MockSmtpService:
    def __init__(self):
        self.email_sent = False
        self.email_content = None
        self.attachments = []

    async def send(self, *args, **kwargs):
        self.email_sent = True
        self.email_content = kwargs.get('body', None)
        self.attachments = kwargs.get('attachments', [])
        return True


class MockApp:
    def __init__(self):
        self.config = {
            'JINJA_FAILSAFE_ENABLED': True
        }

    def get_service(self, service_name):
        if service_name == "JinjaService":
            return MockJinjaService()
        if service_name == "SmtpService":
            return MockSmtpService()
        return None

# Tests
@pytest.fixture
def orchestrator():
    app = MockApp()
    return SendEmailOrchestrator(app)

@pytest.mark.asyncio
async def test_valid_template(orchestrator):
    """
    Test if a valid template renders without any errors.
    """
    result, subject = await orchestrator.render("/Templates/Email/valid_template.html", {})
    assert "<html>" in result

@pytest.mark.asyncio
async def test_invalid_path(orchestrator):
    """
    Test if an invalid path raises a PathError.
    """
    with pytest.raises(PathError):
        await orchestrator.render("/Invalid/Path/template.html", {})

@pytest.mark.asyncio
async def test_failsafe_enabled_on_jinja_error(orchestrator):
    """
    Test if the failsafe mechanism is triggered on a Jinja2 error when enabled.
    """
    result, subject = await orchestrator.render("/Templates/Email/fail_template.html", {})
    assert "An error occurred during Jinja2 rendering." in result

@pytest.mark.asyncio
async def test_failsafe_disabled_on_jinja_error(orchestrator):
    """
    Test if a Jinja2 error is raised when the failsafe mechanism is disabled.
    """
    orchestrator.app.config['JINJA_FAILSAFE_ENABLED'] = False
    with pytest.raises(jinja2.exceptions.TemplateError):
        await orchestrator.render("/Templates/Email/fail_template.html", {})

@pytest.mark.asyncio
async def test_md_template(orchestrator):
    """
    Test if a markdown template renders without any errors.
    """
    result, subject = await orchestrator.render("/Templates/Email/template.md", {})
    assert "<html>" in result

@pytest.mark.asyncio
async def test_unknown_format(orchestrator):
    """
    Test if an unknown format raises a FormatError.
    """
    with pytest.raises(FormatError):
        await orchestrator.render("/Templates/Email/template.unknown", {})

@pytest.mark.asyncio
async def test_email_sent_on_jinja_error(orchestrator):
    """
    Test if an email is sent when a Jinja2 error occurs.
    """
    await orchestrator.render("/Templates/Email/fail_template.html", {})
    assert orchestrator.SmtpService.email_sent

@pytest.mark.asyncio
async def test_email_not_sent_on_valid_template(orchestrator):
    """
    Test if no email is sent when a valid template is rendered.
    """
    await orchestrator.render("/Templates/Email/valid_template.html", {})
    assert not orchestrator.SmtpService.email_sent

@pytest.mark.asyncio
async def test_subject_extraction_from_html(orchestrator):
    """
    Test if the subject is correctly extracted from an HTML template.
    """
    _, subject = await orchestrator.render("/Templates/Email/valid_template.html", {})
    assert subject == "Test"

@pytest.mark.asyncio
async def test_subject_extraction_from_md(orchestrator):
    """
    Test if the subject is correctly extracted from a markdown template.
    """
    _, subject = await orchestrator.render("/Templates/Email/template.md", {})
    assert subject == "Test"

@pytest.mark.asyncio
async def test_failsafe_email_content(orchestrator):
    """
    Test if the content of the failsafe email contains the expected error message and input parameters.
    """
    await orchestrator.render("/Templates/Email/fail_template.html", {"key": "value"})
    assert "This error has been caused by an incorrect Jinja2 template." in orchestrator.SmtpService.email_content
    assert "key" in orchestrator.SmtpService.email_content

def test_attachment_filename_generation(orchestrator):
    """
    Test if the filename for an attachment is correctly generated when not provided.
    """
    filename = orchestrator.get_file_name({"format": "pdf"})
    assert filename.startswith("att-")
    assert filename.endswith(".pdf")

def test_attachment_filename_from_dict(orchestrator):
    """
    Test if the filename for an attachment is correctly taken from the provided dictionary.
    """
    filename = orchestrator.get_file_name({"filename": "test.pdf", "format": "pdf"})
    assert filename == "test.pdf"

@pytest.mark.asyncio
async def test_no_attachments(orchestrator):
    """
    Test if no attachments are added when none are provided.
    """
    await orchestrator.send_email(email_to="test@example.com", body_template="/Templates/Email/valid_template.html", body_params={})
    assert not orchestrator.SmtpService.attachments

@pytest.mark.asyncio
async def test_attachment_processing(orchestrator):
    """
    Test if attachments are correctly processed and added.
    """
    await orchestrator.send_email(email_to="test@example.com", body_template="/Templates/Email/valid_template.html", body_params={}, attachments=[{"template": "/Templates/Email/attachment_template.html", "params": {}}])
    assert orchestrator.SmtpService.attachments

@pytest.mark.asyncio
async def test_email_with_cc_and_bcc(orchestrator):
    """
    Test if an email is sent with the provided CC and BCC addresses.
    """
    await orchestrator.send_email(email_to="test@example.com", email_cc=["cc@example.com"], email_bcc=["bcc@example.com"], body_template="/Templates/Email/valid_template.html", body_params={})
    assert orchestrator.SmtpService.email_sent

@pytest.mark.asyncio
async def test_email_with_invalid_format_attachment(orchestrator):
    """
    Test if a FormatError is raised when an attachment with an invalid format is provided.
    """
    with pytest.raises(FormatError):
        await orchestrator.send_email(email_to="test@example.com", body_template="/Templates/Email/valid_template.html", body_params={}, attachments=[{"template": "/Templates/Email/attachment_template.unknown", "params": {}}])
