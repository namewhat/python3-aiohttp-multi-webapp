from .blog import blog_app
from .admin import admin_app
from .libs.core import AppsManager

__all__ = ['AppsManager', 'blog_app', 'admin_app']