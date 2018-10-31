from applications import *

manager = AppsManager()
manager.configure_app(blog_app, 'blog')
manager.configure_app(admin_app, 'admin')
manager.run_all()