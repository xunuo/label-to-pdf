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
from decimal import Decimal, getcontext

from flask import Flask, send_file, jsonify, request
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.lib.colors import Color
from reportlab.pdfbase.pdfmetrics import stringWidth

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


BASE_DIR = os.path.dirname(__file__)
FONT_PATH = os.path.join(BASE_DIR, 'DejaVuSans.ttf')

# 注册字体
pdfmetrics.registerFont(TTFont("DejaVuSans", FONT_PATH))

app = Flask(__name__)

# —— 配置 —— #
LABEL_STUDIO_HOST  = os.getenv('label_studio_host', 'https://itag.app')
LABEL_STUDIO_TOKEN = os.getenv('label_studio_api_token')
if not LABEL_STUDIO_TOKEN:
    raise RuntimeError("请先在环境变量中配置 label_studio_api_token")
# —————— #


def convert_text_to_meters_text(text: str) -> str:
    frac_map = {
        (1, 2): '½', (1, 3): '⅓', (2, 3): '⅔',
        (1, 4): '¼', (3, 4): '¾',
        (1, 5): '⅕', (2, 5): '⅖', (3, 5): '⅗', (4, 5): '⅘',
        (1, 6): '⅙', (5, 6): '⅚',
        (1, 8): '⅛', (3, 8): '⅜', (5, 8): '⅝', (7, 8): '⅞',
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
    annots = []
    results = task_json.get('annotations', [])[0].get('result', [])
    rects, texts = {}, {}
    for e in results:
        eid = e['id']
        if e['type'] == 'rectangle':
            rects[eid] = e['value']
        elif e['type'] == 'textarea':
            texts[eid] = ''.join(e['value'].get('text', []))
    for eid, rect in rects.items():
        annots.append({'value': rect, 'text': texts.get(eid, '')})
    return annots

def parse_html_color(col, alpha=None):
    """
    解析 HTML/CSS 里的颜色值，返回 reportlab.lib.colors.Color 对象。

    参数
    ----
    col : str or tuple or Color
        - "#RRGGBB" 或 "RRGGBB"（可带/不带 #）
        - "#RRGGBBAA" 或 "RRGGBBAA"（带透明度通道）
        - CSS 预定义名字，如 "blue", "lightgreen"
        - (r, g, b) 三元组，或 (r, g, b, a) 四元组，范围 0–1 或 0–255
        - 已经是一个 reportlab.lib.colors.Color 实例
    alpha : float, optional
        如果传入，这个透明度会覆盖 col 里任何已有的 alpha，范围 0.0–1.0。

    返回
    ----
    reportlab.lib.colors.Color
    """
    # 如果已经是 Color，直接覆盖 alpha（如果有）
    if isinstance(col, Color):
        base = col
        if alpha is not None:
            return Color(base.red, base.green, base.blue, alpha=alpha)
        return base

    # 如果是 元组／列表
    if isinstance(col, (tuple, list)):
        vals = list(col)
        # 如果给的是 0–255，就转换到 0–1
        if max(vals) > 1:
            vals = [v/255.0 for v in vals]
        # 拆成 r,g,b,(a)
        r, g, b = vals[0], vals[1], vals[2]
        a = vals[3] if len(vals) == 4 else alpha or 1.0
        return Color(r, g, b, alpha=a)

    # 到这里，col 应该是字符串
    s = col.strip().lower()

    # 1) Hex 格式
    if s.startswith('#') or all(c in '0123456789abcdef' for c in s):
        hs = s.lstrip('#')
        # 支持 RRGGBB 或 RRGGBBAA
        if len(hs) == 6:
            r8, g8, b8 = int(hs[0:2], 16), int(hs[2:4], 16), int(hs[4:6], 16)
            a = alpha if alpha is not None else 1.0
        elif len(hs) == 8:
            r8, g8, b8 = int(hs[0:2], 16), int(hs[2:4], 16), int(hs[4:6], 16)
            a8 = int(hs[6:8], 16)
            a = (alpha if alpha is not None else a8/255.0)
        else:
            raise ValueError(f"无效的 hex 长度：{hs!r}")
        return Color(r8/255.0, g8/255.0, b8/255.0, alpha=a)

    # 2) 预定义名字（找 reportlab.lib.colors）
    try:
        base = getattr(colors, s)
        # 有些名字直接就是 Color 或 HexColor 实例
        if isinstance(base, Color):
            return Color(base.red, base.green, base.blue,
                         alpha=alpha if alpha is not None else getattr(base, 'alpha', 1.0))
        # 如果不是 Color，就递归一次（万一是 HexColor）
        return parse_html_color(base, alpha=alpha)
    except AttributeError:
        raise ValueError(f"未知的颜色名字：{col!r}")
      

def annotate_image_to_pdf(img: Image.Image, annots: list, buf: BytesIO):
    w, h = img.size
    c = canvas.Canvas(buf, pagesize=(w, h))

    # 用 ImageReader 读取内存中的图片
    img_bio = BytesIO()
    img.save(img_bio, format='PNG')
    img_bio.seek(0)
    reader = ImageReader(img_bio)
    c.drawImage(reader, 0, 0, width=w, height=h)


    font_color = "white"
    font_size = 10
    font_alpha = 0.8
  
    bg_color = "green"
    bg_alpha = 0.6
  
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

        c.setFillColor(parse_html_color(bg_color, alpha=bg_alpha))
        c.rect(-bg_w/2, -bg_h/2, bg_w, bg_h, fill=1, stroke=1)

        c.setFillColor(parse_html_color(font_color, alpha=font_alpha))
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

    # 获取 Project title
    pj = requests.get(f"{LABEL_STUDIO_HOST}/api/projects/{project_id}", headers=headers)
    try:
        pj.raise_for_status()
        title = pj.json().get('title', f'project_{project_id}')
    except requests.HTTPError as e:
        return jsonify({"error": "获取 Project 失败", "details": str(e)}), pj.status_code

    # 获取 Task JSON
    tj = requests.get(f"{LABEL_STUDIO_HOST}/api/tasks/{task_id}", headers=headers)
    try:
        tj.raise_for_status()
    except requests.HTTPError as e:
        return jsonify({"error": "获取 Task 失败", "details": str(e)}), tj.status_code
    task_json = tj.json()

    # 下载 OCR 图像
    ocr_path = task_json.get('data', {}).get('ocr')
    if not ocr_path:
        return jsonify({"error": "Task JSON 中未找到 data['ocr']"}), 500
    ir = requests.get(f"{LABEL_STUDIO_HOST}{ocr_path}", headers=headers)
    try:
        ir.raise_for_status()
    except requests.HTTPError as e:
        return jsonify({"error": "下载图像失败", "details": str(e)}), ir.status_code
    img = Image.open(BytesIO(ir.content)).convert('RGB')

    # 渲染注释到 PDF
    annots = load_annotations(task_json)
    pdf_buf = BytesIO()
    annotate_image_to_pdf(img, annots, pdf_buf)
    pdf_buf.seek(0)

    # 触发下载
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
        debug=True
    )
