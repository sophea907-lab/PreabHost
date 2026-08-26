from flask import Flask, render_template, request, make_response, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import timedelta
import json
import datetime
from product import products, get_product_category, get_product_title, get_product_id
from config import Config
from extension import db, migrate
from models import User
from helper import upload_image

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
migrate.init_app(app, db)

with app.app_context():
    db.create_all()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to access the Admin Terminal.", "warning")
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_only(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to access the Admin Terminal.", "warning")
            return redirect(url_for("admin_login", next=request.path))
        if (session.get("user_role") or "").lower() == "staff":
            flash("Access restricted: Staff members cannot access the User Directory.", "danger")
            return redirect(url_for("admin_dashboard"))
        return view(*args, **kwargs)
    return wrapped



# Global in-memory storage for orders
orders = []
users = []

@app.route('/')
def home():
    for item in products:
        print(item['title'])

    return render_template('front/index.html', products=products)

@app.route('/shop')
def shop():
    return render_template('front/products.html', products=products)

@app.route('/product/<product_name>')
def product(product_name):
    from product import get_product_title
    product = get_product_title(product_name)
    if product is None:
        return "Product not found", 404
    related_product = get_product_category(product['category'])
    return render_template('front/product.html', product=product, related_product=related_product)

@app.route('/cart')
def cart():
    product_id = request.args.get("product_id")
    qty = request.args.get("qty", 1, type=int)
    
    cart_list = request.cookies.get('cart_list')
    try:
        cart_list = json.loads(cart_list) if cart_list else []
    except Exception:
        cart_list = []
    
    if product_id:
        from product import get_product_id
        cart_product = get_product_id(product_id)
        if cart_product:
            found = False
            for item in cart_list:
                if str(item['id']) == str(product_id):
                    item['qty'] += qty
                    if item['qty'] <= 0:
                        cart_list.remove(item)
                    found = True
                    break

            if not found and qty > 0:
                cart_list.append(
                    {
                        "id" : cart_product['id'],
                        "title" : cart_product['title'],
                        "qty" : qty,
                        "price" : cart_product['price'],
                        "category" : cart_product['category'],
                        "image" : cart_product['image'],
                        "description" : cart_product['description'],
                    }
                )

            resp = redirect(url_for('cart'))
            resp.set_cookie('cart_list', json.dumps(cart_list))
            return resp

    return render_template("front/cart.html", cart_list=cart_list)

@app.route('/cart/remove')
def cart_remove():
    product_id = request.args.get("product_id")
    cart_list = request.cookies.get('cart_list')
    try:
        cart_list = json.loads(cart_list) if cart_list else []
    except Exception:
        cart_list = []
    
    if product_id:
        cart_list = [item for item in cart_list if str(item['id']) != str(product_id)]
        resp = redirect(url_for('cart'))
        resp.set_cookie('cart_list', json.dumps(cart_list))
        return resp
        
    return redirect(url_for('cart'))

# @app.context_processor
# def inject_cart_count():
#     cart_list = request.cookies.get('cart_list')
#     try:
#         cart_list = json.loads(cart_list) if cart_list else []
#     except Exception:
#         cart_list = []
#     count = sum(item.get('qty', 1) for item in cart_list)
#     return dict(cart_count=count)

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart_list = request.cookies.get('cart_list')
    try:
        cart_list = json.loads(cart_list) if cart_list else []
    except Exception:
        cart_list = []

    # telegram BOT
    if request.method == 'POST':
        # Telegram Bot Credentials - Replace these with your actual keys
        TELEGRAM_BOT_TOKEN = "8444491707:AAEevkdpW3Cr9qp326161W7uv8tFh70wHU0"
        TELEGRAM_CHAT_ID = "-1003803032717"

        first_name = request.form.get('firstName')
        last_name = request.form.get('lastName')
        address = request.form.get('address')
        city = request.form.get('city')
        zip_code = request.form.get('zip')

        if cart_list:
            subtotal = sum(item['price'] * item['qty'] for item in cart_list)
            shipping = 15.00 if subtotal > 0 else 0
            tax = subtotal * 0.08
            total = subtotal + shipping + tax

            msg = f"🛒 *New Order Received!*\n\n"
            msg += f"👤 *Customer:* {first_name} {last_name}\n"
            msg += f"📍 *Address:* {address}, {city}, {zip_code}\n\n"
            msg += f"🛍️ *Items:*\n"
            for item in cart_list:
                msg += f"- {item['title']} (x{item['qty']}): ${item['price'] * item['qty']:.2f}\n"
            
            msg += f"\n💰 *Subtotal:* ${subtotal:.2f}\n"
            msg += f"🚚 *Shipping:* ${shipping:.2f}\n"
            msg += f"🧾 *Tax:* ${tax:.2f}\n"
            msg += f"💳 *Total:* ${total:.2f}\n"

            if TELEGRAM_BOT_TOKEN != "YOUR_TELEGRAM_BOT_TOKEN" and TELEGRAM_CHAT_ID != "YOUR_TELEGRAM_CHAT_ID":
                import urllib.request
                import json as json_lib
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                payload = {
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": msg,
                    "parse_mode": "Markdown"
                }
                try:
                    req = urllib.request.Request(url, data=json_lib.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
                    urllib.request.urlopen(req)
                except Exception as e:
                    print(f"Error sending Telegram message: {e}")

            # Store order in our in-memory orders list
            email_placeholder = f"{first_name.lower()}.{last_name.lower()}@example.com"
            new_order = {
                "id": len(orders) + 1,
                "customer_name": f"{first_name} {last_name}",
                "email": email_placeholder,
                "address": f"{address}, {city}, {zip_code}",
                "items": cart_list,
                "subtotal": subtotal,
                "shipping": shipping,
                "tax": tax,
                "total": total,
                "status": "Pending",
                "date": datetime.date.today().isoformat()
            }
            orders.append(new_order)

            # Auto-register user in user base if new email
            if not any(u['email'].lower() == email_placeholder.lower() for u in users):
                users.append({
                    "id": len(users) + 1,
                    "username": f"{first_name} {last_name}",
                    "name": f"{first_name} {last_name}",
                    "email": email_placeholder,
                    "password": "auto-generated",
                    "role": "Customer",
                    "profile": "",
                    "date": datetime.date.today().isoformat()
                })


        resp = make_response(redirect(url_for('home')))
        resp.set_cookie('cart_list', '', expires=0)
        return resp

    return render_template('front/checkout.html', cart_list=cart_list)

@app.route('/account')
def account():
    return render_template('front/account.html')

@app.route('/login')
def login():
    return render_template('front/createUser.html')
    
@app.route('/register')
def register():
    return render_template('front/createUser.html')
    
@app.route('/forgot-password')
def forgot_password():
    return render_template('front/forgotPw.html')

@app.route('/admin')
def admin():
    if session.get("user_id"):
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('admin_login'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get("user_id"):
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        identity = (request.form.get('identity') or request.form.get('username') or '').strip()
        password = request.form.get('password', '')

        # Check database User or preset admin credentials
        user = User.query.filter((User.email == identity) | (User.fullname == identity)).first()
        is_valid = user.check_password(password) if user else False

        if user and is_valid and user.role.lower() in ['admin', 'administrator', 'super administrator', 'staff']:
            session.clear()
            session.permanent = bool(request.form.get('remember_me') or request.form.get('remember'))
            session["user_id"] = user.id
            session["username"] = user.fullname or user.email
            session["user_email"] = user.email
            session["user_role"] = user.role
            session["user_image"] = user.image
            flash(f"Welcome back, {user.fullname or user.role}!", "success")
            return redirect(request.args.get('next') or url_for('admin_dashboard'))
        elif identity == 'admin@pspstore.com' and password == 'admin123':
            session.clear()
            session.permanent = bool(request.form.get('remember_me') or request.form.get('remember'))
            session["user_id"] = 9999
            session["username"] = 'Sophea Preab'
            session["user_email"] = 'admin@pspstore.com'
            session["user_role"] = 'Super Administrator'
            flash("Welcome back, Super Administrator!", "success")
            return redirect(request.args.get('next') or url_for('admin_dashboard'))
        elif user and is_valid:
            flash('Access denied. Administrator or Staff privileges required for this portal.', 'danger')
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('admin/auth/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    flash('You have been securely signed out.', 'info')
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    return render_template('admin/dashbord/index.html', active_tab='dashboard')

@app.route('/admin/products')
@login_required
def admin_products():
    return render_template('admin/product/index.html', active_tab='products')

@app.route('/admin/orders')
@login_required
def admin_orders():
    return render_template('admin/order/index.html', active_tab='orders')

@app.route('/admin/users')
@login_required
@admin_only
def admin_users():
    users_list = User.query.order_by(User.id.asc()).all()
    return render_template('admin/user/index.html', active_tab='users', users=users_list)

@app.route('/admin/users/create', methods=['GET', 'POST'])
@login_required
@admin_only
def admin_users_create():
    if request.method == 'POST':
        fullname = request.form.get('fullname') or request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'Customer')
        status = request.form.get('status', 'Active')
        
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            image_path = upload_image(file)

        new_user = User(
            fullname=fullname,
            email=email,
            password=generate_password_hash(password) if password else '',
            role=role,
            status=status,
            image=image_path
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('admin_users'))
    return render_template('admin/user/create.html', active_tab='users')

@app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_only
def admin_users_edit(user_id):
    target_user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        target_user.fullname = request.form.get('fullname') or request.form.get('username')
        target_user.email = request.form.get('email')
        
        password = request.form.get('password')
        if password and password != target_user.password:
            target_user.password = generate_password_hash(password)

        target_user.role = request.form.get('role', 'Customer')
        target_user.status = request.form.get('status', 'Active')
        target_user.update_at = datetime.datetime.utcnow()

        if 'image' in request.files and request.files['image'].filename:
            file = request.files['image']
            uploaded = upload_image(file)
            if uploaded:
                target_user.image = uploaded

        db.session.commit()

        # If current logged in user edited their own profile, sync session
        if session.get("user_id") == target_user.id:
            session["username"] = target_user.fullname or target_user.email
            session["user_role"] = target_user.role
            session["user_image"] = target_user.image

        return redirect(url_for('admin_users'))
        
    return render_template('admin/user/edit.html', active_tab='users', user=target_user)

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_only
def admin_users_delete(user_id):
    target_user = User.query.get(user_id)
    if target_user:
        db.session.delete(target_user)
        db.session.commit()
    return redirect(url_for('admin_users'))

@app.route('/admin/settings')
@login_required
def admin_settings():
    return render_template('admin/settings/index.html', active_tab='settings')

if __name__ == '__main__':
    app.run(debug=True)
