import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import urlparse

import markdown2

logger = logging.getLogger(__name__)


def send_markdown_email(auth_url, markdown_content, subject, to_address):
    parsed_url = urlparse(auth_url)
    html_content = markdown2.markdown(markdown_content)

    msg = MIMEMultipart()
    msg["From"] = parsed_url.username
    msg["To"] = to_address
    msg["Subject"] = subject

    # TODO any sane styling we can setup?
    msg.attach(MIMEText(html_content, "html"))

    with smtplib.SMTP_SSL(parsed_url.hostname, parsed_url.port) as server:
        logger.info("Sending email to %s", to_address)

        server.login(parsed_url.username, parsed_url.password)
        server.send_message(msg)
