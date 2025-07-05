from flask import Flask, send_file, jsonify, request
import os, requests
from io import BytesIO
from PIL import Image

app = Flask(__name__)

LS_HOST      = "https://itag.app"
LS_TOKEN     = os.getenv('label_studio_api_token')
if not LS_TOKEN:
    raise RuntimeError("请先在环境变量中配置 label_studio_api_token")

@app.route('/')
def index():
    return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})

@app.route('/download')
def download():
    # 1. 获取 URL 参数 project 和 task
    project_id = request.args.get('project')
    task_id    = request.args.get('task')
    if not project_id or not task_id:
        return jsonify({"error": "请通过 ?project=<id>&task=<id> 指定项目和任务"}), 400

    headers = {'Authorization': f'Token {LS_TOKEN}'}

    # 2. 取 Project title 作为文件名
    proj_api  = f"{LS_HOST}/api/projects/{project_id}"
    proj_resp = requests.get(proj_api, headers=headers)
    try:
        proj_resp.raise_for_status()
        title = proj_resp.json().get('title', f'project_{project_id}')
    except requests.HTTPError as e:
        return jsonify({
            "error": "无法获取 Project 信息",
            "status_code": proj_resp.status_code,
            "details": str(e)
        }), proj_resp.status_code

    # 3. 调用 Tasks API，拿到 data['ocr']
    task_api  = f"{LS_HOST}/api/tasks/{task_id}"
    task_resp = requests.get(task_api, headers=headers)
    try:
        task_resp.raise_for_status()
        task_json = task_resp.json()
    except requests.HTTPError as e:
        return jsonify({
            "error": "无法获取 Task 信息",
            "status_code": task_resp.status_code,
            "details": str(e)
        }), task_resp.status_code

    # 4. 提取 OCR 路径并拼完整 URL
    ocr_path = task_json.get('data', {}).get('ocr')
    if not ocr_path:
        return jsonify({"error": "Task JSON 中未包含 data['ocr']"}), 500
    image_url = f"{LS_HOST}{ocr_path}"

    # 5. 下载图片
    img_resp = requests.get(image_url, headers=headers)
    try:
        img_resp.raise_for_status()
    except requests.HTTPError as e:
        return jsonify({
            "error": "下载图片失败",
            "status_code": img_resp.status_code,
            "details": str(e)
        }), img_resp.status_code

    # 6. 用 Pillow 打开并转为 RGB
    img = Image.open(BytesIO(img_resp.content))
    if img.mode in ('RGBA', 'LA'):
        img = img.convert('RGB')

    # 7. 在内存生成 PDF
    pdf_buffer = BytesIO()
    img.save(pdf_buffer, format='PDF', resolution=100.0)
    pdf_buffer.seek(0)

    # 8. 返回 PDF，文件名为 <title>.pdf
    filename = f"{title}.pdf"
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,    # Flask 2.x 用 download_name
        mimetype='application/pdf'
    )

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.getenv("PORT", 5000)),
        debug=True
    )
