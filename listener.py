import websocket

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