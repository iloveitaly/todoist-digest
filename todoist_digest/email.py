import logging
import os
import re
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import urlparse

import backoff
import css_inline
import markdown2

from todoist_digest.templates import render_template
from todoist_digest.util import TEMPLATES_DIRECTORY

from .util import log


def process_markdown(markdown, subject):
    digest_html_content = markdown2.markdown(markdown)

    # render the full html template
    html_content = render_template(
        TEMPLATES_DIRECTORY / "email.jinja",
        {"preheader": "", "title": subject, "content": digest_html_content},
    )

    # html_content = Template(open(str(template_path)).read()).render(
    #     preheader="", title=subject, content=digest_html_content
    # )

    inlined_css = css_inline.inline(html_content)

    # https://stackoverflow.com/questions/28208186/how-to-remove-html-comments-using-regex-in-python
    comments_removed = re.sub("(<!--.*?-->)", "", inlined_css, flags=re.DOTALL)

    return comments_removed


# SSLEOFError was thrown a couple times via resend
@backoff.on_exception(backoff.expo, ssl.SSLEOFError, max_tries=5)
def send_markdown_email(auth_url, markdown_content, subject, to_addresses):
    parsed_url = urlparse(auth_url)
    html_content = process_markdown(markdown_content, subject)

    msg = MIMEMultipart()
    # TODO should be passed down
    msg["From"] = os.environ.get("TODOIST_DIGEST_EMAIL_FROM", parsed_url.username)
    msg["To"] = to_addresses
    msg["Subject"] = subject

    log.info(
        "creating email for '%s', from '%s', content length %i",
        to_addresses,
        parsed_url.username,
        len(markdown_content),
    )

    # this caused the html version to be ignored...
    # msg.attach(MIMEText(markdown_content, "plain"))

    # TODO any sane HTML styling we can setup?
    msg.attach(MIMEText(html_content, "html"))

    with smtplib.SMTP_SSL(parsed_url.hostname, parsed_url.port) as server:
        log.info("Sending email to %s", to_addresses)

        login_result = server.login(parsed_url.username, parsed_url.password)
        log.info("Login result: %s", login_result)
        result = server.send_message(msg)
        log.info("Send result: %s", result)
        server.quit()
