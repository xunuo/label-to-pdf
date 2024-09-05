from flask import Flask, render_template, request, jsonify, send_from_directory
import yt_dlp
import os

app = Flask(__name__)

# Set the upload folder path (temporary storage)
DOWNLOAD_FOLDER = os.path.join(os.getcwd(), 'downloads')
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

app.config['DOWNLOAD_FOLDER'] = DOWNLOAD_FOLDER

# Route to serve the HTML file
@app.route('/')
def index():
    return render_template('index.html')

# Function to download audio using yt-dlp
def download_audio(url, output_path):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_path}/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info_dict).replace('.webm', '.mp3')
        return filename

# Route to handle download requests
@app.route('/api/download', methods=['POST'])
def download():
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'success': False, 'error': 'No URL provided'})

    try:
        # Step 1: Download the audio file
        file_path = download_audio(url, app.config['DOWNLOAD_FOLDER'])
        file_name = os.path.basename(file_path)

        # Step 2: Return the file for download (send as response)
        return jsonify({'success': True, 'file': f'/downloads/{file_name}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Route to serve the downloaded file
@app.route('/downloads/<filename>')
def download_file(filename):
    return send_from_directory(app.config['DOWNLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

