from flask import render_template, request, make_response, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash
import json
import datetime
import urllib.request
from extension import db, limiter
from models import User, Category, Product, ProductImage, Order, OrderItem
from helper import upload_image
from . import front_bp

# Global in-memory storage for orders and customers
orders = []
users = []


@front_bp.route('/')
def home():
    products_list = Product.query.order_by(Product.id.asc()).all()
    categories_list = Category.query.order_by(Category.name.asc()).all()
    return render_template('front/index.html', products=products_list, categories=categories_list)


@front_bp.route('/shop')
def shop():
    cat_param = request.args.get('category', '').strip()
    search_query = request.args.get('q', '').strip()
    sort_param = request.args.get('sort', '').strip()

    query = Product.query

    if cat_param and cat_param.lower() != 'all':
        if cat_param.isdigit():
            query = query.filter(Product.CategoryId == int(cat_param))
        else:
            query = query.join(Category).filter(db.func.lower(Category.name) == cat_param.lower())

    if search_query:
        query = query.filter(db.or_(
            Product.name.ilike(f"%{search_query}%"),
            Product.description.ilike(f"%{search_query}%")
        ))

    if sort_param == 'price_asc':
        query = query.order_by(Product.Price.asc())
    elif sort_param == 'price_desc':
        query = query.order_by(Product.Price.desc())
    elif sort_param == 'newest':
        query = query.order_by(Product.id.desc())
    else:
        query = query.order_by(Product.id.asc())

    products_list = query.all()
    categories_list = Category.query.order_by(Category.name.asc()).all()

    return render_template(
        'front/products.html',
        products=products_list,
        categories=categories_list,
        active_category=cat_param,
        search_query=search_query,
        current_sort=sort_param
    )


@front_bp.route('/product/<product_name>')
def product(product_name):
    product_item = None
    if str(product_name).isdigit():
        product_item = Product.query.get(int(product_name))
    if not product_item:
        product_item = Product.query.filter(Product.name == product_name).first()
    if not product_item:
        product_item = Product.query.filter(Product.name.ilike(f"%{product_name.strip()}%")).first()

    if product_item is None:
        flash("Product not found.", "warning")
        return redirect(url_for('front.shop'))

    related_product = Product.query.filter(
        Product.CategoryId == product_item.CategoryId,
        Product.id != product_item.id
    ).limit(4).all()

    return render_template('front/product.html', product=product_item, related_product=related_product)


@front_bp.route('/cart')
def cart():
    product_id = request.args.get("product_id")
    qty = request.args.get("qty", 1, type=int)
    
    cart_list = request.cookies.get('cart_list')
    try:
        cart_list = json.loads(cart_list) if cart_list else []
    except Exception:
        cart_list = []
    
    if product_id and str(product_id).isdigit():
        cart_product = Product.query.get(int(product_id))
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
                        "id": cart_product.id,
                        "title": cart_product.name,
                        "qty": qty,
                        "price": float(cart_product.Price or 0.0),
                        "category": cart_product.category.name if cart_product.category else '',
                        "image": cart_product.thumbnail or (cart_product.images[0].name if cart_product.images else ''),
                        "description": cart_product.description or '',
                    }
                )

            resp = redirect(url_for('front.cart'))
            resp.set_cookie('cart_list', json.dumps(cart_list))
            return resp

    return render_template("front/cart.html", cart_list=cart_list)


@front_bp.route('/cart/remove')
def cart_remove():
    product_id = request.args.get("product_id")
    cart_list = request.cookies.get('cart_list')
    try:
        cart_list = json.loads(cart_list) if cart_list else []
    except Exception:
        cart_list = []
    
    if product_id:
        cart_list = [item for item in cart_list if str(item['id']) != str(product_id)]
        resp = redirect(url_for('front.cart'))
        resp.set_cookie('cart_list', json.dumps(cart_list))
        return resp
        
    return redirect(url_for('front.cart'))


@front_bp.route('/checkout', methods=['GET', 'POST'])
@limiter.limit("20 per hour")
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

        first_name = (request.form.get('firstName') or '').strip()
        last_name = (request.form.get('lastName') or '').strip()
        email_addr = (request.form.get('email') or session.get('user_email') or f"{first_name.lower()}.{last_name.lower()}@example.com").strip()
        phone_num = (request.form.get('phone') or '').strip()
        address = (request.form.get('address') or '').strip()
        city = (request.form.get('city') or '').strip()
        zip_code = (request.form.get('zip') or '').strip()

        if cart_list:
            subtotal = sum(item['price'] * item['qty'] for item in cart_list)
            shipping = 15.00 if subtotal > 0 else 0
            tax = round(subtotal * 0.08, 2)
            total = round(subtotal + shipping + tax, 2)

            customer_fullname = f"{first_name} {last_name}".strip() or "Valued Customer"

            # Create Database Order record
            db_order = Order(
                user_id=session.get('user_id'),
                customer_name=customer_fullname,
                email=email_addr,
                phone=phone_num,
                address=address,
                city=city,
                zip_code=zip_code,
                subtotal=subtotal,
                shipping=shipping,
                tax=tax,
                total=total,
                status="Pending"
            )
            db.session.add(db_order)
            db.session.flush()

            for item in cart_list:
                item_prod_id = item.get('id') if str(item.get('id', '')).isdigit() else None
                order_item = OrderItem(
                    order_id=db_order.id,
                    product_id=int(item_prod_id) if item_prod_id else None,
                    product_name=item.get('title', 'Product'),
                    price=float(item.get('price', 0.0)),
                    quantity=int(item.get('qty', 1)),
                    thumbnail=item.get('image')
                )
                db.session.add(order_item)

                # Decrement stock if product exists
                if item_prod_id:
                    prod = Product.query.get(int(item_prod_id))
                    if prod and prod.Stock is not None:
                        prod.Stock = max(0, prod.Stock - int(item.get('qty', 1)))

            db.session.commit()

            # Telegram notification
            msg = f"🛒 *New Order Received (#{db_order.id})!*\n\n"
            msg += f"👤 *Customer:* {customer_fullname}\n"
            msg += f"📧 *Email:* {email_addr}\n"
            if phone_num:
                msg += f"📞 *Phone:* {phone_num}\n"
            msg += f"📍 *Address:* {address}, {city}, {zip_code}\n\n"
            msg += f"🛍️ *Items:*\n"
            for item in cart_list:
                msg += f"- {item['title']} (x{item['qty']}): ${item['price'] * item['qty']:.2f}\n"
            msg += f"\n💰 *Subtotal:* ${subtotal:.2f}\n"
            msg += f"🚚 *Shipping:* ${shipping:.2f}\n"
            msg += f"🧾 *Tax:* ${tax:.2f}\n"
            msg += f"💳 *Total:* ${total:.2f}\n"

            if TELEGRAM_BOT_TOKEN != "YOUR_TELEGRAM_BOT_TOKEN" and TELEGRAM_CHAT_ID != "YOUR_TELEGRAM_CHAT_ID":
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                payload = {
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": msg,
                    "parse_mode": "Markdown"
                }
                try:
                    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
                    urllib.request.urlopen(req)
                except Exception as e:
                    print(f"Error sending Telegram message: {e}")

            flash(f"Order #{db_order.id} placed successfully! Thank you for shopping with PSPStore.", "success")
            resp = make_response(redirect(url_for('front.home')))
            resp.set_cookie('cart_list', '', expires=0)
            return resp

    return render_template('front/checkout.html', cart_list=cart_list)


@front_bp.route('/account', methods=['GET', 'POST'])
def account():
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in to access your profile settings.", "warning")
        return redirect(url_for('front.login', next=request.path))

    user_role = (session.get("user_role") or "").lower()
    if user_role in ['admin', 'administrator', 'super administrator', 'staff']:
        flash("Administrators should manage settings in the Admin Terminal.", "info")
        return redirect(url_for('admin.admin_dashboard'))

    current_user = User.query.get(user_id)
    if not current_user:
        session.clear()
        return redirect(url_for('front.login'))

    if request.method == 'POST':
        fullname = (request.form.get('fullname') or '').strip()
        email = (request.form.get('email') or '').strip()
        new_password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if fullname:
            current_user.fullname = fullname

        if email:
            existing = User.query.filter(User.email.ilike(email)).first()
            if existing and existing.id != current_user.id:
                flash("This email address is already in use by another account.", "danger")
                return render_template('front/account.html', current_user=current_user)
            current_user.email = email

        if new_password:
            if new_password != confirm_password:
                flash("New passwords do not match. Please re-enter.", "danger")
                return render_template('front/account.html', current_user=current_user)
            current_user.password = generate_password_hash(new_password)

        if 'image' in request.files and request.files['image'].filename:
            uploaded = upload_image(request.files['image'])
            if uploaded:
                current_user.image = uploaded

        current_user.update_at = datetime.datetime.utcnow()
        db.session.commit()

        # Update session
        session["username"] = current_user.fullname or current_user.email
        session["user_email"] = current_user.email
        session["user_image"] = current_user.image
        flash("Profile settings saved successfully!", "success")
        return redirect(url_for('front.account'))

    return render_template('front/account.html', current_user=current_user)


@front_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if session.get("user_id"):
        user_role = (session.get("user_role") or "").lower()
        if user_role in ['admin', 'administrator', 'super administrator', 'staff']:
            return redirect(url_for('admin.admin_dashboard'))
        return redirect(url_for('front.account'))

    if request.method == 'POST':
        email = (request.form.get('email') or '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        # Admins & Staff CANNOT log in on the front storefront
        if email.lower() == 'admin@pspstore.com':
            flash("Access restricted: Administrator accounts must log in via the Admin Portal.", "danger")
            return redirect(url_for('admin.admin_login'))

        # Check DB User
        user = User.query.filter(User.email.ilike(email)).first()
        if user and (user.role or "").lower() in ['admin', 'administrator', 'super administrator', 'staff']:
            flash("Access restricted: Administrator and Staff accounts cannot log in on the storefront. Please use the Admin Portal.", "danger")
            return redirect(url_for('admin.admin_login'))

        if user and user.check_password(password):
            # Only Customer accounts can log in on the front
            session.clear()
            session.permanent = remember
            session["user_id"] = user.id
            session["username"] = user.fullname or user.email
            session["user_email"] = user.email
            session["user_role"] = user.role
            session["user_image"] = user.image
            flash(f"Welcome back, {user.fullname or 'Customer'}!", "success")
            next_url = request.args.get('next') or url_for('front.account')
            return redirect(next_url)
        else:
            flash("Invalid email or password. Please check your credentials.", "danger")

    return render_template('front/login.html')


@front_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def register():
    if session.get("user_id"):
        return redirect(url_for('front.account'))

    if request.method == 'POST':
        fullname = (request.form.get('fullname') or '').strip()
        email = (request.form.get('email') or '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not email or not password:
            flash("Please enter all required fields.", "warning")
            return render_template('front/register.html')

        if password != confirm_password:
            flash("Passwords do not match.", "warning")
            return render_template('front/register.html')

        if User.query.filter(User.email.ilike(email)).first():
            flash("An account with this email address already exists. Please sign in.", "danger")
            return redirect(url_for('front.login'))

        new_user = User(
            fullname=fullname or email.split('@')[0],
            email=email,
            password=generate_password_hash(password),
            role="Customer",
            status="Active"
        )
        db.session.add(new_user)
        db.session.commit()

        session.clear()
        session["user_id"] = new_user.id
        session["username"] = new_user.fullname
        session["user_email"] = new_user.email
        session["user_role"] = new_user.role
        flash(f"Your account has been created! Welcome to PSPSTORE, {new_user.fullname}.", "success")
        return redirect(url_for('front.account'))

    return render_template('front/register.html')


@front_bp.route('/logout')
def logout():
    session.clear()
    flash("You have been securely signed out.", "info")
    return redirect(url_for('front.login'))


@front_bp.route('/forgot-password')
def forgot_password():
    return render_template('front/forgotPw.html')

