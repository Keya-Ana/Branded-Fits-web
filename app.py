import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
DATABASE_PATH = Path(__file__).with_name("branded_fits.db")
DELIVERY_FEE = Decimal("20.00")
PAYSTACK_API_URL = "https://api.paystack.co"
DEMO_PRODUCTS = {
    "p1": ("Elegant Midi Dress", Decimal("180.00")),
    "p2": ("Casual Co-ord Set", Decimal("160.00")),
    "p3": ("White Top & Pants", Decimal("190.00")),
    "p4": ("Bodycon Dress", Decimal("170.00")),
    "p5": ("Classic Blazer Set", Decimal("250.00")),
    "p6": ("Sleek Jumpsuit", Decimal("200.00")),
}


@contextmanager
def get_db_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    with get_db_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                category TEXT,
                image TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT DEFAULT 'active'
            )
        """)
        product_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(products)")
        }
        if "description" not in product_columns:
            connection.execute(
                "ALTER TABLE products ADD COLUMN description TEXT NOT NULL DEFAULT ''"
            )
        connection.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT,
                phone TEXT,
                address TEXT,
                region TEXT,
                total_amount REAL,
                items TEXT,
                payment_ref TEXT,
                order_status TEXT DEFAULT 'Pending Payment',
                email TEXT,
                city TEXT,
                payment_status TEXT DEFAULT 'Pending'
            )
        """)
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(orders)")
        }
        for column, declaration in (
            ("email", "TEXT"),
            ("city", "TEXT"),
            ("payment_status", "TEXT DEFAULT 'Pending'"),
        ):
            if column not in columns:
                connection.execute(f"ALTER TABLE orders ADD COLUMN {column} {declaration}")


init_db()


def paystack_request(path, method="GET", payload=None):
    secret_key = os.environ.get("PAYSTACK_SECRET_KEY")
    if not secret_key:
        return None, (jsonify({"error": "Online payments are not configured."}), 503)

    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    api_request = Request(
        f"{PAYSTACK_API_URL}{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {secret_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "BrandedFits/1.0 (Paystack payment verification)",
        },
    )
    try:
        with urlopen(api_request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        response_body = error.read().decode("utf-8", errors="replace")
        try:
            details = json.loads(response_body)
            message = details.get("message") if isinstance(details, dict) else None
            if not message and isinstance(details, dict):
                error_details = details.get("error")
                if isinstance(error_details, dict):
                    message = error_details.get("message")
        except (json.JSONDecodeError, UnicodeDecodeError):
            details = None
            message = None
        message = message or "Paystack could not process the payment."
        safe_body = re.sub(
            r"(?i)(sk_(?:test|live)_|bearer\s+)[A-Za-z0-9._-]+",
            r"\1[REDACTED]",
            response_body[:1000],
        )
        safe_body = re.sub(
            r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
            "[EMAIL]",
            safe_body,
            flags=re.IGNORECASE,
        )
        app.logger.warning(
            "Paystack returned HTTP %s: %s (content-type: %s, response: %s)",
            error.code,
            message,
            error.headers.get("Content-Type", "unknown"),
            safe_body or "[empty response]",
        )
        return None, (jsonify({"error": message}), 502)
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        app.logger.error("Paystack request failed: %s", error)
        return None, (jsonify({"error": "Unable to reach Paystack. Please try again."}), 502)

    if not result.get("status"):
        message = result.get("message") or "Paystack could not process the payment."
        app.logger.warning("Paystack rejected the request: %s", message)
        return None, (
            jsonify({"error": message}),
            502,
        )
    return result.get("data"), None


@app.route("/")
def home():
    return render_template(
        "index.html",
        paystack_public_key=os.environ.get("PAYSTACK_PUBLIC_KEY", ""),
    )


@app.route("/about")
def about():
    return render_template(
        "index.html",
        paystack_public_key=os.environ.get("PAYSTACK_PUBLIC_KEY", ""),
        initial_view="about",
    )


@app.route("/contact")
def contact():
    return render_template(
        "index.html",
        paystack_public_key=os.environ.get("PAYSTACK_PUBLIC_KEY", ""),
        initial_view="contact",
    )


@app.route("/api/products", methods=["GET"])
def get_products():
    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, name, price, category, image, description
            FROM products
            WHERE status = 'active'
            ORDER BY id DESC
            """
        ).fetchall()
    return jsonify([
        {
            "id": row["id"],
            "name": row["name"],
            "price": row["price"],
            "category": row["category"],
            "image": row["image"],
            "description": row["description"],
        }
        for row in rows
    ])


@app.route("/api/admin/dashboard", methods=["GET"])
def get_admin_dashboard():
    with get_db_connection() as connection:
        order_rows = connection.execute(
            """
            SELECT id, customer_name, total_amount, order_status, payment_status
            FROM orders
            ORDER BY id DESC
            """
        ).fetchall()
        product_count = connection.execute(
            "SELECT COUNT(*) FROM products WHERE status = 'active'"
        ).fetchone()[0]
        revenue = connection.execute(
            """
            SELECT COALESCE(SUM(total_amount), 0)
            FROM orders
            WHERE payment_status = 'Paid'
            """
        ).fetchone()[0]

    orders = [
        {
            "id": row["id"],
            "customer": row["customer_name"] or "Customer",
            "amount": row["total_amount"] or 0,
            "status": row["order_status"],
            "paymentStatus": row["payment_status"],
        }
        for row in order_rows
    ]
    return jsonify({
        "stats": {
            "totalOrders": len(orders),
            "revenue": revenue,
            "pendingOrders": sum(
                order["status"] not in ("Delivered", "Cancelled")
                for order in orders
            ),
            "activeProducts": product_count,
        },
        "orders": orders,
    })


@app.route("/api/orders/<int:order_id>/status", methods=["POST"])
def update_order_status(order_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Order status must be submitted as JSON."}), 400

    status = data.get("status")
    allowed_statuses = {"Processing", "Shipped", "Delivered", "Cancelled"}
    if status not in allowed_statuses:
        return jsonify({"error": "Choose a valid order status."}), 400

    with get_db_connection() as connection:
        order = connection.execute(
            "SELECT payment_status FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        if order is None:
            return jsonify({"error": "Order not found."}), 404
        if order["payment_status"] != "Paid" and status in {"Processing", "Shipped", "Delivered"}:
            return jsonify({"error": "An unpaid order cannot be processed for delivery."}), 409
        connection.execute(
            "UPDATE orders SET order_status = ? WHERE id = ?",
            (status, order_id),
        )
    return jsonify({"id": order_id, "status": status})


@app.route("/api/products", methods=["POST"])
def add_product():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Product details must be submitted as JSON."}), 400
    required_fields = ("name", "price", "category", "image")
    if any(not data.get(field) for field in required_fields):
        return jsonify({"error": "Name, price, category and image are required."}), 400
    if not all(isinstance(data[field], str) for field in ("name", "category", "image")):
        return jsonify({"error": "Product name, category and image must be text."}), 400
    description = data.get("description", "")
    if not isinstance(description, str):
        return jsonify({"error": "Product description must be text."}), 400

    try:
        price = Decimal(str(data["price"]))
        if not price.is_finite() or price <= 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        return jsonify({"error": "Product price must be a positive amount."}), 400

    with get_db_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO products (name, price, category, image, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                data["name"].strip(),
                str(price),
                data["category"].strip(),
                data["image"].strip(),
                description.strip(),
            ),
        )
        product_id = cursor.lastrowid
    return jsonify({
        "id": product_id,
        "name": data["name"].strip(),
        "price": float(price),
        "category": data["category"].strip(),
        "image": data["image"].strip(),
        "description": description.strip(),
        "message": "Product saved successfully",
    }), 201


@app.route("/api/products/<int:prod_id>", methods=["DELETE"])
def remove_product(prod_id):
    with get_db_connection() as connection:
        connection.execute(
            "UPDATE products SET status = 'sold_out' WHERE id = ?", (prod_id,)
        )
    return jsonify({"message": "Product removed"})


@app.route("/api/payments/initialize", methods=["POST"])
def initialize_payment():
    public_key = os.environ.get("PAYSTACK_PUBLIC_KEY", "")
    secret_key = os.environ.get("PAYSTACK_SECRET_KEY", "")
    if not public_key.startswith(("pk_test_", "pk_live_")) or not secret_key.startswith(("sk_test_", "sk_live_")):
        return jsonify({"error": "Paystack public and secret keys must be configured on the server."}), 503
    if public_key[3:7] != secret_key[3:7]:
        return jsonify({"error": "Paystack public and secret keys must both be test keys or both be live keys."}), 503

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Checkout details must be submitted as JSON."}), 400
    customer = data.get("customer") or {}
    if not isinstance(customer, dict):
        return jsonify({"error": "Please provide valid customer details."}), 400
    required_fields = ("name", "email", "phone", "address", "city", "region")
    if any(not isinstance(customer.get(field), str) or not customer[field].strip()
           for field in required_fields):
        return jsonify({"error": "Please provide all required delivery and contact details."}), 400

    items = data.get("items")
    if not isinstance(items, list) or not items:
        return jsonify({"error": "Your cart is empty."}), 400

    catalog = {
        product_id: {"name": name, "price": price}
        for product_id, (name, price) in DEMO_PRODUCTS.items()
    }
    with get_db_connection() as connection:
        database_products = connection.execute(
            "SELECT id, name, price FROM products WHERE status = 'active'"
        ).fetchall()
    catalog.update({
        str(product["id"]): {
            "name": product["name"],
            "price": Decimal(str(product["price"])),
        }
        for product in database_products
    })

    normalized_items = []
    subtotal = Decimal("0.00")
    try:
        for item in items:
            quantity = item.get("quantity")
            if isinstance(quantity, bool) or not isinstance(quantity, int) or not 1 <= quantity <= 100:
                raise ValueError
            product_id = str(item.get("productId", ""))
            product = catalog.get(product_id)
            if product is None:
                raise ValueError
            price = product["price"]
            line_total = (price * quantity).quantize(Decimal("0.01"))
            subtotal += line_total
            normalized_items.append({
                "productId": product_id,
                "name": product["name"],
                "size": str(item.get("size", ""))[:20],
                "quantity": quantity,
                "unitPrice": str(price.quantize(Decimal("0.01"))),
            })
    except (AttributeError, InvalidOperation, TypeError, ValueError):
        return jsonify({"error": "Your cart contains an invalid item."}), 400

    total = (subtotal + DELIVERY_FEE).quantize(Decimal("0.01"))
    amount_in_pesewas = int(total * 100)
    reference = f"BF_{secrets.token_hex(16)}"
    with get_db_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO orders (
                customer_name, phone, address, region, city, email, total_amount,
                items, payment_ref, order_status, payment_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending Payment', 'Pending')
            """,
            (
                customer["name"].strip(),
                customer["phone"].strip(),
                customer["address"].strip(),
                customer["region"].strip(),
                customer["city"].strip(),
                customer["email"].strip(),
                str(total),
                json.dumps(normalized_items),
                reference,
            ),
        )

    return jsonify({
        "reference": reference,
        "amount": amount_in_pesewas,
        "email": customer["email"].strip(),
        "metadata": {
            "customer_name": customer["name"].strip(),
            "phone": customer["phone"].strip(),
        },
        "orderId": f"#BF{cursor.lastrowid:06d}",
    })


@app.route("/api/payments/verify", methods=["POST"])
def verify_payment():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Payment reference must be submitted as JSON."}), 400
    reference = data.get("reference")
    if not isinstance(reference, str) or not reference.strip():
        return jsonify({"error": "A payment reference is required."}), 400
    reference = reference.strip()

    with get_db_connection() as connection:
        order = connection.execute(
            "SELECT * FROM orders WHERE payment_ref = ?", (reference,)
        ).fetchone()
    if order is None:
        return jsonify({"error": "No order was found for this payment reference."}), 404
    if order["payment_status"] == "Paid":
        return jsonify({
            "status": "success",
            "orderId": f"#BF{order['id']:06d}",
            "amount": f"{order['total_amount']:.2f}",
            "customer": order["customer_name"],
            "delivery": f"{order['address']}, {order['city']}, {order['region']}",
            "paymentMethod": "Paystack",
        })

    transaction, error_response = paystack_request(
        f"/transaction/verify/{reference}"
    )
    if error_response:
        return error_response

    expected_amount = int(Decimal(str(order["total_amount"])) * 100)
    if (
        transaction.get("status") != "success"
        or transaction.get("reference") != reference
        or transaction.get("currency") != "GHS"
        or transaction.get("amount") != expected_amount
    ):
        return jsonify({"error": "Payment has not been completed or the amount does not match."}), 402

    with get_db_connection() as connection:
        connection.execute(
            """
            UPDATE orders
            SET payment_status = 'Paid', order_status = 'Processing'
            WHERE payment_ref = ?
            """,
            (reference,),
        )

    return jsonify({
        "status": "success",
        "orderId": f"#BF{order['id']:06d}",
        "amount": f"{order['total_amount']:.2f}",
        "customer": order["customer_name"],
        "delivery": f"{order['address']}, {order['city']}, {order['region']}",
        "paymentMethod": "Paystack",
    })


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
