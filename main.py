from flask import Flask, request, jsonify
import os
import subprocess

app = Flask(__name__)

# Global variable to store the streaming process
streaming_process = None

@app.route('/start-streaming', methods=['POST'])
def start_streaming():
    global streaming_process
    data = request.json
    video_url = data.get("video_url")
    rtmp_server_url = data.get("rtmp_server_url")

    if not video_url or not rtmp_server_url:
        return jsonify({"error": "Missing video_url or rtmp_server_url"}), 400

    command = f"yt-dlp -o - \"{video_url}\" | ffmpeg -re -i - -c:v copy -f flv \"{rtmp_server_url}\""
    print(f"Executing command: {command}")

    try:
        # Start the streaming process
        streaming_process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return jsonify({"message": "Streaming started successfully!"})

    except Exception as e:
        return jsonify({"error": f"Error occurred during streaming: {str(e)}"}), 500

@app.route('/stop-streaming', methods=['POST'])
def stop_streaming():
    global streaming_process

    if streaming_process is None:
        return jsonify({"error": "No active streaming process found"}), 400

    try:
        # Attempt to terminate or kill the process
        streaming_process.terminate()  # Try gracefully terminating
        streaming_process.wait()  # Wait for process to terminate

        if streaming_process.returncode != 0:
            # If the process hasn't ended successfully, force kill it
            print(f"Process didn't terminate gracefully, killing it.")
            streaming_process.kill()

        # Reset the streaming process reference
        streaming_process = None
        return jsonify({"message": "Streaming stopped successfully!"})

    except Exception as e:
        return jsonify({"error": f"Error occurred while stopping the stream: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)
