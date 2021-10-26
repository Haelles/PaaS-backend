import base64
import json
import os
import zipfile
import random
from pprint import pprint

import flask
import yaml
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


# 查看所有node
@deploy_control.route('/list_all_nodes', methods=['POST', 'GET'])
def list_all_nodes():
    return_dict = {'statusCode': '200', 'message': '查看nodes成功'}
    node_list = k8s_core_v1.list_node().items
    res_list = []
    # name roles age version internal-ip
    # print('\n'.join(['%s:%s' % item for item in node_list[1].__dict__.items()]))
    for node in node_list:
        res_list.append({"name": node.metadata.name,
                         "address": {"type": node.status.addresses[0].type,
                                     "ip": node.status.addresses[0].address},
                         "os_image": node.status.node_info.os_image})
    return_dict['info'] = res_list
    return flask.jsonify(return_dict)


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
            res.append(name.split('-')[-1])  # 屏蔽用户名的作用
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
        _ = k8s_core_v1.delete_namespace(name=username + "-" + namespace)
        return_dict['message'] = "删除namespace成功"
    except client.exceptions.ApiException:
        return_dict['message'] = "这个namespace不存在，请检查名字"
    return flask.jsonify(return_dict)


# 创建一个deployment
@deploy_control.route('/create_deployment', methods=['POST'])
def create_deployment():
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
        return flask.jsonify(return_dict)

    if file and (file.filename.endswith('yml') or file.filename.endswith('yaml')):
        filename = file.filename  # e.g. nginx.yml
        user_path = os.path.join(current_app.config.get('UPLOAD_FOLDER'), username)  # /data/username
        if not os.path.exists(user_path):
            os.makedirs(user_path)
        # TODO 文件名重复的问题
        # random_int = random.randint(0, 150)
        # file_path = os.path.join(user_path, filename.rsplit('.', 1)[-2] + str(random_int))
        file_path = os.path.join(user_path, filename)
        file.save(file_path)

        with open(file_path) as f:
            dep = yaml.safe_load(f)
            namespace = dep.get("metadata")
            if namespace is None:
                return_dict['message'] = "缺少metadata字段"
                return return_dict
            namespace = namespace.get("namespace")  # 默认设置为username-default
            if namespace is None:
                namespace = "default"
            try:
                # pprint(dep)
                dep['metadata']['namespace'] = username + "-" + namespace
                # pprint(dep)
                resp = k8s_apps_v1.create_namespaced_deployment(body=dep, namespace=username + "-" + namespace)
                # pprint(resp)
                return_dict['message'] = "创建deployment成功"
                return_dict['info'] = {"selector": dep['spec']['selector']}
            except client.exceptions.ApiException as e:
                return_dict['info'] = {}
                return_dict['message'] = json.loads(e.body)['message']
            finally:
                return flask.jsonify(return_dict)


@deploy_control.route('list_all_pods', methods=['POST'])
def list_all_pods():
    return_dict = {'statusCode': '200', 'message': 'successful!'}
    username = request.form.get('username')
    namespace = request.form.get('namespace')

    if username is "" or namespace is "":
        return_dict['message'] = "username、namespace字段都不能为空"
        return flask.jsonify(return_dict)
    cur_user = User.query.filter(User.name == username).first()
    if cur_user is None:
        return_dict['message'] = "用户名不存在，请检查用户信息"
        return flask.jsonify(return_dict)

    final_namespace = username + "-" + namespace
    try:
        resp = k8s_core_v1.list_namespaced_pod(namespace=final_namespace)

        # TODO 需要什么信息
        res_list = []
        for res in resp.items:
            # print('\n'.join(['%s:%s' % item for item in res.__dict__.items()]))

            res_list.append({"name": res.metadata.name, "ip": res.status.pod_ip})

            # pprint(res.__dict__.get('_metadata').name)
            # pprint(res.__dict__.get('_status').status)

        return_dict['message'] = "查看pods成功"

        return_dict['info'] = {"namespace": namespace, "pods": res_list}
    except client.exceptions.ApiException as e:
        return_dict['info'] = {}
        return_dict['message'] = json.loads(e.body)['message']
    finally:
        return flask.jsonify(return_dict)


# 更新deployment
@deploy_control.route('update_deployment', methods=['POST'])
def update_deployment():
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
        return flask.jsonify(return_dict)

    if file and (file.filename.endswith('yml') or file.filename.endswith('yaml')):
        filename = file.filename  # e.g. nginx.yml
        user_path = os.path.join(current_app.config.get('UPLOAD_FOLDER'), username)  # /data/username
        if not os.path.exists(user_path):
            os.makedirs(user_path)
        # TODO 文件名重复的问题
        # random_int = random.randint(0, 150)
        # file_path = os.path.join(user_path, filename.rsplit('.', 1)[-2] + str(random_int))
        file_path = os.path.join(user_path, filename)
        file.save(file_path)

        with open(file_path) as f:
            dep = yaml.safe_load(f)
            metadata = dep.get("metadata")
            if metadata is None:
                return_dict['message'] = "缺少metadata字段"
                return return_dict
            namespace = metadata.get("namespace")  # 默认设置为username-default
            if namespace is None:
                namespace = "default"
            try:
                # pprint(dep)
                dep['metadata']['namespace'] = username + "-" + namespace
                # pprint(dep)
                resp = k8s_apps_v1.patch_namespaced_deployment(name=metadata.get('name'), body=dep,
                                                               namespace=username + "-" + namespace)
                # pprint(resp)
                return_dict['message'] = "更新deployment成功"
                return_dict['info'] = {"selector": dep['spec']['selector']}
            except client.exceptions.ApiException as e:
                return_dict['info'] = {}
                return_dict['message'] = json.loads(e.body)['message']
            finally:
                return flask.jsonify(return_dict)


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


@deploy_control.route('list_all_deployments', methods=['POST'])
def list_all_deployments():
    return_dict = {'statusCode': '200', 'message': 'successful!'}
    username = request.form.get('username')
    namespace = request.form.get('namespace')

    if username is "" or namespace is "":
        return_dict['message'] = "username、namespace字段都不能为空"
        return flask.jsonify(return_dict)
    cur_user = User.query.filter(User.name == username).first()
    if cur_user is None:
        return_dict['message'] = "用户名不存在，请检查用户信息"
        return flask.jsonify(return_dict)

    final_namespace = username + "-" + namespace
    try:
        resp = k8s_apps_v1.list_namespaced_deployment(namespace=final_namespace)

        # TODO 需要什么信息
        res_list = []
        for res in resp.items:
            # print('\n'.join(['%s:%s' % item for item in res.__dict__.items()]))
            # name images containers age selector
            # TODO if len(res.spec.template.spec.containers) > 1
            res_list.append({"name": res.metadata.name,
                             "image": res.spec.template.spec.containers[0].image,
                             "selector": res.spec.selector.match_labels['run'],
                             "replica": res.status.replicas})
            # print(type(res.spec.template.spec.containers[0]))
            # print(type(res.spec.selector.match_labels))
        return_dict['message'] = "查看deployments成功"

        return_dict['info'] = {"namespace": namespace, "deployments": res_list}
    except client.exceptions.ApiException as e:
        return_dict['info'] = {}
        return_dict['message'] = json.loads(e.body)['message']
    finally:
        return flask.jsonify(return_dict)


@deploy_control.route('delete_deployment', methods=['POST'])
def delete_deployment():
    return_dict = {'statusCode': '200', 'message': 'successful!'}
    username = request.form.get('username')
    namespace = request.form.get('namespace')
    deployment = request.form.get('deployment')

    if username is "" or namespace is "" or deployment is "":
        return_dict['message'] = "username、namespace、deployment字段都不能为空"
        return flask.jsonify(return_dict)
    cur_user = User.query.filter(User.name == username).first()
    if cur_user is None:
        return_dict['message'] = "用户名不存在，请检查用户信息"
        return flask.jsonify(return_dict)

    final_namespace = username + "-" + namespace

    try:
        resp = k8s_apps_v1.delete_namespaced_deployment(
            name=deployment,
            namespace=final_namespace,
            body=client.V1DeleteOptions(
                propagation_policy="Foreground", grace_period_seconds=5
            ),
        )
        return_dict['message'] = "删除deployment成功"
    except ApiException as e:
        return_dict['message'] = json.loads(e.body)['message']
    finally:
        return flask.jsonify(return_dict)


# 创建一个service
@deploy_control.route('/create_service', methods=['POST'])
def create_service():
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
        return flask.jsonify(return_dict)

    if file and (file.filename.endswith('yml') or file.filename.endswith('yaml')):
        filename = file.filename  # e.g. nginx.yml
        user_path = os.path.join(current_app.config.get('UPLOAD_FOLDER'), username)  # /data/username
        if not os.path.exists(user_path):
            os.makedirs(user_path)
        # TODO 文件名重复的问题
        # random_int = random.randint(0, 150)
        # file_path = os.path.join(user_path, filename.rsplit('.', 1)[-2] + str(random_int))
        file_path = os.path.join(user_path, filename)
        file.save(file_path)

        with open(file_path) as f:
            dep = yaml.safe_load(f)
            namespace = dep.get("metadata")
            if namespace is None:
                return_dict['message'] = "缺少metadata字段"
                return return_dict
            namespace = namespace.get("namespace")  # 默认设置为username-default
            if namespace is None:
                namespace = "default"
            try:
                # pprint(dep)
                dep['metadata']['namespace'] = username + "-" + namespace
                # pprint(dep)
                resp = k8s_core_v1.create_namespaced_service(body=dep, namespace=username + "-" + namespace)
                # print('\n'.join(['%s:%s' % item for item in resp.__dict__.items()]))
                # pprint(resp)
                return_dict['message'] = "创建service成功"
                # TODO 如果有更多的port，也即len(resp.spec.port) > 1
                return_dict['info'] = {"name": resp.metadata.name,
                                       "type": resp.spec.type,
                                       "cluster-ip": resp.spec.cluster_ip,
                                       "port": str(resp.spec.ports[0].port) + ":" + str(
                                           resp.spec.ports[0].node_port) + "/" + resp.spec.ports[0].protocol}

            except client.exceptions.ApiException as e:
                return_dict['info'] = {}
                return_dict['message'] = json.loads(e.body)['message']
            finally:
                return flask.jsonify(return_dict)


# 更新service
@deploy_control.route('update_service', methods=['POST'])
def update_service():
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
        return flask.jsonify(return_dict)

    if file and (file.filename.endswith('yml') or file.filename.endswith('yaml')):
        filename = file.filename  # e.g. nginx.yml
        user_path = os.path.join(current_app.config.get('UPLOAD_FOLDER'), username)  # /data/username
        if not os.path.exists(user_path):
            os.makedirs(user_path)
        # TODO 文件名重复的问题
        # random_int = random.randint(0, 150)
        # file_path = os.path.join(user_path, filename.rsplit('.', 1)[-2] + str(random_int))
        file_path = os.path.join(user_path, filename)
        file.save(file_path)

        with open(file_path) as f:
            dep = yaml.safe_load(f)
            metadata = dep.get("metadata")
            if metadata is None:
                return_dict['message'] = "缺少metadata字段"
                return return_dict
            namespace = metadata.get("namespace")  # 默认设置为username-default
            if namespace is None:
                namespace = "default"
            try:
                # pprint(dep)
                dep['metadata']['namespace'] = username + "-" + namespace
                # pprint(dep)
                resp = k8s_core_v1.patch_namespaced_service(name=metadata.get('name'), body=dep,
                                                            namespace=username + "-" + namespace)
                # pprint(resp)
                return_dict['message'] = "更新service成功"
                return_dict['info'] = {"selector": dep['spec']['selector']}
            except client.exceptions.ApiException as e:
                return_dict['info'] = {}
                return_dict['message'] = json.loads(e.body)['message']
            finally:
                return flask.jsonify(return_dict)


# 删除一个服务
@deploy_control.route('delete_service', methods=['POST'])
def delete_service():
    return_dict = {'statusCode': '200', 'message': 'successful!'}
    username = request.form.get('username')
    namespace = request.form.get('namespace')
    service = request.form.get('service')

    if username is "" or namespace is "" or service is "":
        return_dict['message'] = "username、namespace、service字段都不能为空"
        return flask.jsonify(return_dict)
    cur_user = User.query.filter(User.name == username).first()
    if cur_user is None:
        return_dict['message'] = "用户名不存在，请检查用户信息"
        return flask.jsonify(return_dict)

    final_namespace = username + "-" + namespace

    try:
        resp = k8s_core_v1.delete_namespaced_service(
            name=service,
            namespace=final_namespace,
            body=client.V1DeleteOptions()
        )
        return_dict['message'] = "删除service成功"
    except ApiException as e:
        return_dict['message'] = json.loads(e.body)['message']
    finally:
        return flask.jsonify(return_dict)
