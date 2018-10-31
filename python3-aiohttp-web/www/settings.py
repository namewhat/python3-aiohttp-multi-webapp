from pathlib import Path

__all__ = ['configure_class']

class Common(dict):
    BASE_DIR = Path(__file__).parent  # 根目录

    SECRET_KEY = r'yoursecretkeyhere'  # secret_key配置
    
    TOKEN_KEY = 'csrf_token'

    ROOT_URLCONF = 'www.urls'  # 根路由配置文件

    TEMPLATES_URL = BASE_DIR / 'templates'  # 模板文件目录

    STATIC_URL = BASE_DIR / 'static'  # 静态文件目录

    REDIS = {  # redis 配置
        'uri': 'redis://root:@127.0.0.1:6379/0',
        'timeout': 60,
    }

    APPS = {  # 已添加的应用
        'blog': {
            'host': '0.0.0.0',
            'port': 8081,
        },
        'admin': {
            'host': '0.0.0.0',
            'port': 8082,
        }
    }

    DATABASES = {  # 数据库配置
        'mysql': {
            'user': 'root',
            'password': '123456',
            'dbname': 'aioweb',
            'host': '127.0.0.1',
            'port': 3306,
            'minsize': 4,
            'maxsize': 10,
            'charset': 'utf8',
        },
        'postgresql': {
            'user': 'root',
            'password': '123456',
            'dbname': 'aioweb',
            'host': '127.0.0.1',
            'port': 5432,
            'minsize': 4,
            'maxsize': 10
        },
        'redis': {
            'uri': 'redis://root:@127.0.0.1:6379/0',
            'minsize': 4,
            'maxsize': 10,
            'timeout': 60,
        }
    }


class Product(Common):
    DEBUG = False
    ENGINE = 'mysql'


class Develop(Common):
    DEBUG = True
    ENGINE = 'mysql'


class Test(Common):
    DEBUG = False
    ENGINE = 'mysql'

# configure_class = Product()
configure_class = Develop()
# configure_class = Test()