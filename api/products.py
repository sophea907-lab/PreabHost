from flask import request, jsonify
from extension import db
from models import Product, Category, ProductImage
from . import api_bp


@api_bp.route('/products/top', methods=['GET'])
def get_top_product():
    """
    Retrieve the top 1 featured product.
    Prioritizes newest product, or highest stock/rating.
    """
    top_product = Product.query.order_by(Product.id.desc()).first()
    if not top_product:
        return jsonify({
            "success": False,
            "product": None,
            "message": "No products currently available."
        }), 200

    data = top_product.to_dict()
    # Add extra storefront helpers
    data["title"] = top_product.name
    data["image"] = top_product.thumbnail or (top_product.images[0].name if top_product.images else "/static/img/placeholder.png")
    data["category"] = top_product.category.name if top_product.category else "Exclusive"
    data["price"] = float(top_product.Price or 0.0)

    return jsonify({
        "success": True,
        "product": data
    }), 200


@api_bp.route('/products', methods=['GET'])
def get_products():
    """Retrieve all products with optional limit and category filters."""
    query = Product.query
    limit = request.args.get('limit', type=int)
    cat = request.args.get('category')

    if cat:
        query = query.join(Category).filter(Category.name.ilike(cat.strip()))

    query = query.order_by(Product.id.desc())

    if limit and limit > 0:
        products_list = query.limit(limit).all()
    else:
        products_list = query.all()

    results = []
    for p in products_list:
        p_dict = p.to_dict()
        p_dict["title"] = p.name
        p_dict["image"] = p.thumbnail or (p.images[0].name if p.images else "/static/img/placeholder.png")
        p_dict["category"] = p.category.name if p.category else "Uncategorized"
        results.append(p_dict)

    return jsonify({
        "success": True,
        "count": len(results),
        "products": results
    }), 200


@api_bp.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """Retrieve a single product by ID."""
    product = Product.query.get(product_id)
    if not product:
        return jsonify({
            "success": False,
            "error": "Product not found"
        }), 404

    p_dict = product.to_dict()
    p_dict["title"] = product.name
    p_dict["image"] = product.thumbnail or (product.images[0].name if product.images else "/static/img/placeholder.png")
    p_dict["category"] = product.category.name if product.category else "Uncategorized"

    return jsonify({
        "success": True,
        "product": p_dict
    }), 200
