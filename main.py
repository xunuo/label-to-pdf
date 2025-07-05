#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask 应用：一键拉取 Label Studio 私有图像和标注，生成带注释的 PDF 并下载。

使用前请在环境变量中配置：
  label_studio_host=https://itag.app
  label_studio_api_token=<你的 API Token>
"""
import os
import re
from decimal import Decimal, getcontext
from io import BytesIO

import requests
from flask import Flask, send_file, jsonify, request
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import Color
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 注册字体
BASE_DIR = os.path.dirname(__file__)
FONT_PATH = os.path.join(BASE_DIR, 'DejaVuSans.ttf')
pdfmetrics.registerFont(TTFont("DejaVuSans", FONT_PATH))

app = Flask(__name__)

LABEL_STUDIO_HOST  = os.getenv('label_studio_host', 'https://itag.app')
LABEL_STUDIO_TOKEN = os.getenv('label_studio_api_token')
if not LABEL_STUDIO_TOKEN:
    raise RuntimeError("请先在环境变量中配置 label_studio_api_token")


def parse_html_color(col, alpha=None):
    from reportlab.lib import colors
    if isinstance(col, Color):
        return Color(col.red, col.green, col.blue, alpha or col.alpha)
    if isinstance(col, (tuple, list)):
        vals = list(col)
        if max(vals) > 1:
            vals = [v/255 for v in vals]
        r, g, b = vals[:3]
        a = vals[3] if len(vals) == 4 else (alpha or 1.0)
        return Color(r, g, b, alpha=a)
    s = col.strip().lower()
    if s.startswith('#') or all(c in '0123456789abcdef' for c in s):
        hs = s.lstrip('#')
        if len(hs) == 6:
            r = int(hs[0:2],16)/255
            g = int(hs[2:4],16)/255
            b = int(hs[4:6],16)/255
            a = alpha or 1.0
        elif len(hs) == 8:
            r = int(hs[0:2],16)/255
            g = int(hs[2:4],16)/255
            b = int(hs[4:6],16)/255
            a = (int(hs[6:8],16)/255) if alpha is None else alpha
        else:
            raise ValueError(f"Invalid hex color: {col}")
        return Color(r, g, b, alpha=a)
    try:
        base = getattr(colors, s)
        return parse_html_color(base, alpha=alpha)
    except Exception:
        raise ValueError(f"Unknown color name: {col}")


def convert_length_text(text: str) -> str:
    """
    将英尺英寸格式的文本转换为米，并格式化输出。
    支持：
      - "155 5 14" （feet inches frac）
      - "155' 5 1/4\""
      - "155'5\""
      - 纯数字 "155"
    输出示例： 155' 5½" = 47.123 m
    """
    frac_map = {
        (1,2): '½', (1,3): '⅓', (2,3): '⅔',
        (1,4): '¼', (3,4): '¾',
        (1,5): '⅕', (2,5): '⅖', (3,5): '⅗', (4,5): '⅘',
        (1,6): '⅙', (5,6): '⅚',
        (1,8): '⅛', (3,8): '⅜', (5,8): '⅝', (7,8): '⅞',
    }
    getcontext().prec = 10
    FOOT_TO_M  = Decimal('0.3048')
    INCH_TO_M = Decimal('0.0254')

    s = text.strip()
    try:
        m = re.match(r"^(\d+)\s*'\s*(\d+)?(?:\s+(\d+)\s*/\s*(\d+))?\"?$", s)
        if m:
            feet   = int(m.group(1))
            inches = int(m.group(2)) if m.group(2) else 0
            num = int(m.group(3)) if m.group(3) else 0
            den = int(m.group(4)) if m.group(4) else 0
        else:
            parts = s.split()
            if not 1 <= len(parts) <= 3 or not all(p.replace('/','').isdigit() for p in parts):
                raise ValueError
            feet   = int(parts[0])
            inches = int(parts[1]) if len(parts) >= 2 else 0
            if len(parts) == 3:
                if '/' in parts[2]:
                    num_s, den_s = parts[2].split('/', 1)
                    num, den = int(num_s), int(den_s)
                else:
                    v = parts[2]
                    num, den = int(v[:-1]), int(v[-1])
            else:
                num = den = 0

        total_m = Decimal(feet) * FOOT_TO_M + Decimal(inches) * INCH_TO_M
        if num and den:
            total_m += (Decimal(num) / Decimal(den)) * INCH_TO_M

        meters_str = f"{total_m:.3f}"
        res = f"{feet}'"
        if inches or (num and den):
            res += f" {inches}"
        if num and den:
            res += frac_map.get((num, den), f"{num}/{den}")
        if inches or (num and den):
            res += '"'
        res += f" = {meters_str} m"
        return res
    except Exception:
        return text


def convert_bearing_text(text: str) -> str:
    """
    将度分秒格式的文本格式化输出。
    支持："D M S" 形式，兼容小数秒，例如 "30 15 20.5"
    输出示例： 30° 15′ 20.5″
    """
    parts = text.strip().split()
    try:
        d = parts[0]
        m = parts[1] if len(parts) >= 2 else '0'
        s = parts[2] if len(parts) >= 3 else '0'
        return f"{d}° {m}′ {s}″"
    except Exception:
        return text


def load_annotations(task_json: dict) -> list:
    annots = []
    results = task_json.get('annotations', [{}])[0].get('result', [])
    rects, texts, labels = {}, {}, {}
    for e in results:
        eid, t = e['id'], e['type']
        if t in ('rectangle', 'polygon'):
            rects[eid] = e['value']
        elif t == 'labels':
            labs = e['value'].get('labels', [])
            if labs:
                labels[eid] = labs[0]
        elif t == 'textarea':
            texts[eid] = ''.join(e['value'].get('text', []))
    for eid, val in rects.items():
        annots.append({
            'type':  'rectangle',
            'value': val,
            'text':  texts.get(eid, ''),
            'label': labels.get(eid),
        })
    return annots


def annotate_image_to_pdf(img: Image.Image, annots: list, buf: BytesIO, label_color_map: dict):
    w, h = img.size
    max_dim = 6000
    if max(w, h) > max_dim:
        ratio = max_dim / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        w, h = img.size

    c = canvas.Canvas(buf, pagesize=(w, h), pageCompression=True)
    img_bio = BytesIO()
    img.save(img_bio, format='JPEG', quality=80, optimize=True)
    img_bio.seek(0)
    c.drawImage(ImageReader(img_bio), 0, 0, width=w, height=h)

    font_size = 10
    padding   = font_size * 0.2

    for ann in annots:
        if ann['type'] not in ('rectangle', 'polygon'): continue
        val   = ann['value']
        label = ann.get('label')
        raw_text = ann.get('text', '')

        # 选择并格式化文本
        if label == 'Length':
            icon = '📏'
            text = convert_length_text(raw_text)
        elif label == 'Bearing':
            icon = '📐'
            text = convert_bearing_text(raw_text)
        else:
            icon = ''
            text = raw_text
        text = icon + text

        bg_col = label_color_map.get(label, "green")
        st_col = label_color_map.get(label, "green")
        box_fill_color   = parse_html_color(bg_col, alpha=0.15)
        box_stroke_color = parse_html_color(st_col, alpha=0.5)
        text_bg_color    = parse_html_color(st_col, alpha=0.4)
        text_bg_stroke   = parse_html_color(st_col, alpha=0.5)
        font_color       = parse_html_color("white", alpha=0.8)

        xc     = (val['x']      / 100) * w
        yc     = h - (val['y']   / 100) * h
        rect_w = (val['width']  / 100) * w
        rect_h = (val['height'] / 100) * h

        tw   = stringWidth(text, "DejaVuSans", font_size)
        bg_w = max(tw + 2 * padding, rect_w)
        bg_h = font_size + 2 * padding

        c.saveState()
        c.translate(xc, yc)
        rot = val.get('rotation', 0)
        c.rotate(-rot)
        c.translate(rect_w / 2, 0)

        c.setFillColor(box_fill_color)
        c.setStrokeColor(box_stroke_color)
        c.rect(-rect_w/2, -rect_h, rect_w, rect_h, fill=1, stroke=1)

        c.setFillColor(text_bg_color)
        c.setStrokeColor(text_bg_stroke)
        c.rect(-bg_w/2, -rect_h, bg_w, bg_h, fill=1, stroke=1)

        c.setFillColor(font_color)
        c.setFont("DejaVuSans", font_size)
        text_y = -rect_h + font_size/2 - padding/2
        c.drawCentredString(0, text_y, text)
        c.restoreState()

    c.showPage()
    c.save()

@app.route('/')
def index():
    return jsonify({"Choo Choo": "Welcome to Xu's Label Studio PDF Exportor 🚅"})

@app.route('/download')
def download():
    project_id = request.args.get('project')
    task_id    = request.args.get('task')
    if not project_id or not task_id:
        return jsonify({"error":"请通过 ?project=<id>&task=<id> 指定参数"}), 400

    headers = {'Authorization': f"Token {LABEL_STUDIO_TOKEN}"}
    pj = requests.get(f"{LABEL_STUDIO_HOST}/api/projects/{project_id}", headers=headers)
    pj.raise_for_status()
    pj_json = pj.json()

    title = pj_json.get('title', f'project_{project_id}')
    plc = pj_json.get('parsed_label_config', {}).get('label', {}).get('labels_attrs', {})
    label_color_map = { lbl: attrs.get('background', '#00ff00') for lbl, attrs in plc.items() }

    tj = requests.get(f"{LABEL_STUDIO_HOST}/api/tasks/{task_id}", headers=headers)
    tj.raise_for_status()
    task_json = tj.json()

    ocr_path = task_json.get('data', {}).get('ocr')
    if not ocr_path:
        return jsonify({"error":"Task JSON 中未找到 data['ocr']"}), 500
    ir = requests.get(f"{LABEL_STUDIO_HOST}{ocr_path}", headers=headers)
    ir.raise_for_status()
    img = Image.open(BytesIO(ir.content)).convert('RGB')

    annots = load_annotations(task_json)
    pdf_buf = BytesIO()
    annotate_image_to_pdf(img, annots, pdf_buf, label_color_map)
    pdf_buf.seek(0)

    filename = f"{title}[{task_id}].pdf"
    return send_file(pdf_buf, as_attachment=True,
                     download_name=filename, mimetype='application/pdf')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)), debug=True)
