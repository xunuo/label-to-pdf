# main.py (修复版)
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from redis import Redis
import json
import os
import websocket
from tasks import start_websocket_task
from dotenv import load_dotenv
load_dotenv()

app = FastAPI()
# In main.py, update Redis connection:
redis_client = Redis.from_url(
    os.getenv("REDIS_URL", "redis://redis:6379/0"),  # Note 'redis' hostname
    decode_responses=True,
    socket_connect_timeout=5,
    retry_on_timeout=True
)

@app.on_event("startup")
async def startup_event():
    # 初始化默认数据
    if not redis_client.exists("latest_entry") and not redis_client.exists("history"):
        default_data = {
            "latitude": 55.752488,
            "longitude": 12.524214,
            "timestamp": "System Start"
        }
        redis_client.set("latest_entry", json.dumps(default_data))
        redis_client.lpush("history", json.dumps(default_data))
    
    # 启动WebSocket任务
    start_websocket_task.delay()

@app.get("/")
async def index():
    return {"status": "running", "service": "Smart Bike Tracker"}

@app.get("/lastdata")
async def get_last_data():
    # return {"message": "Test data"}
    try:
        latest_entry = redis_client.get("latest_entry")
        history = redis_client.lrange("history", 0, 19) or []
        
        # Combine latest entry with history
        all_data = []
        if latest_entry:
            all_data.append(json.loads(latest_entry))
        all_data.extend([json.loads(h) for h in history])
        
        return JSONResponse(all_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/map", response_class=HTMLResponse)
async def map_view():
    try:
        entry = redis_client.get("latest_entry")
        if not entry:
            return HTMLResponse("<h1>No data available</h1>", status_code=404)
        
        latest = json.loads(entry)
        history = redis_client.lrange("history", 0, 19) or []
        
        markers = "\n".join([
            f"""L.marker([{json.loads(h)['latitude']}, {json.loads(h)['longitude']}])
            .bindPopup("Time: {json.loads(h)['timestamp']}<br>Lat: {json.loads(h)['latitude']}<br>Lon: {json.loads(h)['longitude']}")
            .addTo(map);"""
            for h in history
        ])
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Bike Tracker Map</title>
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
            <style>
                #map {{ height: 80vh; width: 100%; }}
            </style>
        </head>
        <body>
            <h1>Latest Position</h1>
            <div id="map"></div>
            <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
            <script>
                var map = L.map('map').setView([{latest['latitude']}, {latest['longitude']}], 15);
                L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                }}).addTo(map);
                {markers}
                L.circle([{latest['latitude']}, {latest['longitude']}], {{
                    color: 'red',
                    fillColor: '#f03',
                    fillOpacity: 0.5,
                    radius: 50
                }}).addTo(map);
            </script>
        </body>
        </html>
        """
        return HTMLResponse(html)
    except Exception as e:
        return HTMLResponse(f"<h1>Error: {str(e)}</h1>", status_code=500)