from exts import db


class EntityBase(object):
    def to_json(self):
        fields = self.__dict__
        if "_sa_instance_state" in fields:
            del fields["_sa_instance_state"]
        return fields


class User(db.Model, EntityBase):
    # 数据表名、字段
    __tablename__ = 'user'
    name = db.Column(db.String(100), nullable=False, primary_key=True)
    password = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer)


class UserImages(db.Model, EntityBase):
    __tablename__ = 'user_images'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    user_name = db.Column(db.String(100), db.ForeignKey('user.name'))
    image_tag = db.Column(db.String(100), nullable=False, default="latest")
    image_repo = db.Column(db.String(100), nullable=False)
