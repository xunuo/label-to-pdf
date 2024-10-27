from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('postgresql://postgres:AmXtGqYBLoaySfqtBhGRzTkaiSojGJds@postgres.railway.internal:5432/railway')
db = SQLAlchemy(app)

class Flight(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_city = db.Column(db.String(100), nullable=False)
    to_city = db.Column(db.String(100), nullable=False)
    departure_time = db.Column(db.DateTime, nullable=False)
    price = db.Column(db.Float, nullable=False)
    available_seats = db.Column(db.Integer, nullable=False)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    flight_id = db.Column(db.Integer, db.ForeignKey('flight.id'), nullable=False)
    passenger_name = db.Column(db.String(100), nullable=False)
    booking_status = db.Column(db.String(20), nullable=False)
    payment_status = db.Column(db.String(20), nullable=False)

@app.route('/flights/search', methods=['GET'])
def search_flights():
    from_city = request.args.get('from')
    to_city = request.args.get('to')
    date = request.args.get('date')
    
    query = Flight.query.filter_by(
        from_city=from_city,
        to_city=to_city,
    )
    
    if date:
        date = datetime.fromisoformat(date)
        query = query.filter(
            Flight.departure_time >= date,
            Flight.departure_time < date.replace(hour=23, minute=59)
        )
    
    flights = query.all()
    return jsonify([{
        'id': f.id,
        'from': f.from_city,
        'to': f.to_city,
        'departure': f.departure_time.isoformat(),
        'price': f.price,
        'available_seats': f.available_seats
    } for f in flights])

@app.route('/bookings', methods=['POST'])
def create_booking():
    data = request.json
    flight_id = data.get('flight_id')
    passenger_name = data.get('passenger_name')
    
    flight = Flight.query.get(flight_id)
    if not flight or flight.available_seats < 1:
        return jsonify({'error': 'No available seats'}), 400
        
    booking = Booking(
        flight_id=flight_id,
        passenger_name=passenger_name,
        booking_status='pending',
        payment_status='pending'
    )
    
    db.session.add(booking)
    flight.available_seats -= 1
    db.session.commit()
    
    return jsonify({'booking_id': booking.id})

if __name__ == '__main__':
    app.run(debug=True)
