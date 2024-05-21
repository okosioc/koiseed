# -*- coding: utf-8 -*-
"""
    extension.py
    ~~~~~~~~~~~~~~

    Extension reference.

    :copyright: (c) 2016 by fengweimin.
    :date: 16/5/9
"""

from flask_caching import Cache
from flask_mail import Mail

from www.vendors import QiniuSupport, OpenAISupport

__all__ = ['mail', 'cache', 'qiniu', 'openai']

mail = Mail()
cache = Cache()
qiniu = QiniuSupport()
openai = OpenAISupport()
