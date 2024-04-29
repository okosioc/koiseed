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
from flask_login import login_user, logout_user, login_required, current_user
from flask_babel import gettext as _
from flask_wtf import FlaskForm
from werkzeug.datastructures import FileStorage
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from wtforms import StringField, PasswordField, BooleanField, HiddenField
from wtforms.validators import DataRequired, Email, EqualTo, Regexp
from py3seed import populate_search

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
    """ Error page.

    This page will be displayed when the server encounters an error by __init__.py's errorhandler.
    """
    abort(int(request.path.strip('/')))


@public.route('/login')
def login():
    """ Login page.

    This page will be displayed when the user is not logged in by __init__.py's unauthorized errorhandler.
    """
    return redirect(url_for('pub-demo.login'))


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

    NOTE: /upload is used in config.py to set UPLOAD_ENDPOINT, remember to change it if you change this route.
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
