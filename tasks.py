# tasks.py (修复版)
from celery import Celery
import websocket
import json
from redis import Redis
import time

app = Celery("tasks", broker="redis://localhost:6379/0")
redis_client = Redis(host="localhost", port=6379, decode_responses=True)

def hex_to_ascii(hex_string):
    try:
        return bytes.fromhex(hex_string).decode('utf-8')
    except:
        return hex_string  # 如果不是有效的hex，直接返回原数据

def on_message(ws, message):
    print("Raw message received:", message)  # 调试日志
    try:
        # 尝试解析JSON和HEX数据
        if isinstance(message, str):
            data = json.loads(message)
            if 'data' in data:
                processed = hex_to_ascii(data['data'])
            else:
                processed = message
        else:
            processed = message.decode('utf-8')
        
        # 解析坐标数据
        if ',' in processed:
            parts = [p.strip() for p in processed.split(',')]
            if len(parts) >= 3:
                entry = {
                    "latitude": float(parts[0]),
                    "longitude": float(parts[1]),
                    "timestamp": parts[2]
                }
                # 存储到Redis
                redis_client.set("latest_entry", json.dumps(entry))
                redis_client.lpush("history", json.dumps(entry))
                redis_client.ltrim("history", 0, 19)  # 保留最近20条
                print("Stored data:", entry)  # 调试日志
    except Exception as e:
        print("Processing error:", str(e))

def on_error(ws, error):
    print("WebSocket Error:", error)

def on_close(ws, close_status_code, close_msg):
    print("WebSocket Closed. Reconnecting...")
    time.sleep(5)
    start_websocket_task.delay()  # 自动重连

def on_open(ws):
    print("WebSocket Connected")
    subscribe_msg = {
        "command": "subscribe",
        "channels": ["gps_data"]  # 替换为实际频道
    }
    ws.send(json.dumps(subscribe_msg))

@app.task(bind=True, max_retries=3)
def start_websocket_task(self):
    ws_url = "wss://iotnet.teracom.dk/app?token=vnoWVQAAABFpb3RuZXQudGVyYWNvbS5ka3_idG-uatIwbfwpA-5IsDE="
    print(f"Connecting to {ws_url}")
    try:
        ws = websocket.WebSocketApp(
            ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        ws.run_forever()
    except Exception as exc:
        print(f"Connection failed: {exc}")
        self.retry(countdown=5)