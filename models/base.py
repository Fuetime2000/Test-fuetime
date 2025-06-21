from extensions import db

class Base(db.Model):
    __abstract__ = True
