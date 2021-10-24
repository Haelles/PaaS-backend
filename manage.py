from flask_migrate import Migrate, MigrateCommand
from flask_script import Manager

from apps import create_app
from exts import db
from apps.models import user
# 如果有models文件 一定在上面导入，不然migrates 是识别不到的，就会导入数据库失败

# 创建app
app = create_app()
# 把app加入到manger中
manager = Manager(app=app)

# 添加命令 (数据库相关)
migrate = Migrate(app=app, db=db)
manager.add_command('db', MigrateCommand)

if __name__ == '__main__':
    manager.run()
    # app.run()
