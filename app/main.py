"""Flask entry point for the Order Service.

Run with:

    python -m app.main
"""
import os

from flask import Flask, jsonify, request

from . import config, db, services


def create_app() -> Flask:
    """Application factory."""
    app = Flask(__name__)
    app.config.update(config.load_config())

    @app.get("/products")
    def list_products():
        category = request.args.get("category")
        products = db.list_products(category=category)
        return jsonify([p.__dict__ for p in products])

    @app.post("/orders")
    def create_order():
        payload = request.get_json(force=True)
        cart = []
        for line in payload.get("items", []):
            product = db.find_product_by_sku(line["sku"])
            if product is None:
                return jsonify({"error": f"unknown sku: {line['sku']}"}), 404
            cart.append((product, int(line["quantity"])))
        order = services.build_order(order_id=1, user_id=payload["user_id"], cart=cart)
        if payload.get("coupon"):
            services.apply_coupon(order, payload["coupon"])
        return jsonify({
            "id": order.id,
            "subtotal_cents": order.subtotal_cents,
            "discount_cents": order.discount_cents,
            "total_cents": order.total_cents,
            "status": order.status.value,
        })

    return app


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    create_app().run(host="0.0.0.0", port=8080, debug=debug)
