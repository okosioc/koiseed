DOMAIN = 'koiseed.com'
SHORT_NAME = 'KoiSeed'
SECRET_KEY = 'FIXME'
#
# Cache
#
CACHE_TYPE = 'SimpleCache'
CACHE_DEFAULT_TIMEOUT = 300
CACHE_THRESHOLD = 10240
#
# Locale
#
ACCEPT_LANGUAGES = ['en', 'zh']
BABEL_DEFAULT_LOCALE = 'zh'
BABEL_DEFAULT_TIMEZONE = 'UTC'
#
# Log
#
DEBUG_LOG = 'logs/debug.log'
ERROR_LOG = 'logs/error.log'
#
# Email
#
# ADMINS is used to receive support emails, e.g, calling logger.error(), or sending support email programmatically
# MAIL_SERVER is None, will not send email, so you need to update it to your own SMTP server, e.g, 'smtp.gmail.com'
# MAIL_USERNAME is used to log in SMTP server, most of the cases it is same as MAIL_DEFAULT_SENDER
# MAIL_DEFAULT_SENDER can be a tuple, e.g, ('KoiSeed Service', 'service@koiseed.com'), the first part is sender's display name
ADMINS = ['FIXME']
MAIL_SERVER = None
MAIL_PORT = 465
MAIL_USE_TLS = False
MAIL_USE_SSL = True
MAIL_USERNAME = 'FIXME'
MAIL_PASSWORD = 'FIXME'
MAIL_DEFAULT_SENDER = 'FIXME'
#
# DB
#
MONGODB_URI = 'mongodb://localhost:27017/koiseed'
MONGODB_URI_PYTEST = 'mongodb://localhost:27017/pytest'
#
# Upload
#
# UPLOAD_ENDPOINT = '//upload.qiniup.com/'
# UPLOAD_BASE = '//cdn.koiseed.com'
# UPLOAD_BUCKET = 'koiseed'
# UPLOAD_AK = 'FIXME'
# UPLOAD_SK = 'FIXME'
# NOTE: we use some invalid mime types just for easy processing, e.g, image/jpg, application/xlsx etc
# common mime types: https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types/Common_types
# UPLOAD_MIMES = [
#     'image/jpg', 'image/jpeg', 'image/png', 'image/gif',
#     'video/quicktime', 'video/mp4', 'video/mpeg', 'video/webm',
#     'audio/mpeg', 'audio/wav', 'audio/webm',
#     'application/pdf',
#     'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/xlsx', 'application/vnd.ms-excel', 'application/xls',
#     'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/docx', 'application/msword', 'application/doc',
# ]
# UPLOAD_MAX = 50
# UPLOAD_IMAGE_PREVIEW = '?imageMogr2/thumbnail/x300'
# UPLOAD_AVATAR_PREVIEW = '?imageView2/1/w/200/h/200'
# UPLOAD_VIDEO_POSTER = '?vframe/jpg/offset/1/h/200'
# Upload to Local
UPLOAD_ENDPOINT = '/upload'
UPLOAD_FOLDER = 'uploads'
UPLOAD_MIMES = [
    'image/jpg', 'image/jpeg', 'image/png', 'image/gif',
    'video/quicktime', 'video/mp4', 'video/mpeg', 'video/webm',
    'audio/mpeg', 'audio/wav', 'audio/webm',
]
UPLOAD_MAX = 50
# starts with _ means inject this thumbnail ops before file extension
# e.g,
# /static/uploads/20200101/xxx.jpg -> /static/uploads/20200101/xxx_thumbnail_x300.jpg
# _thumbnail_<Width>x -> fix width
# _thumbnail_x<Height> -> fix height
# _thumbnail_<Width>x<Height> -> scale to fit
# _thumbnail_!<Width>x<Height> -> scale to fill
# _thumbnail_!<Width>x<Height>c -> scale to fill and crop to center
# _thumbnail_<Width>x<Height>! -> just resize
UPLOAD_IMAGE_PREVIEW = '_thumbnail_x300'
UPLOAD_AVATAR_PREVIEW = '_thumbnail_!200x200c'
# _frame_<Second>_<Width>x<Height> -> get the frame of the video at specified second
UPLOAD_VIDEO_POSTER = '_frame_1_x300'
#
# OpenAI
#
OPENAI_API_KEY = 'FIXME'
# Azure OpenAI
# Keys and endpoint are defined in an Azure resource of OpenAI
# OPENAI_API_KEY = 'FIXME'
# OPENAI_ENDPOINT = 'FIXME'
# Api versions defined in https://learn.microsoft.com/en-us/azure/ai-services/openai/reference#completions
# OPENAI_API_VERSION = '2024-02-15-preview'
