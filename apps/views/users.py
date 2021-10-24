from sqlalchemy import and_

from flask import Blueprint, jsonify, request
from apps.models.user import User
from exts import db

user = Blueprint('user', __name__, url_prefix='/user')


@user.route('/test', methods=['GET'])
def index():
    print('this is users-bp')
    return 'this is users-bp!'


@user.route('/list_all_users', methods=['GET'])
def list_users():
    users = User.query.all()
    print(users)
    users_output = []
    for cur_user in users:
        users_output.append(cur_user.to_json())
    return jsonify(users_output)


@user.route('/register', methods=['POST'])
def register():
    return_dict = {'statusCode': '200', 'message': 'successful!'}
    name = request.form.get("username", default=None)
    password = request.form.get("password", default=None)
    if name is None or password is None:
        return_dict['message'] = "用户名和密码不能为空"
        return return_dict
    if User.query.filter(User.name == name).first():
        return_dict['message'] = "用户名已被占用，请换一个用户名"
        return return_dict
    new_user = User(name=name, password=password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify(return_dict)


@user.route('/login', methods=['POST'])
def login():
    return_dict = {'statusCode': '200', 'message': '登录成功'}
    name = request.form.get("username", default=None)
    password = request.form.get("password", default=None)
    if name is None or password is None:
        return_dict['message'] = "用户名和密码不能为空"
        return return_dict
    if User.query.filter(and_(User.name == name, User.password == password)).first() is None:
        return_dict['message'] = "用户名不存在或密码错误，请重新登录"
    return jsonify(return_dict)


@user.route('/details/<userid>')
def find_user(userid):
    cur_user = User.query.get(userid)
    return jsonify(cur_user.to_json())
