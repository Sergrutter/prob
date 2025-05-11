from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf.csrf import CSRFProtect
from rapidfuzz import fuzz
from deep_translator import GoogleTranslator  # Используем deep-translator для перевода
import os
import random
import requests
import xml.etree.ElementTree as ET
import datetime

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app():
    # Создаем экземпляр приложения
    app = Flask(__name__)

    # Конфигурация
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Инициализируем расширения с приложением
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = 'login'

    return app


app = create_app()


def get_img(query):
    url = f"https://api.unsplash.com/photos/random?query={query}&client_id=_k1CxaFIKv7ClydnoC6b8XAI_1O5ZYoyijLPYaVqmcI"
    r = requests.get(url)
    if r:
        return r.json().get('urls', {}).get('small')
    return None


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)


page_category = db.Table('page_category',
                         db.Column('page_id', db.Integer, db.ForeignKey('page.id')),
                         db.Column('category_id', db.Integer, db.ForeignKey('category.id'))
                         )


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    image_url = db.Column(db.String(300))
    pages = db.relationship('Page', backref='author', lazy=True)
    bio = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class Page(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(300))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    categories = db.relationship('Category', secondary=page_category, backref='pages')


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), unique=True)

    page_tag = db.Table('page_tag',
                        db.Column('page_id', db.Integer, db.ForeignKey('page.id')),
                        db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'))
                        )


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    page_id = db.Column(db.Integer, db.ForeignKey('page.id'), nullable=False)

    user = db.relationship('User', backref='comments')
    page = db.relationship('Page', backref='comments')


@app.route('/api/pages')
def api_pages():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    pages = Page.query.paginate(page=page, per_page=per_page)

    return jsonify({
        'pages': [{'id': p.id, 'title': p.title} for p in pages.items],
        'total': pages.total,
        'pages': pages.pages
    })


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/category/<int:category_id>')
def show_category(category_id):
    category = Category.query.get_or_404(category_id)
    return render_template('category.html', category=category)


@app.route('/')
def home():
    pages = Page.query.all()
    return render_template('home.html', pages=pages)


@app.route('/profile/<username>')
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    return render_template('profile.html', user=user)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Проверка, существует ли пользователь
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Пользователь с таким именем или email уже существует', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('Регистрация прошла успешно! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/random')
def random_page():
    pages = Page.query.all()
    if not pages:
        flash('Нет доступных страниц.', 'info')
        return redirect(url_for('home'))

    page = random.choice(pages)
    return redirect(url_for('page_detail', page_id=page.id))


@app.route('/api/search', methods=['POST'])
def api_search():
    search_query = request.form.get('search_query', '').lower()
    results = []

    for page in Page.query.all():
        if search_query in page.title.lower():
            results.append({
                'id': page.id,
                'title': page.title,
                'preview': page.content[:100]
            })

    return jsonify(results)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Неверный email или пароль', 'danger')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/create_page', methods=['GET', 'POST'])
@login_required
def create_page():
    if request.method == 'POST':
        title = request.form['page_name']
        content = request.form['content']

        new_page = Page(title=title, content=content, author=current_user)
        db.session.add(new_page)
        db.session.commit()

        flash('Страница успешно создана!', 'success')
        return redirect(url_for('home'))

    return render_template('create_page.html')


@csrf.exempt
@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        search_query = request.form['search_query'].lower()
        all_pages = Page.query.all()

        matched_pages = []
        for page in all_pages:
            score = fuzz.partial_ratio(search_query, page.title.lower())
            if score > 60:
                matched_pages.append((score, page))

        matched_pages.sort(reverse=True, key=lambda x: x[0])
        pages = [p[1] for p in matched_pages]

        return render_template('search_results.html', pages=pages, query=search_query)

    return redirect(url_for('home'))


@app.route('/page/<int:page_id>', methods=['GET', 'POST'])
def page_detail(page_id):
    page = Page.query.get_or_404(page_id)

    if request.method == 'POST' and current_user.is_authenticated:
        comment_text = request.form['comment']
        if comment_text.strip():
            comment = Comment(content=comment_text, user_id=current_user.id, page_id=page.id)
            db.session.add(comment)
            db.session.commit()
            flash("Комментарий добавлен", "success")
            return redirect(url_for('page_detail', page_id=page_id))
        else:
            flash("Комментарий не может быть пустым", "warning")

    return render_template('text_block.html', page=page)


@app.route('/edit_page/<int:page_id>', methods=['GET', 'POST'])
@login_required
def edit_page(page_id):
    page = Page.query.get(page_id)

    if current_user.id != page.user_id:
        flash('У вас нет прав для редактирования этой страницы', 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        page.title = request.form['page_name']
        page.content = request.form['content']
        db.session.commit()

        flash('Страница успешно обновлена', 'success')
        return redirect(url_for('page_detail', page_id=page_id))

    return render_template('edit_page.html', page=page)


def create_first_user():
    if User.query.first() is None:
        user = User(
            username='Таренс Тао',
            email='tarens@gmail.com',
            password='123'
        )
        db.session.add(user)
        db.session.commit()


# def import_articles_from_arxiv(query, max_results):
#     url = f"http://export.arxiv.org/api/query?search_query=all:{query}&start=0&max_results={max_results}"
#     response = requests.get(url)
#     root = ET.fromstring(response.content)
#     user = User.query.first()

#     for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
#         title = entry.find('{http://www.w3.org/2005/Atom}title').text.strip()
#         summary = entry.find('{http://www.w3.org/2005/Atom}summary').text.strip()
#         translated_t = GoogleTranslator(source='auto', target='ru').translate(title)
#         translated_s = GoogleTranslator(source='auto', target='ru').translate(summary)

#         image_url = get_img(title)

#         new_article = Page(
#             title=translated_t,
#             content=translated_s,
#             image_url=image_url,
#             author=user
#         )
#         db.session.add(new_article)

#     db.session.commit()


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_first_user()

        # Проверка: если статей нет, импортируем
        # if Page.query.first() is None:
        #     import_articles_from_arxiv("machine learning", max_results=20)

    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
