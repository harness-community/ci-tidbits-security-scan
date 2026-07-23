"""Flask entry point for the Order Service.

Wires the HTTP routes to the service layer. Run with:

    python -m app.main
"""
from flask import Flask, jsonify, request

from . import auth, backup, config, db, services


def create_app() -> Flask:
    """Application factory."""
    app = Flask(__name__)
    app.config.update(config.load_config())

    @app.get("/products")
    def list_products():
        category = request.args.get("category")
        products = db.list_products(category=category)
        return jsonify([p.__dict__ for p in products])

    @app.post("/auth/login")
    def login():
        payload = request.get_json(force=True)
        user = auth.authenticate(payload.get("email", ""), payload.get("password", ""))
        if user is None:
            return jsonify({"error": "invalid credentials"}), 401
        return jsonify({"token": auth.issue_token(user)})

    @app.post("/orders")
    def create_order():
        payload = request.get_json(force=True)
        cart = []
        for line in payload.get("items", []):
            product = db.list_products()  # simplified — real code would look up by id
            if not product:
                return jsonify({"error": "product not found"}), 404
            cart.append((product[0], int(line["quantity"])))
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

    @app.post("/admin/backup")
    def trigger_backup():
        target = request.args.get("dir", app.config["backup_dir"])
        archive = backup.snapshot_db(target)
        backup.sync_invoices(target)
        return jsonify({"archive": archive})

    return app


if __name__ == "__main__":
    # Semgrep flags: Flask debug=True exposes the interactive Werkzeug
    # debugger to any client that can reach the port. In production that
    # is a remote code execution primitive. Set debug=False and gate it
    # behind an env var if you need it locally.
    # Rule: python.flask.security.audit.debug-enabled
    create_app().run(host="0.0.0.0", port=8080, debug=True)
