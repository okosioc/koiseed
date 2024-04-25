# -*- coding: utf-8 -*-
"""
    public
    ~~~~~~~~~~~~~~

    Public view.

    :copyright: (c) 2021 by weiminfeng.
    :date: 2023/8/31
"""
import os
import re
import email_validator

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
from py3seed import populate_search

from core.models import User, UserStatus, UserRole, POST_TAGS, PostStatus, Post
from www.commons import get_id, send_service_mail, auth_permission, generate_image_preview, generate_video_poster, render_template_with_page

public = Blueprint('public', __name__, url_prefix='')


@public.route('/')
def index():
    """ Index page. """
    return redirect(url_for('pub-demo.index_basic'))


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


@public.route('/home')
def home():
    """ User home page. """
    return redirect(url_for('demo.project_dashboard'))


@public.route('/profile')
@login_required
def profile():
    """ User profile page. """
    return redirect(url_for('demo.user_profile'))


# ----------------------------------------------------------------------------------------------------------------------
# Login/Signup
# Epic samples for FlaskForm, i.e, implement children form of FlaskForm and define a function to handle both get and post(validate_on_submit) of the form.
#


PASSWORD_REGEX = r'^(?=.{8,16}$)(?=.*[a-zA-Z])(?=.*[0-9]).*'


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
            next_url = '/home'
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
        Regexp(PASSWORD_REGEX, 0, _('Password length should between 8 and 16, and should contains at least one letter and one number!'))
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
        email = form.email.data.strip().lower()
        password = form.password.data.strip()
        user = User.find_one({'email': email})
        if user:
            form.email.errors.append(_('This email has already been registered!'))
            return render_template('public/signup.html', form=form)
        # Create user
        user = User()
        user.email = email
        user.password = generate_password_hash(password)
        user.name = user.email.split('@')[0]
        user.avatar = url_for('static', filename='img/avatar.jpg')
        count = User.count({})
        # Set first signup user to admin
        if count == 0:
            user.status = UserStatus.NORMAL
            user.roles = [UserRole.MEMBER, UserRole.ADMIN]
            current_app.logger.info('First user, set it to admin')
        else:
            # If mail is configured, need to verify account
            if current_app.config['MAIL_SERVER']:
                user.status = UserStatus.PENDING
            else:
                user.status = UserStatus.NORMAL
            #
            current_app.logger.info('Current number of users is %s' % count)
        #
        user.save()
        current_app.logger.info(f'A new user created {user} with status {user.status}')
        # Keep the user info in the session using Flask-Login
        login_user(user)
        # If user is in pending status, send verify email
        if user.status == UserStatus.PENDING:
            _send_verfiy_email(user)
        elif user.status == UserStatus.NORMAL:
            _send_welcome_email(user)
        #
        return redirect('/')
    #
    return render_template('public/signup.html', form=form)


# ----------------------------------------------------------------------------------------------------------------------
# Email Verify/Password Reset/Contact Us
# Classic samples if you do not want to define Form class, and some actions are invoked by ajax.
#

CHECK_CODE_SUFFIX_VERIFY = '_verify'
CHECK_CODE_SUFFIX_RESET = '_reset'


@public.route('/send_verify_email', methods=('POST',))
@auth_permission
def send_verify_email():
    """ Send verify email to check email address is correct. """
    if current_user.status != UserStatus.PENDING:
        return jsonify(error=1, message=_('No need to verify email address for current user!'))
    # Limit frequency
    now = datetime.now()
    if current_user.check_code.endswith(CHECK_CODE_SUFFIX_VERIFY) and now - current_user.check_time < timedelta(minutes=5):
        return jsonify(error=1, message=_('We have sent the verify email 5 minutes ago, please check your inbox firstly!'))
    #
    _send_verfiy_email(current_user)
    return jsonify(error=0, message=_('Verify email has been sent, please check your inbox.'))


def _send_verfiy_email(user: User):
    """ Genreate a check code for verify and send verify email. """
    now = datetime.now()
    # Remove starting 14 chars of hash code, i.e, pbkdf2:sha256: and append _verify to mark the check code type
    code = generate_password_hash(user.email + str(now))[14:] + CHECK_CODE_SUFFIX_VERIFY
    subject = _('Verify Email Address')
    link = f'verify_email?check_code={code}'
    email = render_template('emails/verify_email.html', title=subject, name=user.name, link=link)
    #
    user.check_code = code
    user.check_time = now
    user.save()
    current_app.logger.info(f'Send verify code for user {user.email}: {code}')
    #
    send_service_mail(current_app._get_current_object(), subject, [user.email], email)


@public.route('/verify_email')
def verify_email():
    """ User click the verify link in email. """
    check_code = request.args.get('check_code')
    if not check_code:
        abort(400)
    #
    user = User.find_one({'check_code': check_code})
    if not user:
        return render_template('public/ack.html', ack={
            'title': _('Failed!'),
            'content': _('Your verify link is invalid!')
        })
    #
    if user.status != UserStatus.PENDING:
        return render_template('public/ack.html', ack={
            'title': _('Success.'),
            'content': _('Your email address has been verified.')
        })
    #
    now = datetime.now()
    if user.check_time and now - user.check_time > timedelta(days=1):
        return render_template('public/ack.html', ack={
            'title': _('Failed!'),
            'content': _('Your verify link has expired!')
        })
    #
    user.status = UserStatus.NORMAL
    user.check_code = None
    user.check_time = None
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


def _send_welcome_email(user: User):
    """ Send a welcome email to user. """
    # Add name to subject can reduce the chance of being marked as spa
    subject = _('Welcome to ') + _(current_app.config['SHORT_NAME']) + _(', ') + user.name
    link = ''
    email = render_template('emails/welcome.html', title=subject, name=user.name, link=link)
    send_service_mail(current_app._get_current_object(), subject, [user.email], email)


@public.route('/reset_password', methods=('GET', 'POST'))
def reset_password():
    """ Reset password. """
    now = datetime.now()
    check_code = request.values.get('check_code')
    if not check_code:
        # User click forget password link in login page
        if request.method == 'GET':
            return render_template('public/reset_password.html')
        # User enter email address and click send reset email button
        else:
            email = request.values.get('email').strip().lower()
            try:
                email_validator.validate_email(email, check_deliverability=False)
            except email_validator.EmailNotValidError as e:
                return render_template('public/reset_password.html', form={
                    'email': email,
                    'email_error': _('Invalid email address!')
                })
            #
            user = User.find_one({'email': email})
            if not user or user.status != UserStatus.NORMAL:
                return render_template('public/reset_password.html', form={
                    'email': email,
                    'email_error': _('This email address is not registered or it is in an abnormal status!')
                })
            # Limit frequency
            if user.check_code and user.check_code.endswith(CHECK_CODE_SUFFIX_RESET) and now - user.check_time < timedelta(minutes=5):
                return render_template('public/reset_password.html', form={
                    'email': email,
                    'email_error': _('We have sent the reset email 5 minutes ago, please check your inbox firstly!')
                })
            #
            _send_reset_email(user)
            return render_template('public/ack.html', ack={
                'title': _('Success.'),
                'content': _('Reset email has been sent, please check your inbox.')
            })
    else:
        user = User.find_one({'check_code': check_code})
        if not user:
            return render_template('public/ack.html', ack={
                'title': _('Failed!'),
                'content': _('Your reset link is invalid!')
            })
        # User click reset password link in email
        if request.method == 'GET':
            if user.check_time and now - user.check_time > timedelta(days=1):
                return render_template('public/ack.html', ack={
                    'title': _('Failed!'),
                    'content': _('Your reset link has expired!')
                })
            # Begin to reset password
            return render_template('public/reset_password.html', form={
                'check_code': check_code,
            })
        # User enter new password and the repassword and click submit button
        else:
            password = request.values.get('password').strip()
            repassword = request.values.get('repassword').strip()
            #
            if not re.match(PASSWORD_REGEX, password):
                return render_template('public/reset_password.html', form={
                    'check_code': check_code,
                    'password': password,
                    'password_error': _('Password length should between 8 and 16, and should contains at least one letter and one number!'),
                    'repassword': repassword,
                })
            #
            if password != repassword:
                return render_template('public/reset_password.html', form={
                    'check_code': check_code,
                    'password': password,
                    'repassword': repassword,
                    'repassword_error': _('Password mismatched!')
                })
            #
            user.password = generate_password_hash(password)
            user.check_code = None
            user.check_time = None
            user.update_time = now
            user.save()
            current_app.logger.info(f'User {user}\'s password {user.email} has been reset')
            return render_template('public/ack.html', ack={
                'title': _('Success.'),
                'content': _('Your password has been reset.')
            })


def _send_reset_email(user: User):
    """ Genreate a check code for reset and send reset email. """
    now = datetime.now()
    # Remove starting 14 chars of hash code, i.e, pbkdf2:sha256: and append _reset to mark the check code type
    code = generate_password_hash(user.email + str(now))[14:] + CHECK_CODE_SUFFIX_RESET
    subject = _('Password Reset')
    link = f'reset_password?check_code={code}'
    email = render_template('emails/reset_password.html', title=subject, name=user.name, link=link)
    #
    user.check_code = code
    user.check_time = now
    user.save()
    current_app.logger.info(f'Sent reset code for user {user.email}: {code}')
    #
    send_service_mail(current_app._get_current_object(), subject, [user.email], email)


@public.route('/contact', methods=('GET', 'POST'))
def contact():
    """ Contact us. """
    # Open contact us page
    if request.method == 'GET':
        return render_template('public/contact.html')
    # Send message in contact us page
    else:
        if not current_app.config['ADMINS'] or not current_app.config['MAIL_SERVER']:
            return jsonify(error=1, message=_('We are very sorry that our email service is not ready, please contact us by another way!'))
        #
        if not current_user.is_authenticated:
            return jsonify(error=1, message=_('Please login firstly!'))
        #
        name = request.values.get('name').strip()
        if not name:
            return jsonify(error=1, message=_('Full name is required!'))
        #
        email = request.values.get('email').strip().lower()
        try:
            email_validator.validate_email(email, check_deliverability=False)
        except email_validator.EmailNotValidError as e:
            return jsonify(error=1, message=_('Invalid email address!'))
        #
        message = request.values.get('message').strip()
        if not message:
            return jsonify(error=1, message=_('Message is required!'))
        # Limit frequency
        now = datetime.now()
        if current_user.last_contact_time and now - current_user.last_contact_time < timedelta(minutes=5):
            return jsonify(error=1, message=_('You have sent the message 5 minutes ago, please wait for a while!'))
        #
        current_user.last_contact_time = now
        current_user.save()
        #
        current_app.logger.info(f'User {current_user} leave a contact message: {message}')
        subject = f'New Contact Message from {name}'
        email = render_template('emails/contact_us.html', title=subject, name=name, email=email, message_lines=message.splitlines())
        send_service_mail(current_app._get_current_object(), subject, current_app.config['ADMINS'], email)
        #
        return jsonify(error=0, message=_('Your message has been sent, we will contact you as soon as possible!'))


# ----------------------------------------------------------------------------------------------------------------------
# File Upload
#

@public.route('/upload', methods=('POST',))
@auth_permission
def upload_file():
    """ Create a simple upload service.

    In production env we should not use python web server to serve static files directly,
    and we alwasys use nginx to serve the static folder, so simply use its sub folder to store upload files.

    It is also suggested to use a storage service to store your files, such us aws s3.
    """

    def _abort(_is_editorjs, code):
        if _is_editorjs:
            return jsonify(success=0)
        else:
            abort(code)

    # editorjs' image tool has a special format for response
    # https://github.com/editor-js/image#server-format
    uploader = request.values.get('uploader')
    is_editorjs = True if uploader == 'editorjs' else False
    #
    if 'file' not in request.files:
        _abort(is_editorjs, 400)
    #
    file = request.files['file']
    if not isinstance(file, FileStorage) or '.' not in file.filename:
        _abort(is_editorjs, 400)
    #
    ext = file.filename.rsplit('.', 1)[1].lower()
    type_ = None
    for m in current_app.config['UPLOAD_MIMES']:
        mine_ext = m.split('/')[1]
        if ext == mine_ext:
            type_ = m.split('/')[0]
            break
    #
    if not type_:
        _abort(is_editorjs, 400)
    #
    filename = secure_filename(file.filename)
    token = request.values.get('token')
    if token:
        key = '%s/%s/%s' % (current_app.config['UPLOAD_FOLDER'], token, filename)
    else:
        key = '%s/%s/%s' % (current_app.config['UPLOAD_FOLDER'], datetime.now().strftime('%Y%m%d'), filename)
    #
    path = os.path.join(current_app.root_path, 'static', key)
    parent = os.path.dirname(path)
    if not os.path.exists(parent):
        os.makedirs(parent)
    #
    file.save(path)
    if type_ == 'image':
        ops = request.values.get('ops', None)
        generate_image_preview(path, ops)
    elif type_ == 'video':
        generate_video_poster(path)
    #
    if is_editorjs:
        return jsonify(success=1, file={'url': url_for('static', filename=key)})
    else:
        return jsonify(key=key, url=url_for('static', filename=key), name=filename)


# ----------------------------------------------------------------------------------------------------------------------
# Blog
#

@public.route('/blog')
def blog():
    """ 博客首页. """
    posts_featured = list(Post.find({'status': PostStatus.PUBLISHED, 'featured': True}, sort=[('publish_time', -1)], limit=5))
    posts_latest = list(Post.find({'status': PostStatus.PUBLISHED}, sort=[('publish_time', -1)], limit=5))
    return render_template('public/blog.html', posts_featured=posts_featured, posts_latest=posts_latest, tags=POST_TAGS)


@public.route('/posts')
def posts():
    """ 博客文章列表. """
    page, sort = request.args.get('p', 1, lambda x: int(x) if x.isdigit() else 1), [('create_time', -1)]
    search, condition = populate_search(request.args, Post)
    current_app.logger.info(f'Try to search post by {condition}, sort by {sort}')
    posts_result, pagination = Post.search(condition, page, per_page=9, sort=sort)
    #
    return render_template('public/posts.html', search=search, pagination=pagination, posts_result=posts_result, tags=POST_TAGS)


@public.route('/post')
def post():
    """ 文章页面. """
    id_ = get_id(Post.__id_type__)
    post_ = Post.find_one(id_)
    if not post_:
        abort(404)
    #
    return render_template('public/post.html', post=post_, tags=POST_TAGS)
