from celery import Celery
import json
from redis import Redis, ConnectionError
from redis.retry import Retry
from redis.backoff import ExponentialBackoff
import os
import asyncio
import websockets  # Using async websockets library only
from dotenv import load_dotenv
load_dotenv()

app = Celery('tasks', broker=os.getenv('REDIS_URL', 'redis://redis:6379/0'))
redis_client = Redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379/0'))

# app = Celery(
#     "tasks",
#     broker=REDIS_URL,
#     backend=REDIS_URL,
#     broker_transport_options={
#         'visibility_timeout': 3600,
#         'socket_keepalive': True
#     }
# )
# # Configure resilient Redis connection
# redis_client = Redis.from_url(
#     REDIS_URL,
#     decode_responses=True,
#     socket_keepalive=True,
#     retry_on_timeout=True,
#     retry=Retry(ExponentialBackoff(), 3)  # Retry 3 times with exponential backoff
# )

def hex_to_ascii(hex_string):
    try:
        return bytes.fromhex(hex_string).decode('utf-8')
    except:
        return hex_string

def process_message(message):
    """Process and validate incoming message"""
    try:
        if isinstance(message, str):
            data = json.loads(message)
            if 'data' in data:
                processed = hex_to_ascii(data['data'])
            else:
                processed = message
        else:
            processed = message.decode('utf-8')
        
        if ',' in processed:
            parts = [p.strip() for p in processed.split(',')]
            if len(parts) >= 3:
                return {
                    "latitude": float(parts[0]),
                    "longitude": float(parts[1]),
                    "timestamp": parts[2]
                }
        return None
    except Exception as e:
        print(f"Message processing error: {e}")
        return None

async def websocket_listener():
    """Standalone async websocket handler"""
    uri = "wss://iotnet.teracom.dk/app?token=vnoWVQAAABFpb3RuZXQudGVyYWNvbS5ka3_idG-uatIwbfwpA-5IsDE="
    async with websockets.connect(uri) as websocket:
        await websocket.send(json.dumps({
            "command": "subscribe",
            "channels": ["gps_data"]
        }))
        
        while True:
            data = await websocket.recv()
            entry = process_message(data)  # Your existing message processor
            if entry:
                with redis_client.pipeline() as pipe:
                    pipe.set("latest_entry", json.dumps(entry))
                    pipe.lpush("history", json.dumps(entry))
                    pipe.ltrim("history", 0, 1000)
                    pipe.execute()

@app.task(bind=True, max_retries=3)
def start_websocket_task(self):
    """Synchronous Celery task wrapper"""
    try:
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run the async function to completion
        loop.run_until_complete(websocket_listener())
        
    except Exception as e:
        print(f"WebSocket task failed: {str(e)}")
        self.retry(exc=e, countdown=5)
    finally:
        if 'loop' in locals():
            loop.close()