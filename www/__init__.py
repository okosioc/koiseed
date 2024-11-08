# -*- coding: utf-8 -*-
"""
    __init__.py
    ~~~~~~~~~~~~~~

    Project Init.

    :copyright: (c) 2016 by fengweimin.
    :date: 16/6/11
"""

import logging
import os
import random
import re
import socket
import string
from datetime import datetime
from importlib import import_module
from logging.handlers import SMTPHandler, TimedRotatingFileHandler
from urllib.parse import urlparse, quote as url_quote, urlencode as url_encode

from flask import Flask, request, redirect, jsonify, url_for, render_template, session, has_request_context, abort, current_app, Blueprint
from flask_babel import Babel
from flask_login import LoginManager
from py3seed import ModelJSONProvider, connect, SimpleEnumMeta
from werkzeug.datastructures import MultiDict

from core.models import DemoUser
from www.commons import SSLSMTPHandler, helpers, ListConverter, BSONObjectIdConverter, prepare_demo_data
from www.extensions import mail, cache, qiniu, openai, comfyui
from www.jobs import init_schedule
from www.public import public
from www.blueprints import blueprints

DEFAULT_APP_NAME = 'www'
MODELS_MODULE = import_module('core.models')


def create_www(pytest=False, runscripts=False):
    """ Create www instance. """
    app = Flask(DEFAULT_APP_NAME, instance_relative_config=True)
    # Json provider
    app.json = ModelJSONProvider(app)
    # Url converter
    app.url_map.converters['list'] = ListConverter
    app.url_map.converters['ObjectId'] = BSONObjectIdConverter
    # Whitespace control
    app.jinja_options['trim_blocks'] = True
    app.jinja_options['lstrip_blocks'] = True
    # Config
    app.config.from_object('www.config')
    app.config.from_pyfile('config.py')
    if pytest:
        app.debug = True
        # Use test db
        app.config['MONGODB_URI'] = app.config['MONGODB_URI_PYTEST']
    #
    if runscripts:
        app.debug = True
    # Chain
    configure_logging(app)
    configure_errorhandlers(app)
    configure_py3seed(app)
    configure_ai(app)
    configure_demo(app)
    configure_extensions(app)
    configure_login(app)
    configure_before_handlers(app)
    configure_template_filters(app)
    configure_template_functions(app)
    configure_context_processors(app)
    configure_i18n(app)
    configure_uploads(app)
    if not pytest and not runscripts:  # Do not start schedules during testing
        configure_schedulers(app)
    # Register blueprints
    configure_blueprints(app)
    #
    return app


def configure_extensions(app):
    """ Prepare extensions. """
    mail.init_app(app)
    cache.init_app(app)


def configure_py3seed(app):
    """ Prepare db connection. """
    connect(app.config.get('MONGODB_URI'))


def configure_ai(app):
    """ Prepare ai related components. """
    openai.init_app(app)
    comfyui.init_app(app)


def configure_demo(app):
    """ Prepare demo data. """
    prepare_demo_data()


def configure_login(app):
    """ Prepare login. """
    login_manager = LoginManager(app)

    @login_manager.user_loader
    def load_user(user_id):
        """ Reload the user object from the user ID stored in the session. """
        return DemoUser.find_one(DemoUser.__id_type__(user_id))


def configure_uploads(app):
    """ Configure upload settings. """
    endpoint = app.config['UPLOAD_ENDPOINT']
    is_local = re.match(r'^\/[a-z]+', endpoint)
    is_qiniu = 'qiniu' in endpoint
    upload_max = app.config['UPLOAD_MAX']

    if is_local:
        # https://flask.palletsprojects.com/en/1.1.x/patterns/fileuploads/#improving-uploads
        app.config['MAX_CONTENT_LENGTH'] = upload_max * 1024 * 1024  # Config unit is megabyte
    elif is_qiniu:
        qiniu.init_app(app)

    def get_exts(mimes, prefix=None):
        """ Get exts from mimes. """
        exts = []
        for m in mimes:
            # filter image/* or video/*, etc
            if prefix and not m.startswith(prefix):
                continue
            # filter special mimes, e.g, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/svg+xml
            # these mimes do not contain any ext
            # however, we need to add invalid mimes with correct ext such as application/xlsx, so that file upload control in web page can select those files with .xlsx ext
            if '.' in m or '-' in m or '+' in m:
                continue
            #
            exts.append(m.split('/')[1])
        #
        return exts

    @app.context_processor
    def inject_upload_config():
        """ Can use upload_config directly in template. """
        mimes = app.config['UPLOAD_MIMES']
        image_preview = app.config.get('UPLOAD_IMAGE_PREVIEW', '')
        uc = {
            # Basic
            'endpoint': endpoint,
            'max': f'{upload_max}mb',  # Config unit is megabyte
            # Mimes/Exts
            'mimes': mimes,
            'exts': get_exts(mimes),
            'image_mimes': [m for m in mimes if m.startswith('image')],
            'image_exts': get_exts(mimes, 'image'),
            'video_mimes': [m for m in mimes if m.startswith('video')],
            'video_exts': get_exts(mimes, 'video'),
            # Image/Video operations
            'image_preview': image_preview,
            'avatar_preview': app.config.get('UPLOAD_AVATAR_PREVIEW', ''),
            'video_poster': app.config.get('UPLOAD_VIDEO_POSTER', ''),
            # Params when uploading, changed according to different upload services
            'params': {},
        }
        if is_qiniu:
            uc['params'].update({'token': qiniu.gen_token()})
        #
        return dict(upload_config=uc)


def configure_i18n(app):
    """ 国际化支持. """

    def get_locale():
        """ Guess locale. """
        # 默认是英语, 只有在请求中指定了_locale才会变化
        locale = app.config.get('BABEL_DEFAULT_LOCALE')
        if request:
            # Request a locale and save to session
            rl = request.args.get('_locale')
            if rl:
                accept_languages = app.config.get('ACCEPT_LANGUAGES')
                if rl not in accept_languages:
                    rl = request.accept_languages.best_match(accept_languages)
                # Update session
                session['_locale'] = rl
            # Get locale from session, or return default locale
            locale = session.get('_locale', locale)
        #
        return locale

    Babel(app, locale_selector=get_locale)
    # Use new style gettext, https://jinja.palletsprojects.com/en/3.0.x/extensions/#new-style-gettext
    app.jinja_env.newstyle_gettext = True
    # Support inline gettext by __(), , e.g, <h1>__(Welcome)</h1>, <p>__(This is a paragraph)</p>
    app.jinja_env.add_extension('py3seed.ext.InlineGettext')


def configure_schedulers(app):
    """ Init jobs. """
    init_schedule(app)


def configure_context_processors(app):
    """ Context processors run before the template is rendered and inject new values into the template context. """

    @app.context_processor
    def inject_config():
        """ Can use config directly in template. """
        return dict(config=app.config)

    @app.context_processor
    def inject_debug():
        """ Can use debug directly in template. """
        return dict(debug=app.debug)


def configure_template_filters(app):
    """ 自定义Filter. """

    @app.template_filter()
    def timesince(value):
        """ 显示友好日期. """
        return helpers.timesince(value)

    @app.template_filter()
    def date(value, format_=None):
        """ 显示日期, 默认格式为%Y-%m-%d. """
        if isinstance(value, str):
            return value
        #
        return helpers.date_str(value, format_) if format_ else helpers.date_str(value)

    @app.template_filter()
    def datetime(value):
        """ 显示日期时间. """
        if isinstance(value, str):
            return value
        #
        return helpers.datetime_str(value)

    @app.template_filter()
    def time(value):
        """ 显示时间. """
        if isinstance(value, str):
            return value
        #
        return helpers.time_str(value)

    @app.template_filter()
    def timedelta(value):
        """ 将秒转化为时钟格式. """
        if isinstance(value, str):
            return value
        #
        return helpers.timedelta_str(value)

    @app.template_filter()
    def commas(value):
        """ Add commas to an number. """
        if value is None:
            return ''
        # 打印小数点
        if type(value) is int:
            return '{:,d}'.format(value)
        else:
            return "{:,.2f}".format(value)

    @app.template_filter()
    def keys(value):
        """ Return keys of dict or return first elements from list of tuple. """
        if type(value) is list:  # list of tuple
            return map(lambda x: x[0], value)
        else:
            return value.keys()

    @app.template_filter()
    def values(value):
        """ Return values of dict. """
        return value.values()

    @app.template_filter()
    def items(value):
        """ Return key-value pairs of dict. """
        return value.items()

    @app.template_filter()
    def index(value, element):
        """ Return index of the element, value should be a list. """
        try:
            return value.index(element)
        except ValueError:
            return -1

    @app.template_filter()
    def todict(value):
        """ Convert a list to dict. """
        if isinstance(value, list):
            return {i: v for i, v in enumerate(value)}
        else:
            return {}

    @app.template_filter()
    def urlquote(value, charset='utf-8'):
        """ Url Quote. """
        return url_quote(value, charset)

    @app.template_filter()
    def quote(value):
        """ Add single quote to value if it is str, else return its __str__. """
        if isinstance(value, str):
            return '\'' + value + '\''
        else:
            return str(value)

    @app.template_filter()
    def dirname(value):
        """ Return dir name from a path.
        e.g,
        /foo/bar/ -> /foo/bar
        /foo/bar -> /foo
        """
        return os.path.dirname(value)

    @app.template_filter()
    def basename(value):
        """ Return file name from a path.
        e.g,
        /foo/bar/ -> ''
        /foo/bar -> bar
        """
        return os.path.basename(value)

    @app.template_filter()
    def filename(value):
        """ Return file name from a path, without ext. """
        return os.path.splitext(value)[0]

    @app.template_filter()
    def split(value, separator):
        """ Split a string. """
        return value.split(separator)

    @app.template_filter()
    def path(value):
        """ Return the path part from a url.
        e.g,
        /demo/project-detail?id=1 -> /demo/project-detail
        """
        return value.split('?')[0]

    @app.template_filter()
    def complete(url: str):
        """ 尝试补全一个url, i.e, 分享到微信时候需要完整的地址

        i.e:
        - 图片上传到七牛后地址不带scheme, e.g, //cdn.koiplan.com/20211224/Fovvi2-1jwL2j8pyBJcomk4iz5TJ.jpeg
        """
        # 以//开头的网址会解析域名, 否则会被认为是相对路径
        if url.startswith('//'):
            url += request.scheme + ':'
        #
        o = urlparse(url)
        ret = ''
        if not o.scheme:
            ret += request.scheme + '://'
        if not o.netloc:
            ret += request.host
        if url.startswith('/'):
            ret += url
        else:
            ret += '/' + url
        #
        return ret

    @app.template_filter()
    def tocolor(value: str):
        """ 将字符串转化为颜色代码, e.g, primary, secondary, success, info, danger, warning. """
        if not value:
            return 'secondary'
        #
        if re.match(r'(normal|primary|pending|\w+able)', value, re.IGNORECASE):  # have something to do
            return 'primary'
        elif re.match(r'(active|running|online|success)', value, re.IGNORECASE):  # have something ran succsessfully
            return 'success'
        elif re.match(r'(error|fail\w+|reject\w+|offline|danger)', value, re.IGNORECASE):  # have something ran failed
            return 'danger'
        elif re.match(r'(overdue\w+|warning)', value, re.IGNORECASE):  # have something ran but has warning
            return 'warning'
        else:
            return 'secondary'  # something is done


def configure_template_functions(app):
    """ 自定义函数. """

    @app.template_global()
    def update_full_path(view):
        """ Update current full path, by supporting special commands.

        e.g, if current path is /profile?uid=xxx&tab=password
        view=timeline -> timeline
        view=timeline? -> timeline?uid=xxx&index=0, keeping all queries
        view=timeline?uid -> timeline?uid=xxx, keeping the query with specified key
        """
        target_args = None
        if '?' in view:
            target_path = view[0:view.index('?')]
            needed_keys = view[view.index('?') + 1:].strip()
            if needed_keys:
                needed_keys = needed_keys.split('&')
            #
            current_args = request.args.deepcopy()
            if needed_keys:  # keeping the query with specified key
                target_args = MultiDict()
                for k, v in current_args.items(multi=True):
                    if k in needed_keys:  # case sensitive
                        target_args.add(k, v)
            else:  # keeping all queries
                target_args = current_args
        else:
            target_path = view
        #
        current_path = request.path
        if target_path == '<':
            # Back
            # i.e, pay-wechat -> pay
            if '-' in current_path:
                target_path = current_path[0:current_path.rindex('-')]
        #
        if target_args:
            target_path += '?' + url_encode(target_args)
        #
        return target_path

    @app.template_global()
    def current_query():
        """ Get current query string, as request.query_string returns bytes, which needs to encode manually. """
        args = request.args.copy()
        return url_encode(args)

    @app.template_global()
    def update_query(is_replace=True, **new_values):
        """ Update query string. """
        args = request.args.copy()
        for key, value in new_values.items():
            if value is None:
                pass
            else:
                if is_replace:
                    args[key] = value
                else:
                    args.update({key: value})
        #
        return url_encode(args)

    @app.template_global()
    def new_model(class_name):
        """ 初始化一个BaseModel. """
        if class_name in ['bool', 'int', 'float', 'str', 'datetime']:
            return None
        #
        klazz = getattr(MODELS_MODULE, class_name)
        return klazz()

    @app.template_global()
    def enum_titles(class_name):
        """ 返回枚举的可选项, {value:title}. """
        # 如果为数组则取内部的类型, i.e, List[DemoUserRole]
        inner = re.search(r'List\[([a-zA-Z]+)\]', class_name)
        if inner:
            class_name = inner.group(1)
        #
        klazz = getattr(MODELS_MODULE, class_name)
        if isinstance(klazz, SimpleEnumMeta):
            return klazz.titles
        else:
            return {}

    @app.template_global()
    def randstr(n=10):
        """ 生成长度为n的随机字符串. """
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))

    @app.template_global()
    def current_time():
        """ 返回当前时间. """
        return datetime.now()


def configure_before_handlers(app):
    """ Injection before handling each request. """

    @app.before_request
    def set_device():
        """ Set mobile device. """
        mobile_agents = re.compile('android|fennec|iemobile|iphone|opera (?:mini|mobi)|mobile')
        ua = request.user_agent.string.lower()
        platform = request.user_agent.platform
        request.MOBILE = True if mobile_agents.search(ua) else False
        request.IPHONE = True if platform == 'iphone' else False
        request.ANDROID = True if platform == 'android' else False


def configure_errorhandlers(app):
    """ Register error handlers. """

    @app.errorhandler(400)
    def server_error(error):
        """ 400. """
        err = {
            'status': error.code,
            'title': 'Invalid Request',
            'content': 'Unexpected request received!'
        }
        if request.is_json:
            return jsonify(error=error.code, message='{content}({status})'.format(**err))
        #
        return render_template('public/error.html', error=err), error.code

    @app.errorhandler(401)
    def unauthorized(error):
        """ 401. """
        err = {
            'status': error.code,
            'title': 'Please Login',
            'content': 'Login required!'
        }
        if request.is_json:
            return jsonify(error=error.code, message='{content}({status})'.format(**err))
        #
        return redirect(url_for('public.login', next=request.path))

    @app.errorhandler(403)
    def forbidden(error):
        """ 403. """
        err = {
            'status': error.code,
            'title': 'Permission Denied',
            'content': 'Not allowed or forbidden!'
        }
        if request.is_json:
            return jsonify(error=error.code, message='{content}({status})'.format(**err))
        #
        return render_template('public/error.html', error=err), error.code

    @app.errorhandler(404)
    def page_not_found(error):
        """ 404. """
        err = {
            'status': error.code,
            'title': 'Page Not Found',
            'content': 'The requested URL was not found on this server!'
        }
        if request.is_json:
            return jsonify(error=error.code, message='{content}({status})'.format(**err))
        #
        return render_template('public/error.html', error=err), error.code

    @app.errorhandler(500)
    def server_error(error):
        """ 500. """
        err = {
            'status': error.code,
            'title': 'Internal Server Error',
            'content': 'Unexpected error occurred! Please try again later.'
        }
        if request.is_json:
            return jsonify(error=error.code, message='{content}({status})'.format(**err))
        #
        return render_template('public/error.html', error=err), error.code


def configure_blueprints(app):
    """ Register all the blueprints. """
    # Register public blueprint
    app.register_blueprint(public)
    # Register all other blueprints in www.blueprints
    for bp in blueprints:
        app.register_blueprint(bp)


def configure_logging(app):
    """ Config logging. """
    mail_server = app.config['MAIL_SERVER']
    if mail_server:
        subject = '[Error] %s encountered errors on %s' % (app.config['DOMAIN'], datetime.now().strftime('%Y/%m/%d'))
        hostname = socket.gethostname()
        subject += (' [%s]' % hostname if hostname else '')
        mail_config = [
            (mail_server, app.config['MAIL_PORT']),
            app.config['MAIL_DEFAULT_SENDER'],
            app.config['ADMINS'],
            subject,
            (app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD']),
        ]
        #
        if app.config['MAIL_USE_SSL']:
            mail_handler = SSLSMTPHandler(*mail_config)
        else:
            mail_handler = SMTPHandler(*mail_config)
        # Only send email when app is not in debug mode
        if not app.debug:
            mail_handler.setLevel(logging.ERROR)
            app.logger.addHandler(mail_handler)
    #
    formatter = logging.Formatter(
        '%(asctime)s %(process)d-%(thread)d %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    #
    debug_log = os.path.join(app.root_path, app.config['DEBUG_LOG'])
    debug_file_handler = TimedRotatingFileHandler(debug_log, when='midnight', backupCount=90)
    debug_file_handler.setLevel(logging.DEBUG)
    debug_file_handler.setFormatter(formatter)
    app.logger.addHandler(debug_file_handler)
    #
    error_log = os.path.join(app.root_path, app.config['ERROR_LOG'])
    error_file_handler = TimedRotatingFileHandler(error_log, when='midnight', backupCount=90)
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(formatter)
    app.logger.addHandler(error_file_handler)
    # Set logging level
    if app.debug:
        app.logger.setLevel(logging.DEBUG)
    else:
        app.logger.setLevel(logging.INFO)
