__author__ = 'Azharul'

import os
import smtplib
import traceback
from django.core import mail
from django.conf import settings
from django.template.loader import render_to_string
from email.encoders import encode_base64
from email.utils import formataddr
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

class Emailer(object):
    def __init__(self, **options):
        self.options = options
        self.host = options.get('host') or settings.EMAIL_HOST
        self.port = options.get('port') or settings.EMAIL_PORT
        self.host_user = options.get('host_user') or settings.EMAIL_HOST_USER
        self.host_password = options.get('host_password') or settings.EMAIL_HOST_PASSWORD
        self.sender_name = options.get('sender_name') or settings.EMAIL_SENDER_NAME
        self.template_url = options.get('template_url')
        self.template_context = options.get('context')
        self.subject = options.get('subject','')
        self.to = options.get('to',[])
        self.body = options.get('body')

    def format_body(self):
        if self.template_url:
            body =  render_to_string(self.template_url, self.template_context)
        else:
            body = self.body
        return MIMEText(body, "html")

    def create_smtp_message(self):
        message = MIMEMultipart()
        message['From'] = formataddr((self.sender_name, self.host_user))
        message['To'] = ','.join(self.to)
        message['Subject'] = self.subject
        message.attach(self.format_body())

        # if file_name is not '':
        #     attachment = MIMEBase('application', 'octet-stream')
        #     attachment.set_payload(open(email_.file_path, 'rb').read())
        #     encode_base64(attachment)
        #     attachment.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(email_.file_path))
        #     message.attach(attachment)
        return message

    def smtp_send(self):
        try:
            # email.from_email = host_user
            # file_name = str(email.file_path).split('\\')[-1:][0]
            message = self.create_smtp_message()
            print("next execute......................")
            mail_server = smtplib.SMTP(self.host, self.port)
            mail_server.ehlo()
            mail_server.starttls()
            mail_server.ehlo()
            mail_server.login(self.host_user, self.host_password)
            mail_server.sendmail(self.host_user, self.to, message.as_string())
            mail_server.close()
            print("^^^^^^^^^^^^^^^^^^^^^^^^^ MAIL SEND ^^^^^^^^^^^^^^^^^^")
            return (True, 'send mail')
        except Exception as e:
            print(e)
            print(traceback.format_exc())
            err_status=e
            return (False, err_status)


    def send_mail_smtp(self):

        sent = True
        err_status=' '
        print('.......................inside SEND MAIL SMTP method................................\n')
        try:
            print('send_mail_smtp--- TRY block')
            connection = mail.get_connection()
            print('Got connection...\n')
            with connection._lock:
                connection.open()
                try:
                    sent, err_status = self.smtp_send()
                    print("Sent msg>>>>>>>>>>",sent)

                except Exception as e:
                    err_status=e
                    sent = False
                    print("error msg>>>>>>>>>>",e)
                    print(sent)
                connection.close()
        except Exception as e:
            print(e)
            print(traceback.format_exc())
            err_status=e
            sent = False
        return sent
