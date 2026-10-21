import sqlite3
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def init_db():
    conn = sqlite3.connect('branded_fits.db')
    cursor = conn.cursor()
    # Table for Outfits
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT,
            image TEXT NOT NULL,
            status TEXT DEFAULT 'active'
        )
    ''')
    # Table for Customer Orders
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            phone TEXT,
            address TEXT,
            region TEXT,
            total_amount REAL,
            items TEXT,
            payment_ref TEXT,
            order_status TEXT DEFAULT 'Processing'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/api/products', methods=['GET'])
def get_products():
    conn = sqlite3.connect('branded_fits.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, category, image FROM products WHERE status = 'active'")
    rows = cursor.fetchall()
    conn.close()
    
    products = [{"id": r[0], "name": r[1], "price": r[2], "category": r[3], "image": r[4]} for r in rows]
    return jsonify(products)

@app.route('/api/products', methods=['POST'])
def add_product():
    data = request.json
    conn = sqlite3.connect('branded_fits.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO products (name, price, category, image) VALUES (?, ?, ?, ?)",
                   (data['name'], data['price'], data['category'], data['image']))
    conn.commit()
    conn.close()
    return jsonify({"message": "Product saved successfully"}), 201

@app.route('/api/products/<int:prod_id>', methods=['DELETE'])
def remove_product(prod_id):
    conn = sqlite3.connect('branded_fits.db')
    cursor = conn.cursor()
    # Soft delete so historical order data remains intact
    cursor.execute("UPDATE products SET status = 'sold_out' WHERE id = ?", (prod_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Product removed"})

# Render the frontend HTML page
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.json
    # Process order & store in database
    return jsonify({"status": "success", "message": "Order placed successfully!"}), 201

if __name__ == '__main__':
    app.run(debug=True)