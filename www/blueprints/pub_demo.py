# -*- coding: utf-8 -*-
"""
    pub_demo
    ~~~~~~~~~~~~~~

    Demo for public pages.

    :copyright: (c) 2021 by weiminfeng.
    :date: 2024/4/25
"""

import os
import re

from datetime import datetime
from bson import ObjectId

from flask import Blueprint, render_template, current_app, redirect, request, abort, jsonify, url_for
from flask_login import current_user
from py3seed import populate_model, populate_search

from core.models import DemoPost, DemoUser, DemoProject, DemoTask, DemoProjectDashboard, DemoTeam
from www.commons import get_id, auth_permission, admin_permission, json_dumps

from core.models import DemoPostStatus
from www.commons import prepare_demo_data, render_template_with_page

pub_demo = Blueprint('pub-demo', __name__, url_prefix='/pub-demo')


@pub_demo.route('/index-basic')
def index_basic():
    """ Index basic page. """
    return render_template_with_page('pub-demo/index-basic.html')


@pub_demo.route('/index-company')
def index_company():
    """ Index company page. """
    return render_template_with_page('pub-demo/index-company.html')


@pub_demo.route('/index-service')
def index_service():
    """ Index service page. """
    return render_template_with_page('pub-demo/index-service.html')


@pub_demo.route('/index-desktop')
def index_desktop():
    """ Index desktop page. """
    return render_template_with_page('pub-demo/index-desktop.html')


@pub_demo.route('/index-mobile')
def index_mobile():
    """ Index mobile page. """
    return render_template_with_page('pub-demo/index-mobile.html')
