from flask import render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash
import datetime
from extension import db, limiter
from models import User, Category, Product, ProductImage, Order, OrderItem
from helper import upload_image
from auth import login_required, admin_only, super_admin_only, authenticate_admin, is_admin_user
from . import admin_bp


@admin_bp.route('/')
@admin_bp.route('')
def admin():
    if is_admin_user():
        return redirect(url_for('admin.admin_dashboard'))
    return redirect(url_for('admin.admin_login'))


@admin_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def admin_login():
    if is_admin_user():
        return redirect(url_for('admin.admin_dashboard'))

    if request.method == 'POST':
        identity = (request.form.get('identity') or request.form.get('username') or '').strip()
        password = request.form.get('password', '')

        admin_user, error = authenticate_admin(identity, password)
        if admin_user:
            session.clear()
            session.permanent = bool(request.form.get('remember_me') or request.form.get('remember'))
            # Handle either ORM User object or mock admin dictionary
            if isinstance(admin_user, dict):
                session["user_id"] = admin_user["id"]
                session["username"] = admin_user["fullname"]
                session["user_email"] = admin_user["email"]
                session["user_role"] = admin_user["role"]
                session["user_image"] = admin_user.get("image")
                display_name = admin_user["fullname"]
            else:
                session["user_id"] = admin_user.id
                session["username"] = admin_user.fullname or admin_user.email
                session["user_email"] = admin_user.email
                session["user_role"] = admin_user.role
                session["user_image"] = admin_user.image
                display_name = admin_user.fullname or admin_user.role

            flash(f"Welcome back, {display_name}!", "success")
            return redirect(request.args.get('next') or url_for('admin.admin_dashboard'))
        else:
            flash(error or 'Invalid username or password.', 'danger')

    return render_template('admin/auth/login.html')


@admin_bp.route('/logout')
def admin_logout():
    session.clear()
    flash('You have been securely signed out.', 'info')
    return redirect(url_for('admin.admin_login'))


@admin_bp.route('/dashboard')
@login_required
def admin_dashboard():
    # 1. KPI Metrics
    completed_sales = db.session.query(db.func.sum(Order.total)).filter(Order.status.in_(['Delivered', 'Completed'])).scalar() or 0.0
    completed_sales = float(completed_sales)

    active_orders = Order.query.filter(Order.status.in_(['Pending', 'Processing'])).count()

    total_stock = db.session.query(db.func.sum(Product.Stock)).scalar() or 0
    total_products = Product.query.count()
    total_categories = Category.query.count()
    total_users = User.query.count()

    avg_rating = 4.9

    # 2. Sales Timeline Data (Past 7 days)
    today = datetime.date.today()
    date_objs = [today - datetime.timedelta(days=i) for i in range(6, -1, -1)]
    timeline_labels = [d.strftime('%b %d') for d in date_objs]
    timeline_values = [0.0] * 7

    orders = Order.query.filter(Order.status != 'Cancelled').all()
    for o in orders:
        if o.created_at:
            try:
                od = o.created_at.date()
                for idx, d in enumerate(date_objs):
                    if od == d:
                        timeline_values[idx] += float(o.total or 0.0)
            except Exception:
                pass

    timeline_values = [round(v, 2) for v in timeline_values]

    # 3. Stock Category Mix Data
    categories = Category.query.all()
    cat_labels = [c.name for c in categories]
    cat_counts = [len(c.products) for c in categories]

    if not cat_labels:
        cat_labels = ["No Categories"]
        cat_counts = [0]

    # 4. Recent Orders (Latest 6 orders)
    recent_orders = Order.query.order_by(Order.id.desc()).limit(6).all()

    return render_template(
        'admin/dashbord/index.html',
        active_tab='dashboard',
        completed_sales=completed_sales,
        active_orders=active_orders,
        total_stock=total_stock,
        total_products=total_products,
        total_categories=total_categories,
        total_users=total_users,
        avg_rating=avg_rating,
        timeline_labels=timeline_labels,
        timeline_values=timeline_values,
        cat_labels=cat_labels,
        cat_counts=cat_counts,
        recent_orders=recent_orders
    )


# ================= CATEGORY MANAGEMENT =================
@admin_bp.route('/categories')
@login_required
def admin_categories():
    categories_list = Category.query.order_by(Category.id.asc()).all()
    return render_template('admin/category/index.html', active_tab='categories', categories=categories_list)


@admin_bp.route('/categories/create', methods=['GET', 'POST'])
@login_required
@admin_only
def admin_categories_create():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        image_path = None
        if 'image' in request.files and request.files['image'].filename:
            image_path = upload_image(request.files['image'])

        new_cat = Category(
            name=name,
            image=image_path,
            description=description
        )
        db.session.add(new_cat)
        db.session.commit()
        flash(f"Category '{name}' created successfully!", "success")
        return redirect(url_for('admin.admin_categories'))

    return render_template('admin/category/create.html', active_tab='categories')


@admin_bp.route('/categories/edit/<int:cat_id>', methods=['GET', 'POST'])
@login_required
@admin_only
def admin_categories_edit(cat_id):
    target_cat = Category.query.get_or_404(cat_id)
    if request.method == 'POST':
        target_cat.name = request.form.get('name', '').strip()
        target_cat.description = request.form.get('description', '').strip()
        if 'image' in request.files and request.files['image'].filename:
            uploaded = upload_image(request.files['image'])
            if uploaded:
                target_cat.image = uploaded

        db.session.commit()
        flash(f"Category '{target_cat.name}' updated successfully!", "success")
        return redirect(url_for('admin.admin_categories'))

    return render_template('admin/category/edit.html', active_tab='categories', category=target_cat)


@admin_bp.route('/categories/delete/<int:cat_id>', methods=['POST'])
@login_required
@admin_only
def admin_categories_delete(cat_id):
    target_cat = Category.query.get_or_404(cat_id)
    cat_name = target_cat.name
    db.session.delete(target_cat)
    db.session.commit()
    flash(f"Category '{cat_name}' deleted.", "info")
    return redirect(url_for('admin.admin_categories'))


# ================= PRODUCT MANAGEMENT =================
@admin_bp.route('/products')
@login_required
def admin_products():
    products_list = Product.query.order_by(Product.id.desc()).all()
    categories_list = Category.query.order_by(Category.name.asc()).all()
    return render_template('admin/product/index.html', active_tab='products', products=products_list, categories=categories_list)


@admin_bp.route('/products/create', methods=['GET', 'POST'])
@login_required
@admin_only
def admin_products_create():
    categories_list = Category.query.order_by(Category.name.asc()).all()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        cat_id = request.form.get('CategoryId', type=int)
        cost_val = request.form.get('Cost', type=float) or 0.0
        price_val = request.form.get('Price', type=float) or 0.0
        stock_val = request.form.get('Stock', 0, type=int)
        description = request.form.get('description', '').strip()

        thumbnail_path = None
        if 'thumbnail' in request.files and request.files['thumbnail'].filename:
            thumbnail_path = upload_image(request.files['thumbnail'])

        new_prod = Product(
            name=name,
            thumbnail=thumbnail_path,
            Cost=cost_val,
            Price=price_val,
            Stock=stock_val,
            CategoryId=cat_id,
            description=description
        )
        db.session.add(new_prod)
        db.session.flush()

        # Gallery images
        if 'gallery_images' in request.files:
            files = request.files.getlist('gallery_images')
            for f in files:
                if f and f.filename:
                    uploaded_gal = upload_image(f)
                    if uploaded_gal:
                        gallery_entry = ProductImage(ProductId=new_prod.id, name=uploaded_gal)
                        db.session.add(gallery_entry)

        # If no gallery images uploaded but thumbnail exists, add thumbnail as gallery image
        if not new_prod.images and thumbnail_path:
            db.session.add(ProductImage(ProductId=new_prod.id, name=thumbnail_path))

        db.session.commit()
        flash(f"Product '{name}' created successfully!", "success")
        return redirect(url_for('admin.admin_products'))

    return render_template('admin/product/create.html', active_tab='products', categories=categories_list)


@admin_bp.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
@admin_only
def admin_products_edit(product_id):
    product_item = Product.query.get_or_404(product_id)
    categories_list = Category.query.order_by(Category.name.asc()).all()

    if request.method == 'POST':
        product_item.name = request.form.get('name', '').strip()
        product_item.CategoryId = request.form.get('CategoryId', type=int)
        product_item.Cost = request.form.get('Cost', type=float) or 0.0
        product_item.Price = request.form.get('Price', type=float) or 0.0
        product_item.Stock = request.form.get('Stock', 0, type=int)
        product_item.description = request.form.get('description', '').strip()

        if 'thumbnail' in request.files and request.files['thumbnail'].filename:
            uploaded_thumb = upload_image(request.files['thumbnail'])
            if uploaded_thumb:
                product_item.thumbnail = uploaded_thumb

        # Additional gallery images
        if 'gallery_images' in request.files:
            files = request.files.getlist('gallery_images')
            for f in files:
                if f and f.filename:
                    uploaded_gal = upload_image(f)
                    if uploaded_gal:
                        gallery_entry = ProductImage(ProductId=product_item.id, name=uploaded_gal)
                        db.session.add(gallery_entry)

        db.session.commit()
        flash(f"Product '{product_item.name}' updated successfully!", "success")
        return redirect(url_for('admin.admin_products'))

    return render_template('admin/product/edit.html', active_tab='products', product=product_item, categories=categories_list)


@admin_bp.route('/products/delete/<int:product_id>', methods=['POST'])
@login_required
@admin_only
def admin_products_delete(product_id):
    product_item = Product.query.get_or_404(product_id)
    prod_name = product_item.name
    db.session.delete(product_item)
    db.session.commit()
    flash(f"Product '{prod_name}' deleted.", "info")
    return redirect(url_for('admin.admin_products'))


@admin_bp.route('/products/image/delete/<int:image_id>', methods=['POST'])
@login_required
@admin_only
def admin_product_image_delete(image_id):
    img_item = ProductImage.query.get_or_404(image_id)
    prod_id = img_item.ProductId
    db.session.delete(img_item)
    db.session.commit()
    flash("Gallery image deleted.", "info")
    return redirect(url_for('admin.admin_products_edit', product_id=prod_id))


@admin_bp.route('/orders')
@login_required
def admin_orders():
    orders_list = Order.query.order_by(Order.id.desc()).all()
    return render_template('admin/order/index.html', active_tab='orders', orders=orders_list)


@admin_bp.route('/orders/status/<int:order_id>', methods=['POST'])
@login_required
@admin_only
def admin_orders_status(order_id):
    order_obj = Order.query.get_or_404(order_id)
    new_status = request.form.get('status', 'Pending')
    if new_status in ['Pending', 'Processing', 'Delivered', 'Cancelled']:
        order_obj.status = new_status
        db.session.commit()
        flash(f"Order #{order_obj.id} status updated to '{new_status}'.", "success")
    return redirect(url_for('admin.admin_orders'))


@admin_bp.route('/orders/delete/<int:order_id>', methods=['POST'])
@login_required
@admin_only
def admin_orders_delete(order_id):
    order_obj = Order.query.get_or_404(order_id)
    order_num = order_obj.id
    db.session.delete(order_obj)
    db.session.commit()
    flash(f"Order #{order_num} has been deleted.", "info")
    return redirect(url_for('admin.admin_orders'))


@admin_bp.route('/users')
@login_required
@admin_only
def admin_users():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    role = request.args.get('role', 'ALL').strip()

    query = User.query
    if search:
        query = query.filter(
            db.or_(
                User.fullname.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%')
            )
        )
    if role and role.upper() != 'ALL':
        query = query.filter(User.role.ilike(role))

    pagination = query.order_by(User.id.asc()).paginate(page=page, per_page=10, error_out=False)
    users_list = pagination.items

    return render_template(
        'admin/user/index.html',
        active_tab='users',
        users=users_list,
        pagination=pagination,
        search=search,
        role=role
    )


@admin_bp.route('/users/create', methods=['GET', 'POST'])
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
        return redirect(url_for('admin.admin_users'))
    return render_template('admin/user/create.html', active_tab='users')


@admin_bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
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

        return redirect(url_for('admin.admin_users'))
        
    return render_template('admin/user/edit.html', active_tab='users', user=target_user)


@admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_only
def admin_users_delete(user_id):
    target_user = User.query.get(user_id)
    if target_user:
        db.session.delete(target_user)
        db.session.commit()
    return redirect(url_for('admin.admin_users'))


@admin_bp.route('/settings')
@login_required
def admin_settings():
    return render_template('admin/settings/index.html', active_tab='settings')


# Endpoint aliases for flexibility
admin_bp.add_url_rule('/dashboard', endpoint='dashboard', view_func=admin_dashboard)
admin_bp.add_url_rule('/login', endpoint='login', view_func=admin_login, methods=['GET', 'POST'])
admin_bp.add_url_rule('/logout', endpoint='logout', view_func=admin_logout)
admin_bp.add_url_rule('/categories', endpoint='categories', view_func=admin_categories)
admin_bp.add_url_rule('/products', endpoint='products', view_func=admin_products)
admin_bp.add_url_rule('/orders', endpoint='orders', view_func=admin_orders)
admin_bp.add_url_rule('/users', endpoint='users', view_func=admin_users)
admin_bp.add_url_rule('/settings', endpoint='settings', view_func=admin_settings)
