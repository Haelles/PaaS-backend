# PaaS-backend

## 配置

`pip install -r requirements.txt`



settings.py中`SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:@localhost:3306/paas_prac'`修改成本机数据库



修改数据表：

`python manage.py db init `执行一次即可

`python manage.py db migrate`

`python manage.py db upgrade`



## api

### 登录注册

/user/register

* username
* password



/user/login

* username
* password



### 镜像管理

/image/upload_image 

上传一个包含Dockerfile的zip文件，进行解压和build

参数：

* username
* repo
* tag
* file



/image/list_all_my_repo 

查看某个用户的全部repo

参数：

* username



/image/list_all_my_images

查看某个用户的某个repo中的全部镜像

参数：

* username
* repo



/images/tag_image

修改镜像的tag，相当于docker tag

参数：

* username
* oldrepo
* oldtag
* newrepo
* newtag



/images/delete_image

删除某个repo中的某个镜像

参数：

* username
* repo
* tag





### 容器管理

/deploy/list_all\_nodes

get方法，查看所有nodes信息



/deploy/create_namespace

创建一个namespace，**现暂时按照username-namespace的格式创建**

参数：

* username  如"henry"
* namespace 如"test"

则会创建一个henry-test的namespace



/deploy/list_all_my_namespace

查看某个用户所有的namespace

参数：

* username  





/deploy/delete_namespace

查看某个用户的某个namespace

参数：

* username  如"henry"
* namespace 如"test"

则会删除henry-test这个namespace



/deploy/create_deployment

上传一个yaml文件，创建一个deployment **？需要返回的信息是**

参数：

* username  如"henry"
* file 如"nginx.yaml"

在/data/henry下存储这个yaml文件，然后创建



/deploy/list_all_pods

查看某个用户某个namespace下的所有pods

参数：

* username  如"henry"
* namespace 如"test"



/deploy/list_all\_developments

查看某个用户在某个namespace下的所有developments

参数：

* username  如"henry"
* namespace 如"test"



/deploy/update_deployment

上传更新后的yaml文件，对deployment进行更新

参数：

* username  如"henry"
* file 如"nginx.yaml"



/deploy/delete_deployment

删除用户某个namespace中的一个deployment 

参数：

* username  如"henry"
* namespace
* deployment 要删除的deployment的名字



/deploy/create_service

上传一个yaml文件，创建一个service

参数：

* username  如"henry"
* file 如"nginx-service.yaml"

在/data/henry下存储这个yaml文件，然后创建



/deploy/update_service

上传更新后的yaml文件，对service进行更新

参数：

* username  如"henry"
* file 如"nginx.yaml"



/deploy/delete_service

删除某个service

参数：

* username  如"henry"
* namespace 如"name1"
* service 服务的名称如"nginx-test-service"

效果为删除henry-name1这个namespace下的服务nginx-test-service







### 应用部署





## 现有的mysql表

User:

* name(primary key)
* password



UserImages:

* id(int, primary key)
* user_name(foreign key: User.name)
* image_tag
* image_repo

镜像名字格式为 username/image\_repo:image\_tag

前端传参只需要传repo和tag即可，后端会加上username

