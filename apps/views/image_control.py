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


@image_control.route('/test', methods=['GET'])
def test():
    print('this is image_control-bp, route is /image')
    return 'this is image_control-bp, route is /image'


# 删除某个repo中的某个镜像
@image_control.route('/delete_image', methods=['POST'])
def delete_image():
    return_dict = {'statusCode': '200', 'message': 'successful!'}
    username = request.form.get('username')
    repo = request.form.get('repo')
    tag = request.form.get('tag')

    if username is None or tag is None or repo is None:
        return_dict['message'] = "username、tag、repo字段都不能为空"
        return flask.jsonify(return_dict)
    cur_user = User.query.filter(User.name == username).first()
    if cur_user is None:
        return_dict['message'] = "用户名不存在，请检查用户信息"
        return flask.jsonify(return_dict)

    final_tag = cur_user.name + "/" + repo + ":" + tag
    client = docker.DockerClient(base_url='unix://var/run/docker.sock')

    # 删除镜像tag
    try:
        client.images.remove(final_tag)
        # 删除mysql表中的tag
        user_image = UserImages.query.filter(
            and_(UserImages.user_name == cur_user.name, UserImages.image_repo == repo,
                 UserImages.image_tag == tag)).first()
        if user_image is None:
            return_dict['message'] = "找不到该镜像，请重新检查tag"
        else:
            db.session.delete(user_image)
            db.session.commit()
            return_dict['message'] = "删除成功"
    except docker.errors.ImageNotFound:
        return_dict['message'] = "找不到该镜像，请重新检查tag"
    finally:
        return flask.jsonify(return_dict)


# 修改镜像的tag
@image_control.route('/tag_image', methods=['POST'])
def tag_image():
    return_dict = {'statusCode': '200', 'message': 'successful!'}
    username = request.form.get('username')
    old_repo = request.form.get('oldrepo')
    new_repo = request.form.get('newrepo')
    old_tag = request.form.get('oldtag')
    new_tag = request.form.get('newtag')
    if username is None or new_tag is None or old_tag is None or old_repo is None or new_repo is None:
        return_dict['message'] = "username、oldtag、newtag、old_repo、old_repo字段都不能为空"
        return flask.jsonify(return_dict)

    cur_user = User.query.filter(User.name == username).first()
    if cur_user is None:
        return_dict['message'] = "用户名不存在，请检查用户信息"
        return flask.jsonify(return_dict)

    final_old_tag = cur_user.name + "/" + old_repo + ":" + old_tag
    final_new_tag = cur_user.name + "/" + new_repo + ":" + new_tag

    client = docker.DockerClient(base_url='unix://var/run/docker.sock')

    if UserImages.query.filter(and_(UserImages.user_name == cur_user.name, UserImages.image_repo == old_repo,
                                    UserImages.image_tag == old_tag)).first() is None:
        return_dict['message'] = "找不到镜像，请检查tag是否有误"
        return flask.jsonify(return_dict)

    if UserImages.query.filter(and_(UserImages.user_name == cur_user.name, UserImages.image_repo == new_repo,
                                    UserImages.image_tag == new_tag)).first() is not None:
        return_dict['message'] = "这个repo/tag已被使用过，请换一个"
        return flask.jsonify(return_dict)

    try:
        # 修改镜像tag
        image = client.images.get(final_old_tag)
        # for tag in image.tags:
        #     print(tag)
        image.tag(final_new_tag)
        # print("------")
        # for tag in image.tags:
        #     print(tag)
        client.images.remove(final_old_tag)
        # 修改mysql表中的tag
        user_image = UserImages.query.filter(
            and_(UserImages.user_name == cur_user.name, UserImages.image_repo == old_repo,
                 UserImages.image_tag == old_tag)).first()
        user_image.image_tag = new_tag
        user_image.image_repo = new_repo
        db.session.commit()
        return_dict["info"] = {"userId": cur_user.id, "imageId": user_image.id, "repo": new_repo, "imageTag": new_tag}
    except docker.errors.ImageNotFound:
        return_dict['message'] = "找不到该镜像，请重新检查tag"
    except docker.errors.APIError:
        return_dict['message'] = "docker.errors.APIError: the server returns an error"
    finally:
        return flask.jsonify(return_dict)


# 查看某个用户某个repo中的全部镜像
@image_control.route('/list_all_repo_images', methods=['POST'])
def list_all_repo_images():
    return_dict = {'statusCode': '200', 'message': 'successful!'}
    username = request.form.get('username')
    # repo字段中不需要添加username，只取username/repo中的repo即可
    repo = request.form.get('repo')
    cur_user = User.query.filter(User.name == username).first()
    if cur_user is None:
        return_dict['message'] = "用户不存在，请检查用户名"
        return flask.jsonify(return_dict)
    if repo is None:
        return_dict['message'] = "repo字段不能为空"
        return flask.jsonify(return_dict)
    search_res = UserImages.query.filter(UserImages.user_name == cur_user.name, UserImages.image_repo == repo).all()
    if len(search_res) == 0:
        return_dict['message'] = "用户这个repo中拥有的镜像数为0"
    res_list = []
    for res in search_res:
        res_list.append(res.to_json())
    return_dict['images'] = res_list
    return flask.jsonify(return_dict)


# 查看某个用户的全部repo
@image_control.route('/list_all_my_repo', methods=['POST'])
def list_all_my_repo():
    return_dict = {'statusCode': '200', 'message': 'successful!'}
    username = request.form.get('username')
    cur_user = User.query.filter(User.name == username).first()
    if cur_user is None:
        return_dict['message'] = "用户不存在，请检查用户名"
        return flask.jsonify(return_dict)
    search_res = UserImages.query.filter(UserImages.user_name == cur_user.name).all()
    res_list = set()
    if len(search_res) == 0:
        return_dict['message'] = "用户拥有的repo数为0"
    for res in search_res:
        res_list.add(res.image_repo)
    return_dict['images'] = list(res_list)
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
    cur_user = User.query.filter(User.name == username).first()
    if cur_user is None:
        return_dict['message'] = "用户不存在，请检查用户名"
        return flask.jsonify(return_dict)
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
        repo = request.form.get('repo')
        tag = request.form.get('tag')
        # 偷懒的写法，限制镜像tag格式为"repo:用户输入的tag"，最终对应命令docker build -t username/repo:tag
        if repo is None or ':' in repo or ":" in tag:
            return_dict['message'] = "镜像build失败，repo字段不能为空，且repo/tag字段中不能包含冒号"
            return flask.jsonify(return_dict)
        if tag is None:
            tag = "latest"

        final_tag = cur_user.name + "/" + repo + ':' + tag

        # 限制镜像tag不能与已有的重复
        if UserImages.query.filter(and_(UserImages.user_name == cur_user.name, UserImages.image_repo == repo,
                                        UserImages.image_tag == tag)).first() is not None:
            return_dict['message'] = "镜像build失败，tag与这个repo中已有的tag重复"
            return flask.jsonify(return_dict)
        client = docker.DockerClient(base_url='unix://var/run/docker.sock')
        _, _ = client.images.build(path=file_path, tag=final_tag)

        user_image = UserImages(user_name=cur_user.name, image_repo=repo, image_tag=tag)
        db.session.add(user_image)
        db.session.commit()

        return_dict['message'] = "镜像构建成功"
        return_dict['info'] = {"username": cur_user.name, "imageId": user_image.id, "repo": repo, "imageTag": tag}
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
