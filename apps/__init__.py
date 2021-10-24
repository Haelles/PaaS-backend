from flask import Flask
import settings
from apps.views.image_control import image_control
from apps.views.users import user
from exts import db


def create_app():
    # 创建flask app 并指定目录
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    # 导入配置文件
    app.config.from_object(settings)
    # 添加数据库扩展
    db.init_app(app)
    # 注册蓝图
    app.register_blueprint(image_control)
    app.register_blueprint(user)
    return app
