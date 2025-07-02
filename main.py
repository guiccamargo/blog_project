import datetime
from datetime import date
from functools import wraps
from typing import List

from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import current_user, LoginManager, login_user, UserMixin, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Integer, String, Text, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from werkzeug.security import generate_password_hash, check_password_hash

# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm

'''
Make sure the required packages are installed: 
Open the Terminal in PyCharm (bottom left). 

On Windows type:
python -m pip install -r requirements.txt

On MacOS type:
pip3 install -r requirements.txt

This will install the packages from the requirements.txt for this project.
'''
current_year = datetime.date.today().year
app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap5(app)

# TODO: Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


# Create admin-only decorator
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # If id is not 1, then return abort with 403 error
            if current_user.id == 1:
                return f(*args, **kwargs)
        except AttributeError:
            pass
        return abort(403)  # Otherwise continue with the route function

    return decorated_function


# CREATE DATABASE
class Base(DeclarativeBase):
    pass


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///posts.db'
db = SQLAlchemy(model_class=Base)
db.init_app(app)


# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String(250), nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    user: Mapped["User"] = relationship(back_populates="posts")
    comments: Mapped[List["Comment"]] = relationship(back_populates="post")


# TODO: Create a User table for all your registered users.
class User(UserMixin, db.Model):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(1000))
    posts: Mapped[List["BlogPost"]] = relationship(back_populates="user")
    comments: Mapped[List["Comment"]] = relationship(back_populates="user")

    def __init__(self, email, name, password):
        self.email = email
        self.name = name
        self.password = password


class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    user: Mapped["User"] = relationship(back_populates="comments")
    post_id: Mapped[int] = mapped_column(ForeignKey("blog_posts.id"))
    post: Mapped["BlogPost"] = relationship(back_populates="comments")


with app.app_context():
    db.create_all()


gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user = db.session.execute(db.select(User).where(User.email == request.form.get("email"))).scalar()
        if user:
            flash("You’ve already signed up with that email, log in instead!")
            return redirect(url_for("login"))
        else:
            with app.app_context():
                new_user = User(email=request.form.get("email"), name=request.form.get("name"),
                                password=generate_password_hash(request.form.get("password"), method="pbkdf2:sha256",
                                                                salt_length=8))
                db.session.add(new_user)
                db.session.commit()
                login_user(new_user)
                return redirect(url_for("get_all_posts"))
    else:
        register_form = RegisterForm()
        return render_template("register.html", form=register_form, logged_in=current_user.is_authenticated, year=current_year)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login', methods=["POST", "GET"])
def login():
    if request.method == "POST":
        user = db.session.execute(db.select(User).where(User.email == request.form.get("email"))).scalar()
        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for('login'))
        if check_password_hash(pwhash=user.password, password=request.form.get("password")):
            login_user(user)
            return redirect(url_for("get_all_posts"))
        else:
            flash("Password incorrect, please try again.")
            return render_template("login.html", form=LoginForm(), logged_in=current_user.is_authenticated, year=current_year)
    else:
        return render_template("login.html", form=LoginForm(), logged_in=current_user.is_authenticated, year=current_year)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    try:
        user_id = current_user.id
    except AttributeError:
        user_id = None
    return render_template("index.html", all_posts=posts, logged_in=current_user.is_authenticated, user_id=user_id, year=current_year)


# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>", methods=["POST", "GET"])
def show_post(post_id):
    try:
        user_id = current_user.id
    except AttributeError:
        user_id = None
    requested_post = db.get_or_404(BlogPost, post_id)
    if request.method == "POST":
        with app.app_context():
            new_comment = Comment(text=request.form.get("text"), user_id=current_user.id, user=current_user,
                post_id=post_id, post=db.get_or_404(BlogPost, post_id))
            db.session.add(new_comment)
            db.session.commit()
        comment_form = CommentForm()
        return render_template("post.html", post=requested_post, logged_in=current_user.is_authenticated,
                               user_id=user_id, form=comment_form, comments=db.get_or_404(BlogPost, post_id).comments, year=current_year)
    else:
        return render_template("post.html", post=requested_post, logged_in=current_user.is_authenticated,
                               user_id=user_id, form=CommentForm(), comments=db.get_or_404(BlogPost, post_id).comments, year=current_year)


# TODO: Use a decorator so only an admin user can create a new post
@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(title=form.title.data, subtitle=form.subtitle.data, body=form.body.data,
            img_url=form.img_url.data, author=current_user.name, date=date.today().strftime("%B %d, %Y"),
            user=current_user, user_id=current_user.id)
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, year=current_year)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(title=post.title, subtitle=post.subtitle, img_url=post.img_url, author=post.author,
        body=post.body)
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True, year=current_year)


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html", year=current_year)


@app.route("/contact")
def contact():
    return render_template("contact.html", year=current_year)


if __name__ == "__main__":
    app.run(debug=True, port=5002)
