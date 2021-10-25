import base64
import json
import os
import zipfile
import random
from pprint import pprint

import flask
from docker import errors
from kubernetes import client, config
from flask import send_from_directory, Flask, request, Blueprint, current_app
from kubernetes.client import ApiException

from apps.models.user import User

deploy_control = Blueprint('deploy', __name__, url_prefix='/deploy')
# configuration = client.Configuration()
# configuration.api_key['authorization'] = 'API_KEY'
# configuration.host = 'localhost'
# with client.ApiClient(configuration) as api_client:
config.load_kube_config()
k8s_apps_v1 = client.AppsV1Api()
k8s_core_v1 = client.CoreV1Api()


# 查看所有namespace
def get_all_namespace():
    try:
        api_response = k8s_core_v1.list_namespace()
        res = []
        for namespace in api_response.items:
            res.append(namespace.metadata.name)  # 通过pprint可以打印各个属性
        return res
    except ApiException as e:
        print("Exception when calling CoreV1Api->list_namespace: %s\n" % e)
        return []


# 根据k8s命名规则不能在namespace中使用"/"，因此改用"-"，构成username-namespace格式作为create_namespace的参数
@deploy_control.route('/create_namespace', methods=['POST'])
def create_namespace():
    return_dict = {'statusCode': '200', 'message': 'successful!'}
    username = request.form.get('username')
    namespace = request.form.get('namespace')

    if username is None or namespace is None:
        return_dict['message'] = "username、namespace字段都不能为空"
        return flask.jsonify(return_dict)
    cur_user = User.query.filter(User.name == username).first()
    if cur_user is None:
        return_dict['message'] = "用户名不存在，请检查用户信息"
        return flask.jsonify(return_dict)

    final_namespace = username + "-" + namespace
    if final_namespace not in get_all_namespace():
        body = {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": final_namespace,
            }
        }
        ret = k8s_core_v1.create_namespace(body=body)
        # pprint(ret)
    else:
        return_dict['message'] = "该namespace已被创建过，请换一个名字"
    return flask.jsonify(return_dict)


# 查看当前用户有哪些namespace
@deploy_control.route('/list_all_my_namespaces', methods=['POST'])
def list_all_my_namespaces():
    return_dict = {'statusCode': '200', 'message': 'successful!'}
    username = request.form.get('username')
    if username is None:
        return_dict['message'] = "username字段都能为空"
        return flask.jsonify(return_dict)
    cur_user = User.query.filter(User.name == username).first()
    if cur_user is None:
        return_dict['message'] = "用户名不存在，请检查用户信息"
        return flask.jsonify(return_dict)

    all_namespace = get_all_namespace()
    res = []
    for name in all_namespace:
        if name.startswith(username):
            res.append(name)
    return_dict['namespaces'] = res
    return flask.jsonify(return_dict)


# 删除某个namespace
@deploy_control.route('/delete_namespace', methods=['POST'])
def delete_namespace():
    return_dict = {'statusCode': '200', 'message': 'successful!'}
    username = request.form.get('username', default=None)
    namespace = request.form.get('namespace', default=None)

    if username is "" or namespace is "":
        return_dict['message'] = "username、namespace字段都不能为空"
        return flask.jsonify(return_dict)
    cur_user = User.query.filter(User.name == username).first()
    if cur_user is None:
        return_dict['message'] = "用户名不存在，请检查用户信息"
        return flask.jsonify(return_dict)
    try:
        _ = k8s_core_v1.delete_namespace(name=username+"-"+namespace)
    except client.exceptions.ApiException:
        return_dict['message'] = "这个namespace不存在，请检查名字"
    return flask.jsonify(return_dict)



@deploy_control.route('/create_deploy', methods=['POST'])
def create_deployment(namespace: str, name: str, update_image: str):
    # TODO 检查镜像存在
    username = request.form.get('username')
    namespace = username + '$' + namespace
    # TODO 参数
    body = client.V1Deployment(api_version='apps/v1', kind='Deployment', metadata=None, spec=None)
    # body.spec.template.spec.containers[0].image = update_image
    # body.spec.template.spec.containers[0].name = name
    # TODO return value
    try:
        api_response = k8s_apps_v1.create_namespaced_deployment(namespace=namespace, name=name, body=body)
        return api_response
    except ApiException as e:
        return 'www'


@deploy_control.route('read_deployment_status', methods=['POST'])
def read_deployment_status(namespace: str, name: str):
    username = request.form.get('username')
    namespace = username + '$' + namespace
    # TODO 检查 deployment 存在
    try:
        api_response = k8s_apps_v1.read_namespaced_deployment_status(name, namespace)
        return api_response
    except ApiException as e:
        return 'www'


@deploy_control.route('list_deployment', methods=['POST'])
def list_deployment(namespace: str):
    username = request.form.get('username')
    namespace = username + '$' + namespace
    try:
        api_response = k8s_apps_v1.list_namespaced_deployment(namespace)
        return api_response
    except ApiException as e:
        return 'www'


@deploy_control.route('delete_deployment', methods=['POST'])
def delete_deployment(namespace: str, name: str):
    username = request.form.get('username')
    namespace = username + '$' + namespace
    # TODO 检查 deployment 存在
    try:
        api_response = k8s_apps_v1.delete_namespaced_deployment(namespace=namespace, name=name)
        return api_response
    except ApiException as e:
        return 'www'
