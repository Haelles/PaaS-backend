# PaaS-backend

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



/images/remove_image

删除某个repo中的某个镜像

参数：

* username
* repo
* tag





### 容器管理







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
