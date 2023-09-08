# -*- coding: utf-8 -*-
"""
    public
    ~~~~~~~~~~~~~~

    Public view.

    :copyright: (c) 2021 by weiminfeng.
    :date: 2023/8/31
"""
import os

from datetime import datetime, timedelta

from flask import Blueprint, render_template, current_app, redirect, request, abort, jsonify, url_for
from flask_babel import gettext as _
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from werkzeug.datastructures import FileStorage
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from wtforms import StringField, PasswordField, BooleanField, HiddenField
from wtforms.validators import DataRequired, Email, EqualTo, Regexp

from core.models import User, UserStatus, UserRole
from www.commons import send_service_mail, auth_permission

public = Blueprint('public', __name__, url_prefix='')


@public.route('/')
@public.route('/index')
def index():
    """ Index page. """
    return render_template('public/index.html')


@public.route('/400')
@public.route('/403')
@public.route('/404')
@public.route('/500')
def error():
    """ Error page. """
    abort(int(request.path.strip('/')))


@public.route('/ack')
def ack():
    """ Ack page. """
    return render_template('public/ack.html')


@public.route('/contact')
def contact():
    """ Contact us. """
    return render_template('public/contact.html')


@public.route('/dashboard')
def dashboard():
    """ User home page. """
    return redirect(url_for('demo.project_dashboard'))


@public.route('/profile')
def profile():
    """ User profile page. """
    return redirect(url_for('demo.user_profile'))


# ----------------------------------------------------------------------------------------------------------------------
# Login/Signup
#

class LoginForm(FlaskForm):
    """ Login form. """
    email = StringField('email', validators=[
        DataRequired(_('Email is required!')),
        Email(_('Invalid email address!'))
    ])
    password = PasswordField('password', validators=[DataRequired(_('Password is required!'))])
    remember = BooleanField('remember')
    next_url = HiddenField('next')


@public.route('/login', methods=('GET', 'POST'))
def login():
    """ Do login. """
    form = LoginForm()
    #
    if form.validate_on_submit():
        em = form.email.data.strip().lower()
        u = User.find_one({'email': em})
        if not u or not check_password_hash(u.password, form.password.data):
            form.email.errors.append(_('Email or password not matched!'))
            return render_template('public/login.html', form=form)
        # Keep the user info in the session using Flask-Login
        login_user(u, remember=form.remember.data)
        # TODO: Validate next url
        next_url = form.next_url.data
        if not next_url:
            next_url = '/'
        return redirect(next_url)
    #
    next_url = request.args.get('next', '')
    form.next_url.data = next_url
    return render_template('public/login.html', form=form)


@public.route('/logout')
@login_required
def logout():
    """ Logout. """
    logout_user()
    return redirect("/")


class SignupForm(FlaskForm):
    """ Signup form. """
    email = StringField('email', validators=[
        DataRequired(_('Email is required!')),
        Email(_('Invalid email address!'))
    ])
    password = PasswordField('password', validators=[
        DataRequired(_('Password is required!')),
        Regexp(r'^(?=.{8,16}$)(?=.*[a-zA-Z])(?=.*[0-9]).*', 0,
               _('Password length should between 8 and 16, and should contains at least one letter and one number!'))
    ])
    repassword = PasswordField('repassword', validators=[
        DataRequired(_('Password is required!')),
        EqualTo('password', _('Password mismatched!'))
    ])
    agree = BooleanField('agree', validators=[DataRequired(_('Please agree our terms and policy!'))])


@public.route('/signup', methods=('GET', 'POST'))
def signup():
    """ Do signup. """
    form = SignupForm()
    #
    if form.validate_on_submit():
        em = form.email.data.strip().lower()
        pwd = form.password.data.strip()
        u = User.find_one({'email': em})
        if u:
            form.email.errors.append(_('This email has already been registered!'))
            return render_template('public/signup.html', form=form)
        # Create user
        u = User()
        u.email = em
        u.password = generate_password_hash(pwd)
        u.name = u.email.split('@')[0]
        u.avatar = url_for('static', filename='img/avatar.jpg')
        count = User.count({})
        # Set first signup user to admin
        if count == 0:
            u.status = UserStatus.NORMAL
            u.roles = [UserRole.MEMBER, UserRole.ADMIN]
            current_app.logger.info('First user, set it to admin')
        else:
            # If mail is configured, need to verify account
            if current_app.config['MAIL_SERVER']:
                u.status = UserStatus.PENDING
            else:
                u.status = UserStatus.NORMAL
            #
            current_app.logger.info('Current number of users is %s' % count)
        #
        u.save()
        current_app.logger.info(f'A new user created {u} with status {u.status}')
        # Keep the user info in the session using Flask-Login
        login_user(u)
        # If user is in pending status, send verify email
        if u.status == UserStatus.PENDING:
            _generate_verify_code(u, 'email')
        elif u.status == UserStatus.NORMAL:
            _send_welcome_email(u)
        #
        return redirect('/')
    #
    return render_template('public/signup.html', form=form)


# TODO: Forget password?

@public.route('/send_verify_email', methods=('POST',))
@auth_permission
def send_verify_email():
    """ Send verify email to check email address is correct. """
    if current_user.status != UserStatus.PENDING:
        return jsonify(error=1, message=_('No need to verify email address for current user!'))
    # Check verify time
    now = datetime.now()
    if current_user.verify_time and now - current_user.verify_time < timedelta(minutes=5):
        return jsonify(error=1, message=_('We have sent the verify email 5 minutes ago, please check your inbox firstly!'))
    #
    _generate_verify_code(current_user, 'email')
    return jsonify(error=0, message=_('Verify email has been sent!'))


def _generate_verify_code(user: User, type_: str):
    """ Genreate a verify code for user. """
    now = datetime.now()
    # Remove starting 14 chars of hash code, i.e, pbkdf2:sha256:
    code = generate_password_hash(user.email + str(now))[14:] + '_' + type_
    if type_ == 'email':
        subject = _('Verify Email Address')
        link = f'verify_email_address?verify_code={code}'
        email = render_template('emails/verify_email_address.html', title=subject, name=user.name, link=link)
    elif type_ == 'forget':
        subject = _('Password Reset')
        link = f'reset_password?verify_code={code}'
        email = render_template('emails/forget_password.html', title=subject, name=user.name, link=link)
    else:
        raise ValueError('Invalid verify type: %s' % type_)
    #
    user.verify_code = code
    user.verify_time = now
    user.save()
    current_app.logger.info(f'Update verify code for user {user.email}: {code}')
    #
    send_service_mail(current_app._get_current_object(), subject, [user.email], email)


def _send_welcome_email(user: User):
    """ Send a welcome email to user. """
    # Add name to subject can reduce the chance of being marked as spa
    subject = _('Welcome to ') + _(current_app.config['SHORT_NAME']) + _(', ') + user.name.capitalize()
    link = ''
    email = render_template('emails/welcome.html', title=subject, name=user.name, link=link)
    send_service_mail(current_app._get_current_object(), subject, [user.email], email)


@public.route('/verify_email_address')
def verify_email_address():
    """ User click the verify link in email. """
    verify_code = request.args.get('verify_code')
    if not verify_code:
        abort(400)
    #
    user = User.find_one({'verify_code': verify_code})
    if not user:
        return render_template('public/ack.html', ack={
            'title': _('Failed!'),
            'content': _('Your verify code is invalid!')
        })
    #
    if user.status != UserStatus.PENDING:
        return render_template('public/ack.html', ack={
            'title': _('Success.'),
            'content': _('Your email address has been verified.')
        })
    #
    now = datetime.now()
    if user.verify_time and now - user.verify_time > timedelta(days=1):
        return render_template('public/ack.html', ack={
            'title': _('Failed!'),
            'content': _('Your verify link has expired!')
        })
    #
    user.status = UserStatus.NORMAL
    user.verify_code = None
    user.verify_time = None
    user.update_time = now
    user.save()
    current_app.logger.info(f'User {user}\'s email address {user.email} has been verified')
    # Send welcome email
    _send_welcome_email(user)
    #
    return render_template('public/ack.html', ack={
        'title': _('Success.'),
        'content': _('Thanks a lot, your email address has been verified!'),
    })


@public.route('/upload', methods=('POST',))
@auth_permission
def upload_file():
    """ Create a simple upload service.

    In production env we should not use python web server to serve static files directly,
    and we alwasys use nginx to serve the static folder, so simply use its sub folder to store upload files.

    It is also suggested to use a storage service to store your files, such us aws s3.
    """
    if 'file' not in request.files:
        abort(400)
    file = request.files['file']
    if not isinstance(file, FileStorage) or '.' not in file.filename:
        abort(400)
    ext = file.filename.rsplit('.', 1)[1].lower()
    mine_exts = [m.split('/')[1] for m in current_app.config['UPLOAD_MIMES']]
    if ext not in mine_exts:
        abort(400)
    #
    filename = secure_filename(file.filename)
    key = '%s/%s/%s' % (current_app.config['UPLOAD_FOLDER'], datetime.now().strftime('%Y%m%d'), filename)
    path = os.path.join(current_app.root_path, 'static', key)
    parent = os.path.dirname(path)
    if not os.path.exists(parent):
        os.makedirs(parent)
    #
    file.save(path)
    return jsonify(key=key, url=url_for('static', filename=key), name=filename)
