#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask 应用：一键拉取 Label Studio 私有图像和标注，生成带注释的 PDF 并下载。

使用前请在环境变量中配置：
  LABEL_STUDIO_HOST=https://itag.app
  LABEL_STUDIO_TOKEN=<你的 API Token>

所有时间将转换为澳大利亚悉尼时间（AEST/AEDT）。
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
from dateutil import parser, tz

# -------------------------------
# 应用初始化
# -------------------------------
app = Flask(__name__)

# 环境变量配置
LABEL_STUDIO_HOST = os.getenv('LABEL_STUDIO_HOST', 'https://itag.app')
LABEL_STUDIO_TOKEN = os.getenv('LABEL_STUDIO_TOKEN')
if not LABEL_STUDIO_TOKEN:
    raise RuntimeError("请先配置环境变量：LABEL_STUDIO_TOKEN")

# 注册自定义字体（支持中文）
BASE_DIR = os.path.dirname(__file__)
FONT_PATH = os.path.join(BASE_DIR, 'DejaVuSans.ttf')
pdfmetrics.registerFont(TTFont('DejaVuSans', FONT_PATH))

# 使用悉尼时区
SYDNEY_TZ = tz.gettz('Australia/Sydney')

# -------------------------------
# 工具函数
# -------------------------------

def parse_html_color(color_val, alpha=None):
    """
    将 HTML/CSS 颜色（Hex、名称或RGB）转换为 reportlab Color 对象。
    支持 (#RRGGBB, #RRGGBBAA, css name, tuple/list)。
    alpha 可覆盖透明度。
    """
    from reportlab.lib import colors
    # 直接返回 Color
    if isinstance(color_val, Color):
        return Color(color_val.red, color_val.green, color_val.blue, alpha or color_val.alpha)
    # 列表或元组 => 归一化
    if isinstance(color_val, (tuple, list)):
        vals = [v / 255 if max(color_val) > 1 else v for v in color_val]
        r, g, b = vals[:3]
        a = vals[3] if len(vals) == 4 else (alpha or 1.0)
        return Color(r, g, b, a)
    s = color_val.strip().lower()
    # Hex 颜色
    if s.startswith('#') or all(c in '0123456789abcdef' for c in s):
        hex_str = s.lstrip('#')
        if len(hex_str) == 6:
            r = int(hex_str[0:2], 16) / 255
            g = int(hex_str[2:4], 16) / 255
            b = int(hex_str[4:6], 16) / 255
            a = alpha or 1.0
        elif len(hex_str) == 8:
            r = int(hex_str[0:2], 16) / 255
            g = int(hex_str[2:4], 16) / 255
            b = int(hex_str[4:6], 16) / 255
            a = (int(hex_str[6:8], 16) / 255) if alpha is None else alpha
        else:
            raise ValueError(f"Invalid hex color: {color_val}")
        return Color(r, g, b, a)
    # CSS 名称
    try:
        base = getattr(colors, s)
        return parse_html_color(base, alpha=alpha)
    except Exception:
        raise ValueError(f"Unknown color name: {color_val}")


def convert_length_text(text: str) -> str:
    """
    将英尺-英寸格式（支持分数）转换为米，并格式化输出。
    示例： 155' 5½" = 47.123 m
    """
    frac_map = {
        (1, 2): '½', (1, 3): '⅓', (2, 3): '⅔', (1, 4): '¼', (3, 4): '¾',
        (1, 5): '⅕', (2, 5): '⅖', (3, 5): '⅗', (4, 5): '⅘', (1, 6): '⅙',
        (5, 6): '⅚', (1, 8): '⅛', (3, 8): '⅜', (5, 8): '⅝', (7, 8): '⅞'
    }
    getcontext().prec = 10
    FOOT_TO_M = Decimal('0.3048')
    INCH_TO_M = Decimal('0.0254')
    s = text.strip()
    try:
        m = re.match(r"^(\d+)\s*'\s*(\d+)?(?:\s+(\d+)\s*/\s*(\d+))?\"?$
                     , s)
        if m:
            feet = int(m.group(1))
            inches = int(m.group(2) or 0)
            num = int(m.group(3) or 0)
            den = int(m.group(4) or 0)
        else:
            parts = s.split()
            if not (1 <= len(parts) <= 3):
                raise ValueError
            feet = int(parts[0])
            inches = int(parts[1]) if len(parts) > 1 else 0
            if len(parts) == 3:
                if '/' in parts[2]:
                    num, den = map(int, parts[2].split('/', 1))
                else:
                    val = parts[2]
                    num, den = int(val[:-1]), int(val[-1])
            else:
                num = den = 0
        total_m = Decimal(feet) * FOOT_TO_M + Decimal(inches) * INCH_TO_M
        if num and den:
            total_m += Decimal(num) / Decimal(den) * INCH_TO_M
        meter_str = f"{total_m:.3f}"
        # 构造原始尺寸字符串
        orig = f"{feet}'"
        if inches or (num and den):
            orig += f" {inches}"
        if num and den:
            orig += frac_map.get((num, den), f"{num}/{den}")
        if inches or (num and den):
            orig += '"'
        return f"{orig} = {meter_str} m"
    except Exception:
        return text


def convert_bearing_text(text: str) -> str:
    """
    将度 分 秒 转换为十进制度数并格式化输出。
    示例： 30° 15′ 20.5″ = 30.256°
    """
    parts = text.strip().split()
    try:
        deg_d = Decimal(parts[0])
        deg_m = Decimal(parts[1]) if len(parts) > 1 else Decimal(0)
        deg_s = Decimal(parts[2]) if len(parts) > 2 else Decimal(0)
        dms = f"{parts[0]}° {parts[1] if len(parts)>1 else '0'}′ {parts[2] if len(parts)>2 else '0'}″"
        getcontext().prec = 10
        decimal_degree = deg_d + deg_m / Decimal(60) + deg_s / Decimal(3600)
        return f"{dms} = {decimal_degree:.3f}°"
    except Exception:
        return text


def load_annotations(task_json: dict) -> list:
    """
    从 Label Studio 的 task JSON 中提取所有矩形/多边形标注及其文本/标签。
    返回列表，每项：{'type','value','text','label'}
    """
    annotations = []
    rect_map, text_map, label_map = {}, {}, {}
    results = task_json.get('annotations', [{}])[0].get('result', [])
    for item in results:
        eid = item['id']
        t = item['type']
        if t in ('rectangle', 'polygon'):
            rect_map[eid] = item['value']
        elif t == 'labels':
            labels = item['value'].get('labels', [])
            if labels:
                label_map[eid] = labels[0]
        elif t == 'textarea':
            text_map[eid] = ''.join(item['value'].get('text', []))
    for eid, val in rect_map.items():
        annotations.append({
            'type': 'rectangle',
            'value': val,
            'text': text_map.get(eid, ''),
            'label': label_map.get(eid)
        })
    return annotations


def annotate_image_to_pdf(
    image: Image.Image,
    annotations: list,
    output_buffer: BytesIO,
    color_map: dict,
    pdf_title: str
):
    """
    将图像和标注绘制到 PDF，并设置 PDF 标题(metadata)。
    """
    w, h = image.size
    # 防止过大导致内存问题，限制最大边
    max_dim = 6000
    if max(w, h) > max_dim:
        ratio = max_dim / max(w, h)
        image = image.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        w, h = image.size

    c = canvas.Canvas(output_buffer, pagesize=(w, h), pageCompression=True)
    c.setTitle(pdf_title)

    # 绘制底图
    img_buf = BytesIO()
    image.save(img_buf, format='JPEG', quality=80, optimize=True)
    img_buf.seek(0)
    c.drawImage(ImageReader(img_buf), 0, 0, width=w, height=h)

    font_size = 10
    padding = font_size * 0.2

    for ann in annotations:
        if ann['type'] not in ('rectangle', 'polygon'):
            continue
        value = ann['value']
        label = ann.get('label')
        raw_text = ann.get('text', '')

        # 根据标签类型调整文本
        if label == 'Length':
            icon = '↦ '
            display_text = icon + convert_length_text(raw_text)
        elif label == 'Bearing':
            icon = '∠ '
            display_text = icon + convert_bearing_text(raw_text)
        else:
            display_text = raw_text

        # 颜色设置
        base_color = color_map.get(label, '#00ff00')
        fill_color = parse_html_color(base_color, alpha=0.15)
        stroke_color = parse_html_color(base_color, alpha=0.5)
        text_bg_color = parse_html_color(base_color, alpha=0.4)
        text_border_color = parse_html_color(base_color, alpha=0.5)
        font_color = parse_html_color('white', alpha=0.8)

        # 计算位置和尺寸
        x_center = value['x'] / 100 * w
        y_center = h - (value['y'] / 100 * h)
        rect_w = value['width'] / 100 * w
        rect_h = value['height'] / 100 * h

        # 文本背景尺寸
        text_width = stringWidth(display_text, 'DejaVuSans', font_size)
        box_w = max(text_width + 2 * padding, rect_w)
        box_h = font_size + 2 * padding

        c.saveState()
        c.translate(x_center, y_center)
        rotation = value.get('rotation', 0)
        c.rotate(-rotation)
        c.translate(rect_w / 2, 0)

        # 绘制标注框
        c.setFillColor(fill_color)
        c.setStrokeColor(stroke_color)
        c.rect(-rect_w/2, -rect_h, rect_w, rect_h, fill=1, stroke=1)

        # 绘制文本背景
        c.setFillColor(text_bg_color)
        c.setStrokeColor(text_border_color)
        c.rect(-box_w/2, -rect_h, box_w, box_h, fill=1, stroke=1)

        # 绘制文本
        c.setFillColor(font_color)
        c.setFont('DejaVuSans', font_size)
        text_y = -rect_h + font_size/2 - padding/2
        c.drawCentredString(0, text_y, display_text)
        c.restoreState()

    c.showPage()
    c.save()

# -------------------------------
# 路由定义
# -------------------------------
@app.route('/')
def index():
    """根路径：欢迎信息"""
    return jsonify({"message": "Welcome to Xu's Label Studio PDF Exportor 🚅"})

@app.route('/download')
def download():
    """
    下载入口：
    - 获取项目与任务
    - 转换 updated_at 为悉尼时间
    - 构造 metadata title
    - 生成 PDF 并返回
    """
    project_id = request.args.get('project')
    task_id = request.args.get('task')
    if not project_id or not task_id:
        return jsonify({"error": "请通过 ?project=<id>&task=<id> 指定参数"}), 400

    headers = {'Authorization': f"Token {LABEL_STUDIO_TOKEN}"}

    # 获取项目名称
    project_resp = requests.get(f"{LABEL_STUDIO_HOST}/api/projects/{project_id}", headers=headers)
    project_resp.raise_for_status()
    project_data = project_resp.json()
    project_title = project_data.get('title', f'project_{project_id}')

    # 获取任务信息
    task_resp = requests.get(f"{LABEL_STUDIO_HOST}/api/tasks/{task_id}", headers=headers)
    task_resp.raise_for_status()
    task_data = task_resp.json()

    # 解析并转换 updated_at
    updated_at = task_data.get('updated_at')
    try:
        dt = parser.isoparse(updated_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz.tzutc())
        dt_sydney = dt.astimezone(SYDNEY_TZ)
        timestamp = dt_sydney.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        timestamp = updated_at

    # 构造 PDF title metadata
    pdf_title = f"{project_title}[{task_id} {timestamp}]"
    # 构造下载文件名（不含时间戳）
    download_filename = f"{project_title}[{task_id}].pdf"

    # 下载并打开图像
    ocr_path = task_data.get('data', {}).get('ocr')
    if not ocr_path:
        return jsonify({"error": "Task JSON 中未找到 data['ocr']"}), 500
    image_resp = requests.get(f"{LABEL_STUDIO_HOST}{ocr_path}", headers=headers)
    image_resp.raise_for_status()
    image = Image.open(BytesIO(image_resp.content)).convert('RGB')

    # 加载标注
    annotations = load_annotations(task_data)
    # 构建颜色映射
    color_map = {
        label: attrs.get('background', '#00ff00')
        for label, attrs in project_data.get('parsed_label_config', {})
                                      .get('label', {})
                                      .get('labels_attrs', {})
                                      .items()
    }

    # 生成 PDF
    pdf_buffer = BytesIO()
    annotate_image_to_pdf(image, annotations, pdf_buffer, color_map, pdf_title)
    pdf_buffer.seek(0)

    # 返回 PDF
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=download_filename,
        mimetype='application/pdf'
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
