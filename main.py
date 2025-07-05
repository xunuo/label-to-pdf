from flask import Flask, send_file, jsonify, request
import os
import requests
from io import BytesIO
from PIL import Image

app = Flask(__name__)

LS_HOST = "https://itag.app"
LS_TOKEN = os.getenv('label_studio_api_token')
if not LS_TOKEN:
    raise RuntimeError("请先在环境变量中配置 label_studio_api_token")

@app.route('/')
def index():
    return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})

@app.route('/download')
def download():
    # 1. 获取 project ID
    project_id = request.args.get('project')
    if not project_id:
        return jsonify({"error": "请通过 ?project=<id> 指定项目 ID"}), 400

    headers = {'Authorization': f'Token {LS_TOKEN}'}

    # 2. 调用 Projects API，取 title
    proj_api = f"{LS_HOST}/api/projects/{project_id}"
    proj_resp = requests.get(proj_api, headers=headers)
    try:
        proj_resp.raise_for_status()
    except requests.HTTPError as e:
        return jsonify({
            "error": "无法获取 Project 信息",
            "status_code": proj_resp.status_code,
            "details": str(e)
        }), proj_resp.status_code

    title = proj_resp.json().get('title', f'project_{project_id}')

    # 3. 获取图片 URL（支持传参覆盖）
    image_url = request.args.get(
        'url',
        'https://itag.app/data/upload/1/e5660918-15723dp-images-1.jpg'
    )

    # 4. 下载图片
    img_resp = requests.get(image_url, headers=headers)
    try:
        img_resp.raise_for_status()
    except requests.HTTPError as e:
        return jsonify({
            "error": "下载图片失败",
            "status_code": img_resp.status_code,
            "details": str(e)
        }), img_resp.status_code

    # 5. 用 Pillow 打开并转为 RGB
    img = Image.open(BytesIO(img_resp.content))
    if img.mode in ('RGBA', 'LA'):
        img = img.convert('RGB')

    # 6. 在内存生成 PDF
    pdf_buffer = BytesIO()
    img.save(pdf_buffer, format='PDF', resolution=100.0)
    pdf_buffer.seek(0)

    # 7. 返回 PDF，文件名为 <title>.pdf
    filename = f"{title}.pdf"
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.getenv("PORT", 5000)),
        debug=True
    )
