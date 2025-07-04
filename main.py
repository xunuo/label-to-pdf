from flask import Flask, send_file, jsonify, request
import os
import requests
from io import BytesIO
from PIL import Image

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})

@app.route('/download_pdf')
def download_pdf():
    # 1. 从 query 参数或默认值拿到要拉取的图片 URL
    image_url = request.args.get(
        'url',
        'https://itag.app/data/upload/1/e5660918-15723dp-images-1.jpg'
    )
    # 2. 从环境变量读取 Label Studio API Key
    ls_token = '8415e0a065d9382be7643284f113acaca84ff989'
    if not ls_token:
        return jsonify({"error": "Label Studio API token not configured"}), 500

    # 3. 发起带鉴权的请求
    headers = {
        'Authorization': f'Token {ls_token}'
    }
    resp = requests.get(image_url, headers=headers)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        return jsonify({
            "error": "Failed to fetch image from Label Studio",
            "status_code": resp.status_code,
            "details": str(e)
        }), resp.status_code

    # 4. 用 Pillow 打开图片并转为 RGB
    img = Image.open(BytesIO(resp.content))
    if img.mode in ('RGBA', 'LA'):
        img = img.convert('RGB')

    # 5. 在内存中生成 PDF
    pdf_buffer = BytesIO()
    img.save(pdf_buffer, format='PDF', resolution=100.0)
    pdf_buffer.seek(0)

    # 6. 返回 PDF 给客户端
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name='image.pdf',
        mimetype='application/pdf'
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)), debug=True)
