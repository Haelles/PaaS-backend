import base64
import json
import os
import zipfile
import random

import flask
from docker import errors
from kubernetes import client, config
from flask import send_from_directory, Flask, request, Blueprint, current_app
from kubernetes.client import ApiException

deploy_control = Blueprint('deploy', __name__, url_prefix='/deploy')
configuration = client.Configuration()
configuration.api_key['authorization'] = 'API_KEY'
configuration.host = 'localhost'
with client.ApiClient(configuration) as api_client:
    api_instance = client.AppsV1Api(api_client)


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
        api_response = api_instance.create_namespaced_deployment(namespace=namespace, name=name, body=body)
        return api_response
    except ApiException as e:
        return 'www'


@deploy_control.route('read_deployment_status', methods=['POST'])
def read_deployment_status(namespace: str, name: str):
    username = request.form.get('username')
    namespace = username + '$' + namespace
    # TODO 检查 deployment 存在
    try:
        api_response = api_instance.read_namespaced_deployment_status(name, namespace)
        return api_response
    except ApiException as e:
        return 'www'


@deploy_control.route('list_deployment', methods=['POST'])
def list_deployment(namespace: str):
    username = request.form.get('username')
    namespace = username + '$' + namespace
    try:
        api_response = api_instance.list_namespaced_deployment(namespace)
        return api_response
    except ApiException as e:
        return 'www'


@deploy_control.route('delete_deployment', methods=['POST'])
def delete_deployment(namespace: str, name: str):
    username = request.form.get('username')
    namespace = username + '$' + namespace
    # TODO 检查 deployment 存在
    try:
        api_response = api_instance.delete_namespaced_deployment(namespace=namespace, name=name)
        return api_response
    except ApiException as e:
        return 'www'
