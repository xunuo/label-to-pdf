```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask 应用：一键拉取 Label Studio 私有图像和标注，生成带注释的 PDF 并下载。

为支持 Unicode 分数字形（如 ⅜），引入 DejaVu Sans 字体。
请在项目根目录下创建一个 fonts/ 目录，并下载 DejaVuSans.ttf 放入其中：
  https://github.com/dejavu-fonts/dejavu-fonts/blob/master/ttf/DejaVuSans.ttf

环境变量：
  label_studio_host=https://itag.app
  label_studio_api_token=<你的 API Token>
"""
import os
import sys
import requests
from io import BytesIO
from decimal import Decimal, getcontext

from flask import Flask, send_file, jsonify, request
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import Color, green, white
from reportlab.pdfbase.pdfmetrics import stringWidth, registerFont
from reportlab.pdfbase.ttfonts import TTFont

app = Flask(__name__)

# ——— 配置 ——— #
LABEL_STUDIO_HOST  = os.getenv('label_studio_host', 'https://itag.app')
LABEL_STUDIO_TOKEN = os.getenv('label_studio_api_token')
if not LABEL_STUDIO_TOKEN:
    print("ERROR: 环境变量 label_studio_api_token 未配置！", file=sys.stderr)
    sys.exit(1)
# —————————— #

# 注册 DejaVu Sans 用于支持 Unicode 包括分数字形
FONT_PATH = os.path.join(os.path.dirname(__file__), 'fonts', 'DejaVuSans.ttf')
if not os.path.isfile(FONT_PATH):
    print(f"ERROR: 找不到字体文件：{FONT_PATH}", file=sys.stderr)
    sys.exit(1)
registerFont(TTFont("DejaVuSans", FONT_PATH))


def convert_text_to_meters_text(text: str) -> str:
    frac_map = {
        (1,2): '½', (1,3): '⅓', (2,3): '⅔',
        (1,4): '¼', (3,4): '¾',
        (1,5): '⅕', (2,5): '⅖', (3,5): '⅗', (4,5): '⅘',
        (1,6): '⅙', (5,6): '⅚',
        (1,8): '⅛', (3,8): '⅜', (5,8): '⅝', (7,8): '⅞',
    }
    getcontext().prec = 10
    FOOT_TO_M = Decimal('0.3048')
    INCH_TO_M = Decimal('0.0254')
    try:
        parts = text.strip().split()
        if not 1 <= len(parts) <= 3 or not all(p.isdigit() for p in parts):
            raise ValueError
        feet = int(parts[0])
        inches = int(parts[1]) if len(parts) >= 2 else 0
        frac = int(parts[2]) if len(parts) == 3 else 0

        numerator = int(str(frac)[:-1]) if frac else 0
        denominator = int(str(frac)[-1]) if frac else 1

        total_m = Decimal(feet) * FOOT_TO_M + Decimal(inches) * INCH_TO_M
        if frac:
            total_m += (Decimal(numerator) / Decimal(denominator)) * INCH_TO_M

        meters_str = f"{total_m:.3f}"
        result = f"{feet}'"
        if inches or frac:
            result += f" {inches}"
        if frac:
            result += frac_map.get((numerator, denominator), f"{numerator}/{denominator}")
        if inches or frac:
            result += '"'
        result += f" = {meters_str} m"
        return result
    except Exception:
        return text


def load_annotations(task_json: dict) -> list:
    results = task_json.get('annotations', [])[0].get('result', [])
    rects, texts = {}, {}
    for e in results:
        if e['type'] == 'rectangle':
            rects[e['id']] = e['value']
        elif e['type'] == 'textarea':
            texts[e['id']] = ''.join(e['value'].get('text', []))
    annots = []
    for eid, rect in rects.items():
        annots.append({'value': rect, 'text': texts.get(eid, '')})
    return annots


def annotate_image_to_pdf(img: Image.Image, annots: list, buf: BytesIO,
                          bg_alpha: float = 0.6, font_size: float = 10):
    w, h = img.size
    c = canvas.Canvas(buf, pagesize=(w, h))

    # 绘制原图
    img_bio = BytesIO()
    img.save(img_bio, format='PNG')
    img_bio.seek(0)
    reader = ImageReader(img_bio)
    c.drawImage(reader, 0, 0, width=w, height=h)

    for ann in annots:
        val = ann['value']
        rot = val.get('rotation', 0)
        xc = (val['x'] / 100) * w
        yc = h - (val['y'] / 100) * h
        rect_w = (val['width'] / 100) * w
        text = convert_text_to_meters_text(ann['text'])

        c.saveState()
        c.translate(xc, yc)
        c.rotate(-rot)
        c.translate(rect_w / 2, 0)

        tw = stringWidth(text, "DejaVuSans", font_size)
        pad = font_size * 0.2
        bg_w = max(tw + 2 * pad, rect_w)
        bg_h = font_size + 2 * pad

        c.setFillColor(Color(green.red, green.green, green.blue, alpha=bg_alpha))
        c.rect(-bg_w/2, -bg_h/2, bg_w, bg_h, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("DejaVuSans", font_size)
        c.drawCentredString(0, -font_size/2 + pad/2, text)
        c.restoreState()

    c.showPage()
    c.save()


@app.route('/')
def index():
    return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})


@app.route('/download')
def download():
    project_id = request.args.get('project')
    task_id    = request.args.get('task')
    if not project_id or not task_id:
        return jsonify({"error": "请通过 ?project=<id>&task=<id> 指定参数"}), 400

    headers = {'Authorization': f"Token {LABEL_STUDIO_TOKEN}"}

    # 获取项目标题
    pj = requests.get(f"{LABEL_STUDIO_HOST}/api/projects/{project_id}", headers=headers)
    pj.raise_for_status()
    title = pj.json().get('title', f'project_{project_id}')

    # 获取 Task JSON
    tj = requests.get(f"{LABEL_STUDIO_HOST}/api/tasks/{task_id}", headers=headers)
    tj.raise_for_status()
    task_json = tj.json()

    # 下载 OCR 图像
    ocr_path = task_json.get('data', {}).get('ocr')
    if not ocr_path:
        return jsonify({"error": "Task JSON 中未找到 data['ocr']"}), 500
    ir = requests.get(f"{LABEL_STUDIO_HOST}{ocr_path}", headers=headers)
    ir.raise_for_status()
    img = Image.open(BytesIO(ir.content)).convert('RGB')

    # 渲染标注到 PDF
    annots = load_annotations(task_json)
    pdf_buf = BytesIO()
    annotate_image_to_pdf(img, annots, pdf_buf)
    pdf_buf.seek(0)

    filename = f"{title}.pdf"
    return send_file(
        pdf_buf,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )


if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.getenv("PORT", 5000)),
        debug=False
    )
```
