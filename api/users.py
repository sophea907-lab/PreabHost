from flask import request, jsonify
from werkzeug.security import generate_password_hash
from datetime import datetime
from extension import db
from models import User
from helper import upload_image
from . import api_bp


@api_bp.route('/users', methods=['GET'])
def get_users():
    """Retrieve a list of users, with optional filtering."""
    query = User.query
    search = request.args.get('search')
    role = request.args.get('role')
    status = request.args.get('status')

    if search:
        search_filter = f"%{search.strip()}%"
        query = query.filter((User.fullname.ilike(search_filter)) | (User.email.ilike(search_filter)))

    if role and role.upper() != 'ALL':
        query = query.filter(User.role.ilike(role.strip()))

    if status and status.upper() != 'ALL':
        query = query.filter(User.status.ilike(status.strip()))

    users_list = query.order_by(User.id.asc()).all()
    return jsonify([user.to_dict() for user in users_list]), 200


@api_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Retrieve a single user by ID."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user.to_dict()), 200


@api_bp.route('/users', methods=['POST'])
def create_user():
    """Create a new user (accepts JSON or Multipart Form)."""
    if request.is_json:
        data = request.get_json() or {}
        fullname = data.get('fullname') or data.get('username')
        email = data.get('email')
        password = data.get('password')
        role = data.get('role', 'Customer')
        status = data.get('status', 'Active')
        image_path = data.get('image')
    else:
        fullname = request.form.get('fullname') or request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'Customer')
        status = request.form.get('status', 'Active')
        image_path = None
        if 'image' in request.files and request.files['image'].filename:
            image_path = upload_image(request.files['image'])

    if not email:
        return jsonify({"error": "Email is required"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "A user with this email already exists"}), 409

    new_user = User(
        fullname=fullname or email.split('@')[0],
        email=email,
        password=generate_password_hash(password) if password else '',
        role=role or 'Customer',
        status=status or 'Active',
        image=image_path
    )

    db.session.add(new_user)
    db.session.commit()

    return jsonify(new_user.to_dict()), 201


@api_bp.route('/users/<int:user_id>', methods=['PUT', 'PATCH'])
def update_user(user_id):
    """Update an existing user (accepts JSON or Multipart Form)."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if request.is_json:
        data = request.get_json() or {}
        if 'fullname' in data:
            user.fullname = data['fullname']
        elif 'username' in data:
            user.fullname = data['username']
        if 'email' in data:
            # Check unique email if changing
            if data['email'] != user.email and User.query.filter_by(email=data['email']).first():
                return jsonify({"error": "Email is already taken"}), 409
            user.email = data['email']
        if 'password' in data and data['password']:
            user.password = generate_password_hash(data['password'])
        if 'role' in data:
            user.role = data['role']
        if 'status' in data:
            user.status = data['status']
        if 'image' in data:
            user.image = data['image']
    else:
        fullname = request.form.get('fullname') or request.form.get('username')
        if fullname:
            user.fullname = fullname
        email = request.form.get('email')
        if email:
            if email != user.email and User.query.filter_by(email=email).first():
                return jsonify({"error": "Email is already taken"}), 409
            user.email = email
        password = request.form.get('password')
        if password:
            user.password = generate_password_hash(password)
        if 'role' in request.form:
            user.role = request.form.get('role')
        if 'status' in request.form:
            user.status = request.form.get('status')
        if 'image' in request.files and request.files['image'].filename:
            uploaded = upload_image(request.files['image'])
            if uploaded:
                user.image = uploaded

    user.update_at = datetime.utcnow()
    db.session.commit()

    return jsonify(user.to_dict()), 200


@api_bp.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Delete a user by ID."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    db.session.delete(user)
    db.session.commit()

    return jsonify({"message": f"User #{user_id} deleted successfully", "id": user_id}), 200
