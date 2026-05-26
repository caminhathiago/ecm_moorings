import os
import sys
from datetime import datetime

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.application import MIMEApplication

from email import encoders
import smtplib
import socket
import pandas as pd

from dotenv import load_dotenv

load_dotenv()

class Email:

    load_dotenv()


    def __init__(self,
                 script_name,
        # buoy,
        # data,
        email: str,
        log_file_path: str = None):

        self.script_name = script_name
        self.email_to = email if isinstance(email, list) else [email]
        self._email_from = os.getenv('EMAIL_FROM')
        self._email_pwd = os.getenv('EMAIL_FROM_APP_PASSWORD')

        # self.buoy = buoy
        # self.data = data
        self.subject = self.create_subject()
        self.content = self.create_content()

        self.log_file_path = log_file_path


    def send(self):

        msg = MIMEMultipart('alternative')
        msg['Subject'] = self.subject
        msg['From'] = self._email_from
        # msg['To'] = self.email_to
        msg['To'] = ', '.join(self.email_to)

        msg.attach(MIMEText(self.content, 'html'))

        if self.log_file_path:
            if isinstance(self.log_file_path, list):
                for log_file_path in self.log_file_path:
                    if os.path.exists(log_file_path):
                        with open(log_file_path, "rb") as log_file:
                            part = MIMEApplication(log_file.read(), Name=os.path.basename(log_file_path))
                            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(log_file_path)}"'
                            msg.attach(part)
            else:
                if os.path.exists(self.log_file_path):
                    with open(self.log_file_path, "rb") as log_file:
                        part = MIMEApplication(log_file.read(), Name=os.path.basename(self.log_file_path))
                        part['Content-Disposition'] = f'attachment; filename="{os.path.basename(self.log_file_path)}"'
                        msg.attach(part)

        try:
            socket.setdefaulttimeout(10)
            server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
            server.ehlo()
            print("Logging into Gmail...")
            server.login(self._email_from, self._email_pwd)
            print(f"Sending email to {', '.join(self.email_to)}...")
            server.sendmail(self._email_from, self.email_to, msg.as_string())
            print("Email sent successfully.")

        except (smtplib.SMTPException, socket.timeout) as e:
            print(f"Error sending email: {e}")

        finally:
            try:
                server.quit()
                print("Closed connection to email server.")
            except NameError:
                print("Server connection was not established.")

    def create_subject(self):
        return f"AODN Pipeline issue | {self.script_name}"

    def create_content(self):

        email_title = f"<h3>Issue with {self.script_name} run</h3>"
        email_content = f"""<p><b>script</b>: {self.script_name}<br />
                            <b>runtime</b>: {datetime.now()}</p>"""

        return f"<html><head></head><body>{email_title}{email_content}</body></html>"