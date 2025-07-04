from flask import Flask, send_file, jsonify, request
import os
import requests
from io import BytesIO
from PIL import Image

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})

@app.route('/download-pdf')
def download_pdf():
    # 如果想固定用这个地址，直接写死；否则也可以通过 query 参数传入
    image_url = request.args.get(
        'url',
        'https://itag.app/data/upload/1/e5660918-15723dp-images-1.jpg'
    )

    # 1. 拉取线上图片
    resp = requests.get(image_url)
    resp.raise_for_status()

    # 2. 用 Pillow 打开并转为 RGB（去除透明通道）
    img = Image.open(BytesIO(resp.content))
    if img.mode in ('RGBA', 'LA'):
        img = img.convert('RGB')

    # 3. 在内存中生成 PDF
    pdf_buffer = BytesIO()
    img.save(pdf_buffer, format='PDF', resolution=100.0)
    pdf_buffer.seek(0)

    # 4. 返回 PDF 下载
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name='image.pdf',
        mimetype='application/pdf'
    )

if __name__ == '__main__':
    # Railway 要监听所有接口
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)), debug=True)
