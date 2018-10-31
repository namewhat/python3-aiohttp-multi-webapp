from .core import web
from itsdangerous import BadData, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import safe_str_cmp
from werkzeug.exceptions import BadRequest

__all__ = ['CSRFProtect']

def generate_csrf(app, secret_key=None, token_key='csrf_token'):
    secret_key = getattr(app.config, 'SECRET_KEY', secret_key)
    field_name = getattr(app.config, 'TOKEN_KEY', token_key)

    async def generate():
        csrf_token = await app.redis.get(field_name)
        if not csrf_token:
            await app.redis.set(field_name, hashlib.sha1(os.urandom(64)).hexdigest())

        s = URLSafeTimedSerializer(secret_key, salt='csrf-token')

        await app.redis.set(field_name, s.dumps(await app.redis.get(field_name)))
        return await app.redis.get(field_name)

    return generate


async def validate_csrf(app, data, secret_key=None, time_limit=None, token_key=None):
    """Check if the given data is a valid CSRF token. This compares the given
    signed token to the one stored in the session.

    :param data: The signed CSRF token to be checked.
    :param secret_key: Used to securely sign the token. Default is
        ``CSRF_SECRET_KEY`` or ``SECRET_KEY``.
    :param time_limit: Number of seconds that the token is valid. Default is
        ``CSRF_TIME_LIMIT`` or 3600 seconds (60 minutes).
    :param token_key: Key where token is stored in session for comparision.
        Default is ``CSRF_FIELD_NAME`` or ``'csrf_token'``.

    :raises ValidationError: Contains the reason that validation failed.

    .. versionchanged:: 0.14
        Raises ``ValidationError`` with a specific error message rather than
        returning ``True`` or ``False``.
    """
    secret_key = getattr(app.config, 'SECRET_KEY', secret_key)
    field_name = getattr(app.config, 'TOKEN_KEY', token_key)
    time_limit = getattr(app.config, 'CSRF_TIME_LIMIT', 3600)
    csrf_token = await app.redis.get(field_name, None)

    if not data:
        raise ValidationError('The CSRF token is missing.')

    if not csrf_token:
        raise ValidationError('The CSRF session token is missing.')

    s = URLSafeTimedSerializer(secret_key, salt='csrf-token')

    try:
        token = s.loads(data, max_age=time_limit)
    except SignatureExpired:
        raise ValidationError('The CSRF token has expired.')
    except BadData:
        raise ValidationError('The CSRF token is invalid.')

    if not safe_str_cmp(csrf_token, token):
        raise ValidationError('The CSRF tokens do not match.')


class CSRFProtect(object):

    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(self.app)

    def init_app(self, app):
        if not self.app:
            self.app = app
        setattr(app, 'csrf', self)
        setattr(app.jinja_env, 'csrf_token', generate_csrf(app))

        app.config.setdefault('CSRF_ENABLED', True)
        app.config.setdefault('CSRF_CHECK_DEFAULT', True)
        app.config['CSRF_METHODS'] = set(app.config.get(
            'CSRF_METHODS', ['POST', 'PUT', 'PATCH', 'DELETE']
        ))
        app.config.setdefault('CSRF_FIELD_NAME', 'csrf_token')
        app.config.setdefault(
            'CSRF_HEADERS', ['X-CSRFToken', 'X-CSRF-Token']
        )
        app.config.setdefault('CSRF_TIME_LIMIT', 3600)
        app.config.setdefault('CSRF_SSL_STRICT', True)

        app.jinja_env.globals['csrf_token'] = generate_csrf

        @web.middleware
        async def csrf_protect(request, handler):
            if not app.config['CSRF_ENABLED']:
                return await handler(request)

            if not app.config['CSRF_CHECK_DEFAULT']:
                return await handler(request)

            if request.method not in app.config['CSRF_METHODS']:
                return await handler(request)

            return await self.protect(request, handler)

        app.middlewares.append(csrf_protect)
    async def protect(self, request, handler):
        if request.method not in app.config['CSRF_METHODS']:
            return

        try:
            await validate_csrf(self.app, await self._get_csrf_token())
        except ValidationError as e:
            logger.info(e.args[0])
            self._error_response(e.args[0])

        if request.is_secure and app.config['CSRF_SSL_STRICT']:
            if not request.referrer:
                self._error_response('The referrer header is missing.')

            good_referrer = 'https://{0}/'.format(request.host)

            if not same_origin(request.referrer, good_referrer):
                self._error_response('The referrer does not match the host.')

        g.csrf_valid = True  # mark this request as CSRF valid

    async def _get_csrf_token(self, request, handler):
        field_name = self.app.config['CSRF_FIELD_NAME']
        form = await request.json()
        csrf_token = form.get(field_name)

        if csrf_token:
            return csrf_token

        for header_name in self.app.config['CSRF_HEADERS']:
            csrf_token = request.headers.get(header_name)

            if csrf_token:
                return csrf_token

        return None

    def _error_response(self, reason):
        raise CSRFError(reason)


class CSRFError(BadRequest):
    """Raise if the client sends invalid CSRF data with the request.

    Generates a 400 Bad Request response with the failure reason by default.
    Customize the response by registering a handler with
    :meth:`flask.Flask.errorhandler`.
    """

    description = 'CSRF validation failed.'
