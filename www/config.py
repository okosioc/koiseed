DOMAIN = 'koiseed.com'
SHORT_NAME = 'KoiSeed'
SECRET_KEY = 'FIXME'
# Cache
CACHE_TYPE = 'SimpleCache'
CACHE_DEFAULT_TIMEOUT = 300
CACHE_THRESHOLD = 10240
# Locale
ACCEPT_LANGUAGES = ['en', 'zh']
BABEL_DEFAULT_LOCALE = 'zh'
BABEL_DEFAULT_TIMEZONE = 'UTC'
# Log
DEBUG_LOG = 'logs/debug.log'
ERROR_LOG = 'logs/error.log'
# Email
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
# DB
MONGODB_URI = 'mongodb://localhost:27017/koiseed'
MONGODB_URI_PYTEST = 'mongodb://localhost:27017/pytest'
# Upload
# UPLOAD_ENDPOINT = '//upload.qiniup.com/'
# UPLOAD_BASE = '//cdn.koiseed.com'
# UPLOAD_BUCKET = 'koiseed'
# UPLOAD_AK = 'FIXME'
# UPLOAD_SK = 'FIXME'
# UPLOAD_MIMES = ['image/jpg', 'image/jpeg', 'image/png', 'image/gif',
#                 'video/quicktime', 'video/mp4', 'video/mpeg', 'video/webm',
#                 'audio/mpeg', 'audio/x-wav', 'audio/webm',
#                 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/vnd.ms-excel']
# UPLOAD_MAX = 50
# UPLOAD_IMAGE_PREVIEW_SM = '?imageMogr2/thumbnail/x200'
# UPLOAD_IMAGE_PREVIEW_MD = '?imageMogr2/thumbnail/600x'
# UPLOAD_VIDEO_POSTER_SM = '?vframe/jpg/offset/1/h/200'
# Upload to Local
UPLOAD_ENDPOINT = '/upload'
UPLOAD_FOLDER = 'uploads'
UPLOAD_MIMES = ['image/jpg', 'image/jpeg', 'image/png', 'image/gif',
                'video/quicktime', 'video/mp4', 'video/mpeg', 'video/webm',
                'audio/mpeg', 'audio/x-wav', 'audio/webm']
UPLOAD_MAX = 50
UPLOAD_IMAGE_PREVIEW_SM = ''
UPLOAD_IMAGE_PREVIEW_MD = ''
UPLOAD_VIDEO_POSTER_SM = ''
