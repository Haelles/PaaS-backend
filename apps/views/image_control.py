import base64
import json
import os
import zipfile
import random

import flask
from docker import errors
from flask import send_from_directory, Flask, request, Blueprint, current_app

import docker
from sqlalchemy import and_

from apps.models.user import User, UserImages
from exts import db

image_control = Blueprint('image', __name__, url_prefix='/image')


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in current_app.config.get('ALLOWED_EXTENSIONS')


@image_control.route('/test')
def test():
    print('this is image_control-bp, route is /image')
    return 'this is image_control-bp, route is /image'


# 修改镜像的tag
@image_control.route('/tag_image', methods=['POST'])
def tag_image():
    return_dict = {'statusCode': '200', 'message': 'successful!'}
    username = request.form.get('username')
    # 偷懒，设定用户输入的tag只包含tag，`docker images`得到的REPOSITORY固定取username
    old_tag = request.form.get('oldtag')
    new_tag = request.form.get('newtag')
    if username is None or new_tag is None or old_tag is None:
        return_dict['message'] = "username、oldtag、newtag都不能为空"
        return flask.jsonify(return_dict)

    cur_user = User.query.filter(User.name == username).first()
    if cur_user is None:
        return_dict['message'] = "用户名不存在"
        return flask.jsonify(return_dict)

    old_tag = cur_user.name + ":" + old_tag
    new_tag = cur_user.name + ":" + new_tag

    client = docker.DockerClient(base_url='unix://var/run/docker.sock')
    image = client.images.get(old_tag)

    if UserImages.query.filter(UserImages.image_tag == old_tag).first() is None:
        return_dict['message'] = "找不到镜像，请检查tag是否有误"
        return flask.jsonify(return_dict)

    if UserImages.query.filter(UserImages.image_tag == new_tag).first() is not None:
        return_dict['message'] = "这个tag已被使用过，请换一个"
        return flask.jsonify(return_dict)

    try:
        # 修改镜像tag
        for tag in image.tags:
            print(tag)
        image.tag(new_tag)
        print("------")
        for tag in image.tags:
            print(tag)
        image.tag(new_tag)
        # 修改mysql表中的tag
        user_image = UserImages.query.filter(UserImages.image_tag == old_tag).first()
        user_image.image_tag = new_tag
        db.session.commit()
        return_dict["info"] = {"userId": cur_user.id, "imageId": user_image.id, "imageTag": new_tag}
    except docker.errors.ImageNotFound:
        return_dict['message'] = "找不到该镜像，请重新检查tag"
    except docker.errors.APIError:
        return_dict['message'] = "docker.errors.APIError: the server returns an error"
    finally:
        return flask.jsonify(return_dict)


# 查看某个用户的全部镜像
@image_control.route('/list_all_my_images', methods=['POST'])
def list_all_my_image():
    return_dict = {'statusCode': '200', 'message': 'successful!'}
    username = request.form.get('username')
    cur_user = User.query.filter(User.name == username).first()
    if cur_user is None:
        return_dict['message'] = "用户不存在，请检查用户名"
        return flask.jsonify(return_dict)
    search_res = UserImages.query.filter(UserImages.user_id == cur_user.id).all()
    res_list = []
    if len(search_res) == 0:
        return_dict['message'] = "用户拥有的镜像数为0"
    for res in search_res:
        res_list.append(res.to_json())
    return_dict['images'] = res_list
    return flask.jsonify(return_dict)


# 上传一个包含Dockerfile的zip文件，进行解压和build
@image_control.route('/upload_image', methods=['POST'])
def upload_image():
    return_dict = {'statusCode': '200', 'message': 'successful!'}
    username = request.form.get('username')
    if 'file' not in request.files or username is None:
        return_dict['message'] = "出错，缺少文件或用户名为空"
        return flask.jsonify(return_dict)
    file = request.files.get('file')
    if file is None or file.filename == '':
        return_dict['message'] = "出错，文件和文件名不能为空"
        return return_dict
    if file and allowed_file(file.filename):
        filename = file.filename
        # data是上传文件的根目录
        # user_path如./data/username，zip文件存在这个路径下面
        user_path = os.path.join(current_app.config.get('UPLOAD_FOLDER'), username)
        # 对某个解压的zip文件如test.zip，解压文件存储在./data/username/test/下面
        random_int = random.randint(0, 150)
        file_path = os.path.join(user_path, filename.rsplit('.', 1)[-2] + str(random_int))
        if not os.path.exists(user_path):
            os.makedirs(user_path)
        # 存储文件，尝试解压
        file.save(os.path.join(user_path, str(random_int) + filename))
        with zipfile.ZipFile(file, mode='r') as zf:
            zf.extractall(file_path)

        # 开始build
        tag = request.form.get('tag')
        # 偷懒的写法，限制镜像tag格式为"用户名:用户输入的tag"
        if tag is None or ':' in tag:
            return_dict['message'] = "镜像build失败，tag不能为空，且tag需要是一个不含':'的字符串"
            return flask.jsonify(return_dict)
        cur_user = User.query.filter(User.name == username).first()
        tag = cur_user.name + ':' + tag

        # 限制镜像tag不能与已有的重复
        if UserImages.query.filter(and_(UserImages.user_id == cur_user.id, UserImages.image_tag == tag)).first() is not None:
            return_dict['message'] = "镜像build失败，tag与已有的tag重复"
            return flask.jsonify(return_dict)
        client = docker.DockerClient(base_url='unix://var/run/docker.sock')
        _, _ = client.images.build(path=file_path, tag=tag)

        user_image = UserImages(user_id=cur_user.id, image_tag=tag)
        db.session.add(user_image)
        db.session.commit()

        return_dict['message'] = "镜像构建成功"
        return_dict['info'] = {"userId": cur_user.id, "imageId": user_image.id, "imageTag": tag}
        return flask.jsonify(return_dict)

    return_dict['message'] = "出错，文件不能为空且文件格式需符合要求（zip）"
    return flask.jsonify(return_dict)


# # todo 进一步检查一下写法
# @bp.route('/download', methods=['POST'])
# def download():
#     username = request.form['username']
#     file_name = request.form['filename']
#     user_path = os.path.join(app.config['UPLOAD_FOLDER'], username)
#     return send_from_directory(user_path, file_name, as_attachment=True)
#
#
# @bp.route('/run_image', methods=['POST'])
# def run_images():
#     host_port = request.form['host_port']
#     container_port = request.form['container_port']
#     image = request.form['image']
#     return_dict = {'statusCode': '200', 'message': 'successful!'}
#     client = docker.DockerClient(base_url='unix://var/run/docker.sock')
#     try:
#         _ = client.containers.run(image=image, detach=True, ports={container_port: host_port})
#     except errors.ContainerError:
#         return_dict['message'] = "the container exits with a non-zero exit code"
#     except errors.ImageNotFound:
#         return_dict['message'] = "the specified image does not exist"
#     except errors.APIError:
#         return_dict['message'] = "the server returns an error"
#     finally:
#         return flask.jsonify(return_dict)
#
