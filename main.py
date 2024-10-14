from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector

app = Flask(__name__)
CORS(app)

# Database connection
def get_db_connection():
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="food_ordering"
    )
    return connection

# Fetch menu items
@app.route('/menu', methods=['GET'])
def get_menu():
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM menu")
        menu = cursor.fetchall()
        cursor.close()
        connection.close()
        return jsonify(menu), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Place an order
@app.route('/order', methods=['POST'])
def place_order():
    try:
        data = request.get_json()
        customer_name = data.get('customer_name')
        table_number = data.get('table_number')
        items = data.get('items')  # Expecting a list of menu_ids

        if not customer_name or not table_number or not items:
            return jsonify({"error": "Missing customer_name, table_number, or items"}), 400

        connection = get_db_connection()
        cursor = connection.cursor()

        # Insert each menu_id as a separate order entry
        for menu_id in items:
            cursor.execute("""
                INSERT INTO orders (menu_id, customer_name, table_number, status)
                VALUES (%s, %s, %s, 'pending')
            """, (menu_id, customer_name, table_number))

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({"message": "Order placed successfully!"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Fetch all orders for chef
@app.route('/orders', methods=['GET'])
def get_orders():
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT orders.id, 
                   menu.name AS menu_name, 
                   menu.price, 
                   menu.description, 
                   menu.image_url, 
                   orders.customer_name, 
                   orders.table_number, 
                   orders.status
            FROM orders
            JOIN menu ON orders.menu_id = menu.id
        """)
        orders = cursor.fetchall()
        cursor.close()
        connection.close()

        # Structure the orders to match the Flutter code
        structured_orders = []
        for order in orders:
            structured_orders.append({
                'id': order['id'],
                'customer_name': order['customer_name'],
                'table_number': order['table_number'],
                'status': order['status'],
                'menu_name': order['menu_name'],
                'price': order['price'],
                'description': order['description'],
                'image_url': order['image_url']
            })

        return jsonify(structured_orders), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/sales', methods=['GET'])
def get_total_sales():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            SELECT SUM(menu.price) AS total_sales 
            FROM orders 
            JOIN menu ON orders.menu_id = menu.id 
            WHERE orders.status = 'completed'
        """)
        total_sales = cursor.fetchone()[0] or 0.0  # Return 0 if no completed orders
        cursor.close()
        connection.close()
        
        # Convert total_sales to a float
        return jsonify({"total_sales": float(total_sales)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500




# Update order status
@app.route('/order/status', methods=['PUT'])
def update_order_status():
    try:
        data = request.json
        order_id = data.get('order_id')
        status = data.get('status')

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("UPDATE orders SET status = %s WHERE id = %s", (status, order_id))
        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({"message": "Order status updated successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Add a new menu item
@app.route('/menu', methods=['POST'])
def add_menu_item():
    try:
        data = request.get_json()
        name = data['name']
        price = data['price']
        description = data['description']
        image_url = data['image_url']

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("INSERT INTO menu (name, price, description, image_url) VALUES (%s, %s, %s, %s)",
                       (name, price, description, image_url))
        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({"message": "Menu item added!"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Delete a menu item
@app.route('/menu/<int:menu_id>', methods=['DELETE'])
def delete_menu_item(menu_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("DELETE FROM menu WHERE id = %s", (menu_id,))
        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({"message": "Menu item deleted!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    # Fetch available rooms
@app.route('/rooms', methods=['GET'])
def get_rooms():
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM rooms")
        rooms = cursor.fetchall()
        
        # Update the booking status for each room
        for room in rooms:
            room_id = room['room_id']
            cursor.execute("SELECT COUNT(*) FROM bookings WHERE room_id = %s", (room_id,))
            booked_count = cursor.fetchone()['COUNT(*)']
            room['is_booked'] = booked_count > 0  # Update booking status
            
        cursor.close()
        connection.close()
        return jsonify(rooms), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Book a room
@app.route('/book', methods=['POST'])
def book_room():
    try:
        data = request.json
        room_id = data['room_id']
        booked_by = data['booked_by']
        client_name = data['client_name']
        purpose = data['purpose']

        connection = get_db_connection()
        cursor = connection.cursor()

        # Insert booking into the database
        cursor.execute("""INSERT INTO bookings (room_id, booked_by, client_name, purpose) 
                          VALUES (%s, %s, %s, %s)""", (room_id, booked_by, client_name, purpose))
        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({"message": "Room booked successfully!"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# Send a request message to the person who booked the room
@app.route('/message', methods=['POST'])
def send_message():
    try:
        data = request.json
        booking_id = data['booking_id']
        sender_name = data['sender_name']
        message = data['message']

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO messages (booking_id, sender_name, message) 
            VALUES (%s, %s, %s)
        """, (booking_id, sender_name, message))
        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({"message": "Message sent successfully!"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
