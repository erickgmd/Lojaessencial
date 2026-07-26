import os
import re
import uuid
import mimetypes

import requests
from datetime import datetime
from pathlib import Path
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, send_from_directory, Response
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
# Carrega sempre o .env desta pasta e substitui variáveis antigas do Windows.
load_dotenv(dotenv_path=ENV_PATH, override=True)

def normalize_database_url(url: str) -> str:
    """Normaliza a URL do Supabase para o Psycopg 3 usado pelo SQLAlchemy."""
    url = (url or "").strip().strip('"').strip("'")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql+psycopg2://"):
        url = "postgresql+psycopg://" + url[len("postgresql+psycopg2://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url

UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
raw_database_url = os.getenv("DATABASE_URL", "").strip()
if not raw_database_url:
    raise RuntimeError(
        "DATABASE_URL não configurada. Crie o arquivo .env e informe a conexão do Supabase."
    )
database_url = normalize_database_url(raw_database_url)
if not database_url.startswith("postgresql"):
    raise RuntimeError("DATABASE_URL deve apontar para o PostgreSQL do Supabase.")

# A conexão direta db.<ref>.supabase.co costuma exigir IPv6. Para Windows/redes IPv4,
# use a string exibida em Supabase > Connect > Session pooler (porta 5432).
if "@db." in database_url and ".supabase.co" in database_url:
    raise RuntimeError(
        "A DATABASE_URL ainda usa a conexão direta do Supabase (host db.<ref>.supabase.co). "
        "Copie em Supabase > Connect > Session pooler a URL com host pooler.supabase.com "
        "e salve no arquivo .env desta pasta."
    )
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}
if database_url.startswith("postgresql"):
    app.config["SQLALCHEMY_ENGINE_OPTIONS"]["connect_args"] = {"sslmode": "require"}
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "admin_login"

def slugify(value):
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9\s-]", "", value)
    value = re.sub(r"[\s-]+", "-", value)
    return value.strip("-")

class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, default="")
    image_url = db.Column(db.String(700), default="")
    image_path = db.Column(db.String(500), default="")
    active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False)
    code = db.Column(db.String(60), unique=True, nullable=False)
    price = db.Column(db.Float, nullable=False)
    old_price = db.Column(db.Float)
    category = db.Column(db.String(80), nullable=False)
    brand = db.Column(db.String(80), nullable=False)
    sizes = db.Column(db.String(120), default="P,M,G")
    colors = db.Column(db.String(160), default="Preto")
    material = db.Column(db.String(120), default="Algodão")
    fit = db.Column(db.String(120), default="Regular")
    gender = db.Column(db.String(40), default="Unissex")
    description = db.Column(db.Text, default="")
    stock = db.Column(db.Integer, default=0)
    status = db.Column(db.String(40), default="Em estoque")
    featured = db.Column(db.Boolean, default=False)
    launch = db.Column(db.Boolean, default=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    images = db.relationship("ProductImage", backref="product", cascade="all, delete-orphan")

    @property
    def primary_image(self):
        if self.images:
            return self.images[0].url
        return url_for("static", filename="img/product-placeholder.svg")

    @property
    def discount_percent(self):
        if self.old_price and self.old_price > self.price:
            return round((1 - self.price / self.old_price) * 100)
        return 0

class ProductImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(700), nullable=False)
    path = db.Column(db.String(500), default="")
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Admin, int(user_id))

@app.context_processor
def inject_globals():
    return {
        "store_name": "Essencial",
        "whatsapp_number": os.getenv("WHATSAPP_NUMBER", "61998064041"),
        "current_year": datetime.now().year
    }

@app.route("/")
def home():
    active_categories = Category.query.filter_by(active=True).order_by(
        Category.sort_order, Category.name
    ).all()
    active_names = [category.name for category in active_categories]
    launches = Product.query.filter(
        Product.active.is_(True),
        Product.launch.is_(True),
        Product.category.in_(active_names)
    ).limit(4).all() if active_names else []
    bestsellers = Product.query.filter(
        Product.active.is_(True),
        Product.featured.is_(True),
        Product.category.in_(active_names)
    ).limit(4).all() if active_names else []
    return render_template(
        "home.html",
        launches=launches,
        bestsellers=bestsellers,
        categories=active_categories,
    )

@app.route("/catalogo")
def catalog():
    category_rows = Category.query.filter_by(active=True).order_by(Category.sort_order, Category.name).all()
    categories = [c.name for c in category_rows]
    products = Product.query.filter(
        Product.active.is_(True),
        Product.category.in_(categories)
    ).order_by(Product.created_at.desc()).all() if categories else []
    brands = sorted({p.brand for p in products})
    return render_template("catalog.html", products=products, categories=categories, brands=brands)

@app.route("/produto/<slug>")
def product_detail(slug):
    active_categories = db.session.query(Category.name).filter(Category.active.is_(True)).subquery()
    product = Product.query.filter(
        Product.slug == slug,
        Product.active.is_(True),
        Product.category.in_(db.select(active_categories.c.name))
    ).first_or_404()
    related = Product.query.filter(
        Product.category == product.category,
        Product.id != product.id,
        Product.active.is_(True)
    ).limit(4).all()
    return render_template("product.html", product=product, related=related)

@app.route("/api/produtos")
def api_products():
    q = request.args.get("q", "").lower().strip()
    category = request.args.get("category", "")
    brand = request.args.get("brand", "")
    size = request.args.get("size", "")
    color = request.args.get("color", "")
    availability = request.args.get("availability", "")
    promo = request.args.get("promo", "")
    launch = request.args.get("launch", "")
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)

    active_category_names = [c.name for c in Category.query.filter_by(active=True).all()]
    products = Product.query.filter(
        Product.active.is_(True),
        Product.category.in_(active_category_names)
    ).all() if active_category_names else []

    def matches(p):
        searchable = f"{p.name} {p.code} {p.category} {p.brand}".lower()
        return (
            (not q or q in searchable) and
            (not category or p.category == category) and
            (not brand or p.brand == brand) and
            (not size or size.lower() in p.sizes.lower()) and
            (not color or color.lower() in p.colors.lower()) and
            (not availability or p.status == availability) and
            (not promo or p.discount_percent > 0) and
            (not launch or p.launch) and
            (min_price is None or p.price >= min_price) and
            (max_price is None or p.price <= max_price)
        )

    data = [{
        "id": p.id,
        "name": p.name,
        "slug": p.slug,
        "code": p.code,
        "price": p.price,
        "old_price": p.old_price,
        "discount": p.discount_percent,
        "category": p.category,
        "brand": p.brand,
        "sizes": p.sizes,
        "colors": p.colors,
        "status": p.status,
        "image": p.primary_image
    } for p in products if matches(p)]
    return jsonify(data)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        admin = Admin.query.filter_by(username=request.form["username"]).first()
        if admin and check_password_hash(admin.password_hash, request.form["password"]):
            login_user(admin)
            return redirect(url_for("admin_dashboard"))
        flash("Usuário ou senha inválidos.", "error")
    return render_template("admin_login.html")

@app.route("/admin/logout")
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for("home"))

@app.route("/admin")
@login_required
def admin_dashboard():
    products = Product.query.order_by(Product.created_at.desc()).all()
    categories = Category.query.order_by(Category.sort_order, Category.name).all()
    return render_template("admin_dashboard.html", products=products, categories=categories)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
CATEGORY_BUCKET = os.getenv("SUPABASE_CATEGORY_BUCKET", "category-images")
PRODUCT_BUCKET = os.getenv("SUPABASE_PRODUCT_BUCKET", "product-images")


def _storage_headers(content_type=None):
    headers = {
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def validate_storage_config():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError(
            "Configure SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no arquivo .env."
        )


def upload_storage_image(file, bucket, folder):
    if not file or not file.filename:
        return None, None
    if not allowed_file(file.filename):
        raise ValueError("Formato inválido. Use PNG, JPG, JPEG ou WEBP.")

    validate_storage_config()
    ext = secure_filename(file.filename).rsplit(".", 1)[1].lower()
    object_path = f"{folder}/{uuid.uuid4().hex}.{ext}"
    content_type = file.mimetype or mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
    file.stream.seek(0)
    response = requests.post(
        f"{SUPABASE_URL}/storage/v1/object/{bucket}/{object_path}",
        headers={**_storage_headers(content_type), "x-upsert": "false"},
        data=file.stream.read(),
        timeout=45,
    )
    if response.status_code not in (200, 201):
        raise RuntimeError(f"Falha ao enviar imagem ao Supabase Storage: {response.text}")

    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{object_path}"
    return public_url, object_path


def delete_storage_image(bucket, object_path):
    if not object_path or not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return
    response = requests.delete(
        f"{SUPABASE_URL}/storage/v1/object/{bucket}",
        headers={**_storage_headers("application/json")},
        json={"prefixes": [object_path]},
        timeout=30,
    )
    if response.status_code not in (200, 204):
        app.logger.warning("Não foi possível remover a imagem do Storage: %s", response.text)


def upload_category_image(file, category_slug):
    return upload_storage_image(file, CATEGORY_BUCKET, f"categories/{category_slug}")


def delete_category_image(object_path):
    delete_storage_image(CATEGORY_BUCKET, object_path)


def save_product_images(files, product_slug):
    images = []
    for file in files:
        if file and file.filename:
            url, path = upload_storage_image(file, PRODUCT_BUCKET, f"products/{product_slug}")
            images.append((url, path))
    return images

@app.route("/admin/produto/novo", methods=["GET", "POST"])
@login_required
def admin_product_new():
    categories = Category.query.filter_by(active=True).order_by(Category.sort_order, Category.name).all()
    if request.method == "POST":
        uploaded_images = []
        try:
            name = request.form.get("name", "").strip()
            code = request.form.get("code", "").strip()
            brand = request.form.get("brand", "").strip()
            category_name = request.form.get("category", "").strip()
            price_text = request.form.get("price", "").strip().replace(",", ".")
            old_price_text = request.form.get("old_price", "").strip().replace(",", ".")
            stock_text = request.form.get("stock", "0").strip() or "0"

            if not name or not code or not brand or not price_text or not category_name:
                raise ValueError("Preencha todos os campos obrigatórios.")
            if Product.query.filter(db.func.lower(Product.code) == code.lower()).first():
                raise ValueError("Já existe um produto cadastrado com esse código.")
            if not Category.query.filter_by(name=category_name, active=True).first():
                raise ValueError("Selecione uma categoria ativa cadastrada no painel.")

            price = float(price_text)
            old_price = float(old_price_text) if old_price_text else None
            stock = int(stock_text)
            if price < 0 or (old_price is not None and old_price < 0) or stock < 0:
                raise ValueError("Preço, preço anterior e estoque não podem ser negativos.")

            product = Product(
                name=name,
                slug=slugify(name) + "-" + uuid.uuid4().hex[:5],
                code=code,
                price=price,
                old_price=old_price,
                category=category_name,
                brand=brand,
                sizes=request.form.get("sizes", ""),
                colors=request.form.get("colors", ""),
                material=request.form.get("material", ""),
                fit=request.form.get("fit", ""),
                gender=request.form.get("gender", ""),
                description=request.form.get("description", ""),
                stock=stock,
                status=request.form.get("status", "Em estoque"),
                featured="featured" in request.form,
                launch="launch" in request.form,
                active="active" in request.form,
            )
            db.session.add(product)
            db.session.flush()

            uploaded_images = save_product_images(request.files.getlist("images"), product.slug)
            for url, path in uploaded_images:
                db.session.add(ProductImage(url=url, path=path, product_id=product.id))
            db.session.commit()
            flash("Produto cadastrado com sucesso.", "success")
            return redirect(url_for("admin_dashboard"))

        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")
        except IntegrityError:
            db.session.rollback()
            flash("Não foi possível cadastrar. Verifique se o código do produto já existe.", "error")
        except (RuntimeError, requests.RequestException) as exc:
            db.session.rollback()
            app.logger.exception("Falha no upload da imagem do produto")
            flash(f"Não foi possível enviar a imagem: {exc}", "error")
        except SQLAlchemyError:
            db.session.rollback()
            app.logger.exception("Falha ao cadastrar produto no banco de dados")
            flash("Erro ao salvar o produto no banco. Verifique se as migrações do Supabase foram executadas.", "error")
        except Exception:
            db.session.rollback()
            app.logger.exception("Erro inesperado ao cadastrar produto")
            flash("Ocorreu um erro inesperado no cadastro. Consulte os logs do Render.", "error")

        for _, image_path in uploaded_images:
            try:
                delete_storage_image(PRODUCT_BUCKET, image_path)
            except Exception:
                app.logger.warning("Não foi possível limpar imagem órfã: %s", image_path)
        return render_template("admin_form.html", product=None, categories=categories)
    return render_template("admin_form.html", product=None, categories=categories)

@app.route("/admin/produto/<int:product_id>/editar", methods=["GET", "POST"])
@login_required
def admin_product_edit(product_id):
    product = Product.query.get_or_404(product_id)
    categories = Category.query.order_by(Category.sort_order, Category.name).all()
    if request.method == "POST":
        category_name = request.form.get("category", "").strip()
        category = Category.query.filter_by(name=category_name).first()
        if not category or (not category.active and category_name != product.category):
            flash("Selecione uma categoria válida.", "error")
            return render_template("admin_form.html", product=product, categories=categories)
        product.name = request.form["name"]
        product.code = request.form["code"]
        product.price = float(request.form["price"])
        product.old_price = float(request.form["old_price"]) if request.form.get("old_price") else None
        product.category = category_name
        product.brand = request.form["brand"]
        product.sizes = request.form.get("sizes", "")
        product.colors = request.form.get("colors", "")
        product.material = request.form.get("material", "")
        product.fit = request.form.get("fit", "")
        product.gender = request.form.get("gender", "")
        product.description = request.form.get("description", "")
        product.stock = int(request.form.get("stock", 0))
        product.status = request.form.get("status", "Em estoque")
        product.featured = "featured" in request.form
        product.launch = "launch" in request.form
        product.active = "active" in request.form
        try:
            uploaded_images = save_product_images(request.files.getlist("images"), product.slug)
        except (ValueError, RuntimeError) as exc:
            flash(str(exc), "error")
            return render_template("admin_form.html", product=product, categories=categories)
        for url, path in uploaded_images:
            db.session.add(ProductImage(url=url, path=path, product_id=product.id))
        db.session.commit()
        flash("Produto atualizado.", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin_form.html", product=product, categories=categories)

@app.route("/admin/categoria/nova", methods=["GET", "POST"])
@login_required
def admin_category_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Informe o nome da categoria.", "error")
            return render_template("admin_category_form.html", category=None)
        if Category.query.filter(db.func.lower(Category.name) == name.lower()).first():
            flash("Já existe uma categoria com esse nome.", "error")
            return render_template("admin_category_form.html", category=None)
        slug = slugify(name) or uuid.uuid4().hex[:8]
        if Category.query.filter_by(slug=slug).first():
            slug = f"{slug}-{uuid.uuid4().hex[:5]}"
        image_url = ""
        image_path = ""
        try:
            uploaded = request.files.get("image")
            if uploaded and uploaded.filename:
                image_url, image_path = upload_category_image(uploaded, slug)
        except (ValueError, RuntimeError) as exc:
            flash(str(exc), "error")
            return render_template("admin_category_form.html", category=None)

        category = Category(
            name=name,
            slug=slug,
            description=request.form.get("description", "").strip(),
            image_url=image_url,
            image_path=image_path,
            sort_order=int(request.form.get("sort_order") or 0),
            active="active" in request.form,
        )
        db.session.add(category)
        db.session.commit()
        flash("Categoria cadastrada com sucesso.", "success")
        return redirect(url_for("admin_dashboard") + "#categorias")
    return render_template("admin_category_form.html", category=None)

@app.route("/admin/categoria/<int:category_id>/editar", methods=["GET", "POST"])
@login_required
def admin_category_edit(category_id):
    category = Category.query.get_or_404(category_id)
    if request.method == "POST":
        old_name = category.name
        name = request.form.get("name", "").strip()
        duplicate = Category.query.filter(
            db.func.lower(Category.name) == name.lower(),
            Category.id != category.id
        ).first()
        if not name or duplicate:
            flash("Informe um nome válido e não repetido.", "error")
            return render_template("admin_category_form.html", category=category)
        category.name = name
        category.slug = slugify(name) or category.slug
        category.description = request.form.get("description", "").strip()
        category.sort_order = int(request.form.get("sort_order") or 0)
        category.active = "active" in request.form

        old_image_path = category.image_path
        remove_image = "remove_image" in request.form
        uploaded = request.files.get("image")
        try:
            if uploaded and uploaded.filename:
                new_url, new_path = upload_category_image(uploaded, category.slug)
                category.image_url = new_url
                category.image_path = new_path
                if old_image_path:
                    delete_category_image(old_image_path)
            elif remove_image:
                category.image_url = ""
                category.image_path = ""
                if old_image_path:
                    delete_category_image(old_image_path)
        except (ValueError, RuntimeError) as exc:
            flash(str(exc), "error")
            return render_template("admin_category_form.html", category=category)

        if old_name != name:
            Product.query.filter_by(category=old_name).update({"category": name})
        db.session.commit()
        flash("Categoria atualizada.", "success")
        return redirect(url_for("admin_dashboard") + "#categorias")
    return render_template("admin_category_form.html", category=category)

@app.post("/admin/categoria/<int:category_id>/toggle")
@login_required
def admin_category_toggle(category_id):
    category = Category.query.get_or_404(category_id)
    category.active = not category.active
    db.session.commit()
    flash("Visibilidade da categoria atualizada.", "success")
    return redirect(url_for("admin_dashboard") + "#categorias")

@app.post("/admin/categoria/<int:category_id>/excluir")
@login_required
def admin_category_delete(category_id):
    category = Category.query.get_or_404(category_id)
    product_count = Product.query.filter_by(category=category.name).count()
    if product_count:
        flash(f"Não é possível excluir: há {product_count} produto(s) nesta categoria.", "error")
        return redirect(url_for("admin_dashboard") + "#categorias")
    image_path = category.image_path
    db.session.delete(category)
    db.session.commit()
    if image_path:
        delete_category_image(image_path)
    flash("Categoria excluída.", "success")
    return redirect(url_for("admin_dashboard") + "#categorias")

@app.post("/admin/produto/<int:product_id>/excluir")
@login_required
def admin_product_delete(product_id):
    product = Product.query.get_or_404(product_id)
    image_paths = [image.path for image in product.images if image.path]
    db.session.delete(product)
    db.session.commit()
    for image_path in image_paths:
        delete_storage_image(PRODUCT_BUCKET, image_path)
    flash("Produto excluído.", "success")
    return redirect(url_for("admin_dashboard"))

@app.post("/admin/produto/<int:product_id>/toggle")
@login_required
def admin_product_toggle(product_id):
    product = Product.query.get_or_404(product_id)
    product.active = not product.active
    db.session.commit()
    return redirect(url_for("admin_dashboard"))

@app.route("/api/health/database")
def database_health():
    """Verifica se a aplicação consegue consultar o banco de dados."""
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify({"database": "connected", "provider": "supabase-postgres"}), 200
    except Exception as exc:
        app.logger.exception("Falha na conexão com o banco")
        return jsonify({"database": "disconnected", "error": str(exc)}), 503

@app.route("/robots.txt")
def robots():
    return Response("User-agent: *\nAllow: /\nSitemap: /sitemap.xml", mimetype="text/plain")

@app.route("/sitemap.xml")
def sitemap():
    products = Product.query.filter_by(active=True).all()
    urls = [url_for("home", _external=True), url_for("catalog", _external=True)]
    urls += [url_for("product_detail", slug=p.slug, _external=True) for p in products]
    xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    xml += "".join(f"<url><loc>{u}</loc></url>" for u in urls)
    xml += "</urlset>"
    return Response(xml, mimetype="application/xml")

def initialize_database():
    """Cria tabelas e aplica pequenas migrações compatíveis com instalações existentes."""
    db.create_all()
    # db.create_all() não adiciona colunas em tabelas já existentes.
    # Estas alterações evitam erro 500 ao salvar caminhos das imagens no Supabase Storage.
    if database_url.startswith("postgresql"):
        db.session.execute(db.text("ALTER TABLE product_image ADD COLUMN IF NOT EXISTS path VARCHAR(500) DEFAULT ''"))
        db.session.execute(db.text("ALTER TABLE category ADD COLUMN IF NOT EXISTS image_url VARCHAR(700) DEFAULT ''"))
        db.session.execute(db.text("ALTER TABLE category ADD COLUMN IF NOT EXISTS image_path VARCHAR(500) DEFAULT ''"))
        db.session.commit()
    existing_names = {c.name.lower() for c in Category.query.all()}
    product_categories = db.session.query(Product.category).filter(
        Product.category.isnot(None), Product.category != ""
    ).distinct().all()
    changed = False
    for (name,) in product_categories:
        clean_name = (name or "").strip()
        if clean_name and clean_name.lower() not in existing_names:
            base_slug = slugify(clean_name) or uuid.uuid4().hex[:8]
            category_slug = base_slug
            if Category.query.filter_by(slug=category_slug).first():
                category_slug = f"{base_slug}-{uuid.uuid4().hex[:5]}"
            db.session.add(Category(name=clean_name, slug=category_slug, active=True))
            existing_names.add(clean_name.lower())
            changed = True
    if changed:
        db.session.commit()


def create_admin_from_env():
    """Cria um administrador somente quando credenciais explícitas forem informadas."""
    username = os.getenv("ADMIN_USER", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "").strip()
    if not username or not password:
        raise RuntimeError("Defina ADMIN_USER e ADMIN_PASSWORD no .env antes de criar o administrador.")
    if Admin.query.filter_by(username=username).first():
        return False
    db.session.add(Admin(username=username, password_hash=generate_password_hash(password)))
    db.session.commit()
    return True

if __name__ == "__main__":
    with app.app_context():
        initialize_database()
        if os.getenv("CREATE_ADMIN_ON_START", "0") == "1":
            created = create_admin_from_env()
            if created:
                app.logger.warning("Administrador inicial criado a partir do .env.")
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
