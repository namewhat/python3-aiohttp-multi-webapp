import when
import base64
import asyncio
import aiohttp_jinja2
import aiohttp_autoreload

from aiohttp import web
from .csrf import CSRFProtect
from jinja2 import FileSystemLoader
from .config import Config
from aioredis import create_redis_pool
from aiohttp.abc import AbstractAccessLogger
from cryptography import fernet
from www.settings import configure_class
from aiohttp_session import setup as session_setup
from aiohttp_session.cookie_storage import EncryptedCookieStorage


class AccessLogger(AbstractAccessLogger):
    LOG_FORMAT = None

    def access_logger(self):
        pass

    def log(self, request, response, time):
        self.logger.info(f'{self.now()} '
                         f'{request.method} '
                         f'{request.method} {request.path} '
                         f'done in {"%.2f" % time}s {response.status}')

    @staticmethod
    def now():
        return when.now().strftime(r'[%Y-%m-%d %H:%M:%S]')


class AppWrapper:
    '''应用初始化

    [description]
    '''

    def __init__(self, loop, app, app_name):
        self.app = app
        self.loop = loop
        self.app_name = app_name
        setattr(self.app, 'config', Config())
        self.app.config.from_object(configure_class)

        # 修改代码时会自动重启
        if self.app.config['DEBUG']:
            aiohttp_autoreload.start()

    def initialize(self, *, path=None, sock=None, shutdown_timeout=60,
                   ssl_context=None, backlog=128, access_log_class=AccessLogger,
                   access_log_format=AccessLogger.LOG_FORMAT,
                   access_log=AccessLogger.access_logger, handle_signals=True,
                   reuse_address=None, reuse_port=None):

        # 初始化模板
        self._initialize_template()
        # 初始化session
        self._initialize_session()
        # 初始化csrf
        self._initialize_csrf()

        self._initialize_runner(handle_signals, access_log_class,
                                access_log_format, access_log)

        sites = []
        try:
            sites.append(web.TCPSite(runner, self.app.config["APPS"][self.app_name]['host'],
                                     self.app.config["APPS"][
                                         self.app_name]['port'],
                                     shutdown_timeout=shutdown_timeout,
                                     ssl_context=ssl_context,
                                     backlog=backlog,
                                     reuse_address=reuse_address,
                                     reuse_port=reuse_port))
            if path is not None:
                if isinstance(path, (str, bytes, bytearray, memoryview)):
                    sites.append(web.UnixSite(runner, path,
                                              shutdown_timeout=shutdown_timeout,
                                              ssl_context=ssl_context,
                                              backlog=backlog))
                else:
                    for p in path:
                        sites.append(web.UnixSite(runner, p,
                                                  shutdown_timeout=shutdown_timeout,
                                                  ssl_context=ssl_context,
                                                  backlog=backlog))
            if sock is not None:
                if not isinstance(sock, Iterable):
                    sites.append(web.SockSite(runner, sock,
                                              shutdown_timeout=shutdown_timeout,
                                              ssl_context=ssl_context,
                                              backlog=backlog))
                else:
                    for s in sock:
                        sites.append(web.SockSite(runner, s,
                                                  shutdown_timeout=shutdown_timeout,
                                                  ssl_context=ssl_context,
                                                  backlog=backlog))
            for site in sites:
                self.loop.run_until_complete(site.start())
        finally:
            self.loop.run_until_complete(runner.cleanup())
            self.show_info()

    def _initialize_template(self):
        # 初始化模板路径
        jinja_env = aiohttp_jinja2.setup(self.app,
                                         loader=FileSystemLoader(str(self.app.config['TEMPLATES_URL'])))
        # 初始化静态资源路径
        self.app.router.add_static(
            '/static', path=self.app.config['STATIC_URL'])
        # 初始化文件资源路径,用于提供源码、素材等资源下载
        self.app.router.add_static(
            '/src', path=self.app.config['STATIC_URL'] / 'src')
        setattr(self.app, 'jinja_env', jinja_env)

    def _initialize_session(self):
        fernet_key = fernet.Fernet.generate_key()
        secret_key = base64.urlsafe_b64decode(fernet_key)
        session_setup(self.app, EncryptedCookieStorage(secret_key))

    def _initialize_csrf(self):
        csrf = CSRFProtect()
        csrf.init_app(self.app)

    def _initialize_runner(self, handle_signals, access_log_class,
                           access_log_format, access_log):
        if asyncio.iscoroutine(self.app):
            self.app = self.loop.run_until_complete(self.app)

        if self.app.config['ENGINE'] == 'mysql':
            self.app.on_startup.append(init_mysql)
        elif self.app.config['ENGINE'] == 'postgressql':
            self.app.on_startup.append(init_pg)
        else:
            raise RuntimeError('Error set ENGINE in www.settings.')
        self.app.on_startup.append(init_redis)

        runner = web.AppRunner(self.app, handle_signals=handle_signals,
                               access_log_class=access_log_class,
                               access_log_format=access_log_format,
                               access_log=access_log)
        self.loop.run_until_complete(runner.setup())

    def shutdown(self):
        self.loop.run_until_complete(self.app.shutdown())

    def cleanup(self):
        self.app.on_cleanup.append(close_db)
        self.app.on_cleanup.append(close_redis)
        self.loop.run_until_complete(self.app.cleanup())

    def show_info(self):
        print(f'{"="*10} '
              f'{self.app_name} '
              f'Running on '
              f'{self.app.config["APPS"][self.app_name]["host"]}:'
              f'{self.app.config["APPS"][self.app_name]["port"]} '
              f'{"="*10}')


class AppsManager:

    def __init__(self, loop=None):
        self.loop = loop if loop else asyncio.get_event_loop()
        self.user_supplied_loop = loop is not None
        self._apps = []  # 应用列表

    def configure_app(self, app, app_name):
        self._apps.append(
            AppWrapper(self.loop, app, app_name))

    def run_all(self):
        try:
            for app in self._apps:
                app.initialize()
                # app.startup()

            try:
                print("(Press CTRL+C to quit)")
                self.loop.run_forever()
            except KeyboardInterrupt as e:
                pass
            finally:
                for app in self._apps:
                    app.shutdown()
        finally:
            for app in self._apps:
                app.cleanup()

        if hasattr(self.loop, 'shutdown_asyncgens'):
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())

        if not self.user_supplied_loop:
            self.loop.close()

async def init_pg(app):
    from aiopg.sa import create_engine
    conf = app.config['DATABASES']['postgressql']
    engine = await create_engine(database=conf['dbname'],
                                 user=conf['user'],
                                 password=conf['password'],
                                 host=conf['host'],
                                 port=conf['port'],
                                 minsize=conf['minsize'],
                                 maxsize=conf['maxsize'])
    setattr(app, 'db', engine)

async def init_mysql(app):
    from aiomysql.sa import create_engine
    conf = app.config['DATABASES']['mysql']
    engine = await create_engine(host=conf['host'],
                                 port=conf['port'],
                                 user=conf['user'],
                                 password=conf['password'],
                                 db=conf['dbname'],
                                 charset=conf['charset'],
                                 minsize=conf['minsize'],
                                 maxsize=conf['maxsize'])
    setattr(app, 'db', engine)


async def init_redis(app):
    import aioredis
    conf = app.config['DATABASES']['redis']
    redis = await aioredis.create_redis_pool(conf['uri'],
                                             minsize=conf['minsize'],
                                             maxsize=conf['maxsize'])
    setattr(app, 'redis', 'redis')

async def close_db(app):
    app.db.close()
    await app.db.wait_closed()

async def close_redis(app):
    app.redis.close()
    await app.redis.wait_closed()
