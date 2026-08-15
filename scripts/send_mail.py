#!/usr/bin/env python3
"""Port of the upstream Snakefile send_mail() helper.

Fidelity note: upstream calls client.quit() in a finally block even when
SMTP_SSL() itself raised (client undefined -> NameError); the port keeps
the notification behavior but exits 0 after reporting the failure, so a
failed notification never fails the finished workflow.
"""

import smtplib
import sys
from email.mime.text import MIMEText


def send_mail(subject, content, sender, sender_passwd,
              smtp_server='smtp.qq.com', msg_to="xuzhougeng@163.com"):
    msg = MIMEText(content, 'plain', 'utf-8')

    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = msg_to
    # Send the email via our own SMTP server.
    client = None
    try:
        client = smtplib.SMTP_SSL(smtp_server, smtplib.SMTP_SSL_PORT)
        print("connecting mail server successfully")
        client.login(sender, sender_passwd)
        print("loging mail server successfully")
        client.sendmail(sender, msg_to, msg.as_string())
        print("sending mail successfully")
    except smtplib.SMTPException as e:
        print("unable to send mail, check your SMTP server.", file=sys.stderr)
    finally:
        if client is not None:
            client.quit()


if __name__ == "__main__":
    # argv: subject content sender sender_passwd [mail_to]
    if len(sys.argv) < 5:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    subject, content, sender, sender_passwd = sys.argv[1:5]
    msg_to = sys.argv[5] if len(sys.argv) > 5 else "xuzhougeng@163.com"
    send_mail(subject, content, sender, sender_passwd, msg_to=msg_to)
