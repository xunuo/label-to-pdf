from flask import Flask, jsonify
import os
import threading
import json
import websocket
import json

app = Flask(__name__)

# Global variable to hold the latest parsed data
latest_data = [{
    "latitude": "55.752488",
    "longitude": "12.524214",
    "timestamp": "Cold Start"
}]

# --- WebSocket Functions ---
def on_open(ws):
    print("WebSocket connection established.")
    subscription_message = json.dumps({
        "command": "subscribe",
        "channels": ["your_channel_id"]  # Replace with your actual channel
    })
    ws.send(subscription_message)

# def on_message(ws, message):
#     global latest_data
#     try:
#         data = json.loads(message)
#         if 'data' in data:
#             ascii_data = hex_to_ascii(data['data'])
#             print("Decoded ASCII data:", ascii_data)

#             parts = [part.strip() for part in ascii_data.split(',')]
#             if len(parts) == 3:
#                 latest_data = {
#                     "latitude": parts[0],
#                     "longitude": parts[1],
#                     "timestamp": parts[2]
#                 }
#                 print(f"Updated latest data: {latest_data}")
#             else:
#                 print("Unexpected ASCII format.")
#     except Exception as e:
#         print(f"Error processing message: {e}")

DATA_FILE = "latest_data.json"

# Function to load data from the JSON file
def load_data():
    global latest_data
    try:
        with open(DATA_FILE, "r") as file:
            latest_data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        # If the file doesn't exist or is invalid, use the default data
        latest_data = [{
            "latitude": "55.752488",
            "longitude": "12.524214",
            "timestamp": "Cold Start"
        }]

# Function to save data to the JSON file
def save_data():
    with open(DATA_FILE, "w") as file:
        json.dump(latest_data, file)

# Update the on_message function to save data
def on_message(ws, message):
    global latest_data
    try:
        data = json.loads(message)
        if 'data' in data:
            ascii_data = hex_to_ascii(data['data'])
            print("Decoded ASCII data:", ascii_data)

            parts = [part.strip() for part in ascii_data.split(',')]
            if len(parts) == 3:
                new_entry = {
                    "latitude": parts[0],
                    "longitude": parts[1],
                    "timestamp": parts[2]
                }

                # Check if the new entry is already in the list
                if not latest_data or latest_data[-1] != new_entry:
                    latest_data.append(new_entry)

                    # Keep only the last 20 entries
                    if len(latest_data) > 20:
                        latest_data.pop(0)

                    # Save the updated data to the file
                    save_data()

                print(f"Updated latest data: {latest_data}")
            else:
                print("Unexpected ASCII format.")
    except Exception as e:
        print(f"Error processing message: {e}")        
        
def on_error(ws, error):
    print(f"WebSocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("WebSocket connection closed.")

def hex_to_ascii(hex_string):
    return ''.join(chr(int(hex_string[i:i+2], 16)) for i in range(0, len(hex_string), 2))

def start_websocket():
    ws_url = "wss://iotnet.teracom.dk/app?token=vnoWVQAAABFpb3RuZXQudGVyYWNvbS5ka3_idG-uatIwbfwpA-5IsDE="
    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

# --- Flask Routes ---
@app.route('/')
def index():
    return jsonify({"Hello": "Welcome to the smart bike light app 🚅"})

# @app.route('/lastdata')
# def get_last_data():
#     if latest_data["latitude"] is None:
#         return jsonify({"message": "No data received yet"}), 503
#     return jsonify(latest_data)

@app.route('/lastdata')
def get_last_data():
    if not latest_data:
        return jsonify({"message": "No data received yet"}), 503

    # Generate an HTML table for the last 20 geolocations
    table_rows = ""
    for location in latest_data:
        if isinstance(location, dict) and "latitude" in location and "longitude" in location:
            table_rows += f"""
            <tr>
                <td>{location["latitude"]}</td>
                <td>{location["longitude"]}</td>
                <td>{location["timestamp"]}</td>
            </tr>
            """

    table_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Last 20 Geolocations</title>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body>
        <h1>Last 20 Geolocations</h1>
        <table border="1" style="width: 100%; text-align: left; border-collapse: collapse;">
            <thead>
                <tr>
                    <th>Latitude</th>
                    <th>Longitude</th>
                    <th>Timestamp</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
        <br>
        <a href="/map">View Map</a>
    </body>
    </html>
    """
    return table_html


@app.route('/map')
def show_map():
    if not latest_data:
        return jsonify({"message": "No data received yet"}), 503

    # Generate JavaScript for markers on the map
    markers_js = ""
    for location in latest_data:
        if isinstance(location, dict) and "latitude" in location and "longitude" in location:
            markers_js += f"""
            L.circleMarker([{location["latitude"]}, {location["longitude"]}], {{
                color: 'red',
                radius: 8
            }}).addTo(map)
            .bindPopup('Latitude: {location["latitude"]}<br>Longitude: {location["longitude"]}<br>Timestamp: {location["timestamp"]}');
            """

    # Ensure the map is centered on the last valid location
    if latest_data and isinstance(latest_data[-1], dict):
        center_lat = latest_data[-1]["latitude"]
        center_lon = latest_data[-1]["longitude"]
    else:
        center_lat, center_lon = 0, 0  # Default center if no valid data

    map_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Geolocation Map</title>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    </head>
    <body>
        <h1>Geolocation Map</h1>
        <div id="map" style="width: 100%; height: 500px;"></div>
        <script>
            var map = L.map('map').setView([{center_lat}, {center_lon}], 13);
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                maxZoom: 19,
                attribution: '© OpenStreetMap'
            }}).addTo(map);
            {markers_js}
        </script>
    </body>
    </html>
    """
    return map_html
# --- Main Entrypoint ---
if __name__ == '__main__':
    # Run WebSocket in a background thread
    ws_thread = threading.Thread(target=start_websocket)
    ws_thread.daemon = True
    ws_thread.start()

    # Start Flask app
    port = int(os.getenv("PORT", 8000))  # Use Render's assigned port or default to 5000
    app.run(debug=True, host="0.0.0.0", port=port)
