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

    logger.info(
        "creating email for %s, from %s, content length %i",
        to_address,
        parsed_url.username,
        len(markdown_content),
    )

    # this caused the html version to be ignored...
    # msg.attach(MIMEText(markdown_content, "plain"))

    # TODO any sane HTML styling we can setup?
    msg.attach(MIMEText(html_content, "html"))

    with smtplib.SMTP_SSL(parsed_url.hostname, parsed_url.port) as server:
        logger.info("Sending email to %s", to_address)

        login_result = server.login(parsed_url.username, parsed_url.password)
        logger.info("Login result: %s", login_result)
        result = server.send_message(msg)
        logger.info("Send result: %s", result)
        server.quit()
