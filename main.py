#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask 应用：一键拉取 Label Studio 私有图像和标注，生成带注释的 PDF 并下载。

使用前请在环境变量中配置：
  label_studio_host=https://itag.app
  label_studio_api_token=<你的 API Token>
"""
import os
import sys
import requests
from io import BytesIO
import re
from decimal import Decimal, getcontext

from flask import Flask, send_file, jsonify, request
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import Color
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

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


def convert_text_to_meters_text(text: str) -> str:
    """
    支持以下输入格式：
      - "155 5 14"    （feet inches frac，不带符号，三部分均数字）
      - "155' 5 1/4\""
      - "155'5\""
      - "155'5 1/4\""
      - "155' 5\""
      - 纯数字 "155"
    """
    # 映射常见分数到符号
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
        # 1) 尝试匹配 带符号的格式：feet'inches frac"
        m = re.match(r"^(\d+)\s*'\s*(\d+)?(?:\s+(\d+)\s*/\s*(\d+))?\"?$", s)
        if m:
            feet = int(m.group(1))
            inches = int(m.group(2)) if m.group(2) else 0
            if m.group(3) and m.group(4):
                num = int(m.group(3))
                den = int(m.group(4))
            else:
                num = den = 0
        else:
            # 2) 纯数字拆分：feet inches frac，最多三部分
            parts = s.split()
            if not 1 <= len(parts) <= 3 or not all(p.isdigit() for p in parts):
                raise ValueError
            feet   = int(parts[0])
            inches = int(parts[1]) if len(parts) >= 2 else 0
            if len(parts) == 3:
                # 最后一部分是 frac，例如 "1/4" 或 "14"
                if '/' in parts[2]:
                    num_s, den_s = parts[2].split('/', 1)
                    num, den = int(num_s), int(den_s)
                else:
                    # 如果是连续数字，将最后一位当分母，其余当分子
                    v = parts[2]
                    num, den = int(v[:-1]), int(v[-1])
            else:
                num = den = 0

        # 计算总米数
        total_m = Decimal(feet) * FOOT_TO_M + Decimal(inches) * INCH_TO_M
        if num and den:
            total_m += (Decimal(num) / Decimal(den)) * INCH_TO_M

        meters_str = f"{total_m:.3f}"
        # 组装结果字符串
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
        # 出错时原样返回
        return text


def load_annotations(task_json: dict) -> list:
    annots = []
    results = task_json.get('annotations',[{}])[0].get('result',[])
    rects, texts = {}, {}
    for e in results:
        eid = e['id']
        if e['type']=='rectangle':
            rects[eid] = e['value']
        elif e['type']=='textarea':
            texts[eid] = ''.join(e['value'].get('text',[]))
    for eid, rect in rects.items():
        annots.append({'value': rect, 'text': texts.get(eid,'')})
    return annots


def annotate_image_to_pdf(img: Image.Image, annots: list, buf: BytesIO):
    # —— 可选：先做下采样 —— #
    w, h = img.size
    max_dim = 6000
    if max(w, h) > max_dim:
        ratio = max_dim / max(w, h)
        img = img.resize((int(w*ratio), int(h*ratio)), Image.LANCZOS)
        w, h = img.size

    # Canvas 开启流压缩
    c = canvas.Canvas(buf, pagesize=(w, h), pageCompression=True)

    # 用 JPEG 嵌入底图
    img_bio = BytesIO()
    img.save(img_bio, format='JPEG', quality=80, optimize=True)
    img_bio.seek(0)
    reader = ImageReader(img_bio)
    c.drawImage(reader, 0, 0, width=w, height=h)

    # 样式预计算
    font_size = 10
    font_color       = parse_html_color("white", alpha=0.8)
    padding          = font_size * 0.2
    bg_h             = font_size + 2 * padding
    box_fill_color   = parse_html_color("green", alpha=0.1)
    box_stroke_color = parse_html_color("green", alpha=0.2)
    text_bg_color    = parse_html_color("green", alpha=0.4)
    text_bg_stroke_color   = parse_html_color("green", alpha=0.2)
                            
    for ann in annots:
        val    = ann['value']
        rot    = val.get('rotation', 0)
        # 1) 框中心像素
        xc     = (val['x']      / 100) * w
        yc     = h - (val['y']   / 100) * h
        # 2) 框尺寸
        rect_w = (val['width']  / 100) * w
        rect_h = (val['height'] / 100) * h

        text = convert_text_to_meters_text(ann['text'])
        tw   = stringWidth(text, "DejaVuSans", font_size)

        c.saveState()
        # 定位到框中心 → 旋转 → 再平移半宽
        c.translate(xc, yc)
        c.rotate(-rot)
        c.translate(rect_w / 2, 0)

        # 注释框背景
        c.setFillColor(box_fill_color)
        c.setStrokeColor(box_stroke_color)
        c.rect(-rect_w/2, -rect_h, rect_w, rect_h, fill=1, stroke=1)

        # 文字背景框（同宽、紧贴上方）
        bg_w = max(tw + 2*padding, rect_w)
        c.setFillColor(text_bg_color)
        c.setStrokeColor(text_bg_stroke_color)
        c.rect(-bg_w/2, -rect_h, bg_w, bg_h, fill=1, stroke=1)

        # 渲染文字（水平 & 垂直居中于文字背景）
        c.setFillColor(font_color)
        c.setFont("DejaVuSans", font_size)
        text_y = -rect_h + font_size/2 - padding/2
        c.drawCentredString(0, text_y, text)

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
        return jsonify({"error":"请通过 ?project=<id>&task=<id> 指定参数"}),400

    headers = {'Authorization':f"Token {LABEL_STUDIO_TOKEN}"}
    pj = requests.get(f"{LABEL_STUDIO_HOST}/api/projects/{project_id}",headers=headers)
    pj.raise_for_status()
    title = pj.json().get('title',f'project_{project_id}')

    tj = requests.get(f"{LABEL_STUDIO_HOST}/api/tasks/{task_id}",headers=headers)
    tj.raise_for_status()
    task_json = tj.json()

    ocr_path = task_json.get('data',{}).get('ocr')
    if not ocr_path:
        return jsonify({"error":"Task JSON 中未找到 data['ocr']"}),500
    ir = requests.get(f"{LABEL_STUDIO_HOST}{ocr_path}",headers=headers)
    ir.raise_for_status()
    img = Image.open(BytesIO(ir.content)).convert('RGB')

    annots = load_annotations(task_json)
    pdf_buf = BytesIO()
    annotate_image_to_pdf(img, annots, pdf_buf)
    pdf_buf.seek(0)

    filename = f"{title}.pdf"
    return send_file(pdf_buf, as_attachment=True,
                     download_name=filename,mimetype='application/pdf')


if __name__ == '__main__':
    app.run(host='0.0.0.0',port=int(os.getenv("PORT",5000)),debug=True)
