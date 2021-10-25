import os

# 项目基础配置
ENV = 'development'  # 是开发模式
DEBUG = True   # 打开debug

#  mysql+驱动://用户名:密码@主机:3306/数据库名
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:@localhost:3306/paas_prac'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# # cookies配置
# SECRET_KEY = '1821'

# 文件上传配置
BASE_DIR = os.path.dirname(__file__)
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'data')

# 设置允许上传的文件类型
ALLOWED_EXTENSIONS = {'zip', 'yaml', 'yml'}
