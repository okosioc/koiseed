# -*- coding: utf-8 -*-
"""
    helpers
    ~~~~~~~~~~~~~~

    Helper functions.

    :copyright: (c) 2016 by fengweimin.
    :date: 16/6/11
"""
import os.path
import re
import json
import ffmpeg

from datetime import datetime, timedelta
from typing import Type
from PIL import Image

from flask import abort, request, current_app
from flask_babel import gettext, ngettext


def timesince(dt, default=None):
    """  Returns string representing "time since".

    :param dt:
    :param default:
    :return: e.g. 3 days ago, 5 hours ago etc.
    """
    if default is None:
        default = gettext("just now")

    now = datetime.now()
    diff = now - dt

    years = diff.days // 365
    months = diff.days // 30
    weeks = diff.days // 7
    days = diff.days
    hours = diff.seconds // 3600
    minutes = diff.seconds // 60
    seconds = diff.seconds

    periods = (
        (years, ngettext("%(num)s year", "%(num)s years", num=years)),
        (months, ngettext("%(num)s month", "%(num)s months", num=months)),
        (weeks, ngettext("%(num)s week", "%(num)s weeks", num=weeks)),
        (days, ngettext("%(num)s day", "%(num)s days", num=days)),
        (hours, ngettext("%(num)s hour", "%(num)s hours", num=hours)),
        (minutes, ngettext("%(num)s minute", "%(num)s minutes", num=minutes)),
        (seconds, ngettext("%(num)s second", "%(num)s seconds", num=seconds)),
    )

    for period, trans in periods:
        if period:
            return gettext("%(period)s ago", period=trans)

    return default


def date_str(dt, format_='%Y-%m-%d'):
    """ Show date string in jinja2. """
    return dt.strftime(format_)


def time_str(dt):
    """ Show date time string in jinja2. """
    return dt.strftime('%H:%M:%S')


def datetime_str(dt):
    """ Show date time string in jinja2. """
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def str_datetime(dts):
    """ Convert datetime string to datetine. """
    return datetime.strptime(dts, '%Y-%m-%d %H:%M:%S')


def timedelta_str(seconds):
    """ Show timedelta of seconds, e.g, 100 -> 0:01:40. """
    return str(timedelta(seconds=seconds))


def json_dumps(data, pretty=False):
    """ 序列化json对象.

    pretty=False, 返回无空格以及utf8编码的json字符串, 用于调用api时进行签名.
    pretty=True, 漂亮的打印, 用于日志.
    """
    if pretty:
        return json.dumps(data, indent=2, ensure_ascii=False)
    else:
        return json.dumps(data, separators=(',', ':'), ensure_ascii=False)


def get_id(type_: Type):
    """ Try to get model id from request.args and request.form.  """
    id_ = request.values.get('id')
    if id_:
        try:
            id_ = type_(id_)
        except ValueError:
            abort(400)
    #
    return id_


def generate_image_thumbnail(path):
    """ Generate a thumbnail for given image path. """
    endpoint = current_app.config['UPLOAD_ENDPOINT']
    is_local = re.match(r'^\/[a-z]+', endpoint)
    # Only generate for local upload, as most of the storage services can generate thumbnails by adding suffix to the image url
    # e.g, qiniu uses ?imageMogr2/thumbnail/x300 to generate thumbnails with 300px height
    thumbnail_ops = current_app.config['UPLOAD_IMAGE_PREVIEW']
    if is_local and thumbnail_ops:
        # e.g,
        # /static/uploads/20200101/xxx.jpg -> /static/uploads/20200101/xxx_thumbnail_x300.jpg
        # _thumbnail_<Width>x -> fix width
        # _thumbnail_x<Height> -> fix height
        # _thumbnail_<Width>x<Height> -> outer fit
        # _thumbnail_!<Width>x<Height>r -> inner fit
        # _thumbnail_<Width>x<Height>! -> just resize
        image_mine_exts = [m.split('/')[1] for m in current_app.config['UPLOAD_MIMES'] if m.startswith('image')]
        ext = os.path.splitext(path)[1][1:]  # (xxx, .jpg) -> [1] -> .jpg -> [1:] -> jpg
        if ext.lower() in image_mine_exts:
            match = re.match(r'^_thumbnail_(!?)(\d*)x(\d*)([r!]?)$', thumbnail_ops)
            if not match:
                current_app.logger.error(f'Invalid thumbnail ops {thumbnail_ops}')
                return
            #
            thumbnail_path = path.replace('.' + ext, f'{thumbnail_ops}.{ext}')
            _generate_image_thumbnail(path, thumbnail_path, match.group(1), match.group(2), match.group(3), match.group(4))


def _generate_image_thumbnail(path, thumbnail_path, prefix, target_width, target_height, suffix):
    """ Generate a thumbnail for given image path. """
    with Image.open(path) as image:
        width, height = image.size
        # fix width
        if not target_height:
            target_width = int(target_width)
            target_height = target_width * height // width
        # fix height
        elif not target_width:
            target_height = int(target_height)
            target_width = target_height * width // height
        else:
            target_width, target_height = int(target_width), int(target_height)
            # outer fit
            if not prefix and not suffix:
                ratio = min(target_width / width, target_height / height)
                target_width, target_height = int(width * ratio), int(height * ratio)
            # inner fit
            elif prefix == '!' and suffix == 'r':
                ratio = max(target_width / width, target_height / height)
                target_width, target_height = int(width * ratio), int(height * ratio)
        #
        image.resize((target_width, target_height)).save(thumbnail_path)
        current_app.logger.info(f'Generate thumbnail {target_width}x{target_height} at {thumbnail_path}')


def generate_video_poster(path):
    """ Generate a poster for given video path. """
    endpoint = current_app.config['UPLOAD_ENDPOINT']
    is_local = re.match(r'^\/[a-z]+', endpoint)
    # Only generate for local upload, as most of the storage services can generate posters by adding suffix to the video url
    # e.g, qiniu uses ?vframe/jpg/offset/1/h/200 to generate poster at 1 second and with 300px height
    poster_ops = current_app.config['UPLOAD_VIDEO_POSTER']
    if is_local and poster_ops:
        # e.g,
        # /static/uploads/20200101/xxx.mp4 -> /static/uploads/20200101/xxx_frame_1_x300.jpg
        video_mine_exts = [m.split('/')[1] for m in current_app.config['UPLOAD_MIMES'] if m.startswith('video')]
        ext = os.path.splitext(path)[1][1:]  # (xxx, .mp4) -> [1] -> .mp4 -> [1:] -> mp4
        if ext.lower() in video_mine_exts:
            match = re.match(r'^_frame_([0-9.]*)_(.*)$', poster_ops)
            if not match:
                current_app.logger.warning(f'Invalid video poster ops {poster_ops}')
                return
            #
            second = float(match.group(1))
            thumbnail_ops = match.group(2)
            #
            poster_path = path.replace('.' + ext, f'{poster_ops}.jpg')
            try:
                # 指定时间获取截图, https://ffmpeg.org/ffmpeg-utils.html#time-duration-syntax
                ffmpeg.input(path, ss=second).output(poster_path, vframes=1).run(overwrite_output=True)
            except ffmpeg.Error:
                current_app.logger.exception(f'Failed when generating video poster')
                return
            #
            thumbnail_match = re.match(r'^(!?)(\d*)x(\d*)([r!]?)$', thumbnail_ops)
            if not thumbnail_match:
                current_app.logger.error(f'Invalid thumbnail ops {thumbnail_ops}')
                return
            #
            _generate_image_thumbnail(poster_path, poster_path, thumbnail_match.group(1), thumbnail_match.group(2), thumbnail_match.group(3), thumbnail_match.group(4))
