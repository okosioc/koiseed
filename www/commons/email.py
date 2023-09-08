# -*- coding: utf-8 -*-
"""
    notifier
    ~~~~~~~~~~~~~~

    Notifier, which is used to send email/sms notifications.

    :copyright: (c) 2016 by fengweimin.
    :date: 16/8/14
"""
import socket
import smtplib
import traceback

from datetime import datetime
from email.utils import formatdate, formataddr
from logging.handlers import SMTPHandler
from smtplib import SMTPServerDisconnected

from flask import current_app
from flask_mail import Message

from www.extensions import mail
from . import async_exec, retry


@async_exec
def send_service_mail(app, subject, recipients, html, bcc=None):
    """ Async Send emails to business user for notification.

    If you are calling in a request context, you need to pass the real app object:
    e.g,
    - send_service_mail(current_app._get_current_object(), subject, recipients, html)

    NOTE: this method should not be triggered by user directly, if you have to do so, please limit the frequency, or your service email will be in a high risk of being blocked by mail server.
    """
    with app.app_context():
        mail_server = current_app.config['MAIL_SERVER']
        if not mail_server:
            return
        #
        msg = Message(subject, recipients, html=html, bcc=bcc)
        try:
            retry_send(msg)
        except Exception as e:
            current_app.logger.warn('Can not send service email %s to %s, %s' % (subject, recipients, e))


@retry(exceptions=(SMTPServerDisconnected,))
def retry_send(msg):
    """ Retry to send email. """
    # print('Sending ...')
    mail.send(msg)


class SSLSMTPHandler(SMTPHandler):
    """ Add ssl support for SMTPHandler, Only used in logging error. """

    def emit(self, record):
        """
        Emit a record.

        :param record:
        :return:
        """
        self.async_emit(record)

    @async_exec
    def async_emit(self, record):
        """
        Async emit a record.

        :param record:
        :return:
        """
        try:
            self.retry_emit(record)
        except:
            traceback.print_exc()

    @retry(exceptions=(SMTPServerDisconnected,))
    def retry_emit(self, record):
        """
        Retry emit a record.

        :param record:
        :return:
        """
        # print('Emitting ...')
        port = self.mailport
        if not port:
            port = smtplib.SMTP_PORT
        #
        smtp = smtplib.SMTP_SSL(self.mailhost, port)
        msg = self.format(record)
        msg = "From: %s\r\nTo: %s\r\nSubject: %s\r\nDate: %s\r\n\r\n%s" % (
            self.fromaddr,
            ",".join(self.toaddrs),
            self.getSubject(record),
            formatdate(), msg)
        #
        if self.username:
            smtp.login(self.username, self.password)
        #
        smtp.sendmail(self.fromaddr, self.toaddrs, msg)
        smtp.quit()
