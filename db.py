from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mydatabase.db'
db = SQLAlchemy(app)


class Page(db.Model):
    """Таблица для хранения созданных страниц"""
    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(100), nullable = False)
    creator = db.Column(db.String(100), nullable = False)
    url = db.Column(db.String(200), nullable = False)


class User(db.Model):
    """Таблица для хранения зарегистрировавшихся пользователей"""
    id = db.Column(db.Integer, primary_key = True)
    email = db.Column(db.String(100), nullable = False)
    name = db.Column(db.String(100), nullable = False)


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    page_id = db.Column(db.Integer, db.ForeignKey('page.id'), nullable=False)

    user = db.relationship('User', backref='comments')
    page = db.relationship('Page', backref='comments')


db.create_all()
