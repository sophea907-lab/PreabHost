from datetime import datetime
from extension import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image = db.Column(db.Text, nullable=True)
    fullname = db.Column(db.String(128))
    email = db.Column(db.String(128), nullable=False, unique=True)
    password = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="Customer")
    status = db.Column(db.String(30), nullable=False, default="Active")
    create_at = db.Column(db.DateTime, default=datetime.utcnow)
    update_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw_password):
        self.password = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        if not self.password:
            return False
        try:
            return check_password_hash(self.password, raw_password)
        except Exception:
            return self.password == raw_password

    def to_dict(self):
        return {
            "id": self.id,
            "fullname": self.fullname,
            "email": self.email,
            "role": self.role,
            "status": self.status,
            "image": self.image,
            "create_at": self.create_at.isoformat() if self.create_at else None,
            "update_at": self.update_at.isoformat() if self.update_at else None,
        }


class Category(db.Model):
    __tablename__ = 'category'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    image = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)

    products = db.relationship('Product', backref='category', cascade='all, delete-orphan', lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "image": self.image,
            "description": self.description,
            "products_count": len(self.products) if self.products else 0
        }


class Product(db.Model):
    __tablename__ = 'product'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    thumbnail = db.Column(db.String(255), nullable=True)
    Cost = db.Column(db.Numeric(10, 2), nullable=True, default=0.00)
    Price = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    Stock = db.Column(db.Integer, nullable=False, default=0)
    CategoryId = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    description = db.Column(db.Text, nullable=True)

    images = db.relationship('ProductImage', backref='product', cascade='all, delete-orphan', lazy=True)

    @property
    def cost(self):
        return float(self.Cost) if self.Cost is not None else 0.0

    @cost.setter
    def cost(self, val):
        self.Cost = val

    @property
    def price(self):
        return float(self.Price) if self.Price is not None else 0.0

    @price.setter
    def price(self, val):
        self.Price = val

    @property
    def stock(self):
        return self.Stock or 0

    @stock.setter
    def stock(self, val):
        self.Stock = val

    @property
    def category_id(self):
        return self.CategoryId

    @category_id.setter
    def category_id(self, val):
        self.CategoryId = val

    @property
    def title(self):
        return self.name

    @title.setter
    def title(self, val):
        self.name = val

    @property
    def image(self):
        if self.thumbnail:
            return self.thumbnail
        if self.images and len(self.images) > 0:
            return self.images[0].name
        return "/static/img/placeholder.png"

    @image.setter
    def image(self, val):
        self.thumbnail = val

    @property
    def rating(self):
        return {"rate": 4.8, "count": 120}

    def __getitem__(self, item):
        if item == 'title':
            return self.name
        elif item == 'price':
            return float(self.Price) if self.Price is not None else 0.0
        elif item == 'cost':
            return float(self.Cost) if self.Cost is not None else 0.0
        elif item == 'stock':
            return self.Stock or 0
        elif item == 'image':
            return self.image
        elif item == 'thumbnail':
            return self.thumbnail
        elif item == 'category':
            return self.category.name if self.category else ''
        elif item == 'rating':
            return self.rating
        elif hasattr(self, item):
            return getattr(self, item)
        raise KeyError(item)

    def get(self, item, default=None):
        try:
            return self[item]
        except KeyError:
            return default

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "thumbnail": self.thumbnail,
            "Cost": float(self.Cost) if self.Cost is not None else 0.0,
            "Price": float(self.Price) if self.Price is not None else 0.0,
            "Stock": self.Stock,
            "CategoryId": self.CategoryId,
            "category": self.category.name if self.category else None,
            "description": self.description,
            "images": [img.name for img in self.images] if self.images else []
        }


class ProductImage(db.Model):
    __tablename__ = 'product_image'
    id = db.Column(db.Integer, primary_key=True)
    ProductId = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)

    @property
    def product_id(self):
        return self.ProductId

    @product_id.setter
    def product_id(self, val):
        self.ProductId = val

    def to_dict(self):
        return {
            "id": self.id,
            "ProductId": self.ProductId,
            "name": self.name
        }


class Order(db.Model):
    __tablename__ = 'order'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    customer_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    address = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    zip_code = db.Column(db.String(50), nullable=True)
    subtotal = db.Column(db.Numeric(10, 2), default=0.00)
    shipping = db.Column(db.Numeric(10, 2), default=0.00)
    tax = db.Column(db.Numeric(10, 2), default=0.00)
    total = db.Column(db.Numeric(10, 2), default=0.00)
    status = db.Column(db.String(50), default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('orders', lazy=True), lazy=True)
    items = db.relationship('OrderItem', backref='order', cascade='all, delete-orphan', lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "customer_name": self.customer_name,
            "email": self.email,
            "phone": self.phone,
            "address": self.address,
            "city": self.city,
            "zip_code": self.zip_code,
            "subtotal": float(self.subtotal or 0.0),
            "shipping": float(self.shipping or 0.0),
            "tax": float(self.tax or 0.0),
            "total": float(self.total or 0.0),
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [item.to_dict() for item in self.items]
        }


class OrderItem(db.Model):
    __tablename__ = 'order_item'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    product_name = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Numeric(10, 2), default=0.00)
    quantity = db.Column(db.Integer, default=1)
    thumbnail = db.Column(db.String(255), nullable=True)

    product = db.relationship('Product', backref=db.backref('order_items', lazy=True), lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "price": float(self.price or 0.0),
            "quantity": self.quantity,
            "thumbnail": self.thumbnail,
            "item_total": float(self.price or 0.0) * (self.quantity or 1)
        }

