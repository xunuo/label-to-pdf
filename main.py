#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键拉取 Label Studio 私有图像和标注，生成带注释的 PDF 并下载。

使用前请在环境变量中配置：
  label_studio_host
  label_studio_api_token

所有时间为澳大利亚悉尼时间（AEST/AEDT）。
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
LABEL_STUDIO_HOST  = os.getenv('label_studio_host')
LABEL_STUDIO_TOKEN = os.getenv('label_studio_api_token')
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
    if isinstance(color_val, Color):
        return Color(color_val.red, color_val.green, color_val.blue, alpha or color_val.alpha)
    if isinstance(color_val, (tuple, list)):
        vals = [v / 255 if max(color_val) > 1 else v for v in color_val]
        r, g, b = vals[:3]
        a = vals[3] if len(vals) == 4 else (alpha or 1.0)
        return Color(r, g, b, a)
    s = color_val.strip().lower()
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
    try:
        base = getattr(colors, s)
        return parse_html_color(base, alpha=alpha)
    except Exception:
        raise ValueError(f"Unknown color name: {color_val}")


import re
from decimal import Decimal, getcontext

def convert_length_text(text: str) -> dict[str, str]:
    """
    将英尺英寸格式的文本转换为米，并格式化输出。
    支持：
      - 含引号的格式，如 155' 5 1/4", 155'5"
      - 纯数字 "50"（视作 50 英尺）
      - 简写三段 "159 0 12"（12 表示 1/2）
      - 只有英寸或分数，如 5 1/2", 1/2"
    输出示例： 5' 0" ↦ 1.524 m
    解析失败则返回原文本。
    """
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

    s = text.strip()
    parts = s.replace('"','').split()
    show_inches = False
    feet = inches = num = den = 0

    # ——— 1. 纯数字/三段简写 ———
    if 1 <= len(parts) <= 3 and all(p.isdigit() for p in parts):
        feet = int(parts[0])
        inches = int(parts[1]) if len(parts) >= 2 else 0
        show_inches = len(parts) >= 2
        if len(parts) == 3:
            code = parts[2]
            if len(code) >= 2 and code != '0':
                try:
                    num, den = int(code[:-1]), int(code[-1])
                except ValueError:
                    return text  # 不合法，原样返回
    else:
        # ——— 2. 标准格式 ———
        m = re.match(
            r"""^\s*
                (?:(\d+)\s*')?            # group1: feet
                \s*(\d+)?                 # group2: inches integer
                (?:\s+(\d+)\s*/\s*(\d+))? # group3/4: fraction
                \s*"?\s*$""",
            s, re.VERBOSE
        )
        if m:
            feet   = int(m.group(1)) if m.group(1) else 0
            inches = int(m.group(2)) if m.group(2) else 0
            num    = int(m.group(3)) if m.group(3) else 0
            den    = int(m.group(4)) if m.group(4) else 0
            show_inches = m.group(2) is not None
        else:
            # ——— 3. 只含分数，如 "1/2" 或 ' 3 / 4 "' ———
            m2 = re.match(
                r"""^\s*(\d+)\s*/\s*(\d+)\s*"?\s*$""",
                s
            )
            if m2:
                num, den = int(m2.group(1)), int(m2.group(2))
                feet = inches = 0
                show_inches = True  # 显式保留
            else:
                return text  # 无法解析，返回原文本

    # ——— 统一计算米值 ———
    total_m = (
        Decimal(feet) * FOOT_TO_M +
        Decimal(inches) * INCH_TO_M +
        (Decimal(num) / Decimal(den) * INCH_TO_M if den else Decimal(0))
    )
    meters_str = f"{total_m:.3f}"

    # ——— 构造英寸文本 ———
    frac_txt = frac_map.get((num, den), f"{num}/{den}") if den else ''
    if inches == 0 and frac_txt:
        inch_txt = f'{frac_txt}"'
    elif frac_txt:
        inch_txt = f'{inches}{frac_txt}"'
    elif inches or show_inches:
        inch_txt = f'{inches}"'
    else:
        inch_txt = ''

    # ——— 构造最终输出 ———
    if feet and inch_txt:
        feet_inch_text = f"{feet}' {inch_txt}"
    elif feet:
        feet_inch_text = f"{feet}'"
    else:
        feet_inch_text = inch_txt

    return {
        "feet_inch_text": feet_inch_text,
        "meters_text": meters_str
    }



def convert_bearing_text(text: str) -> dict[str, str]:
    """
    将度 分 秒 转换为十进制度数并格式化输出，
    并额外返回 AutoCAD PLINE 需要的正向角度 cad_deg_text
    以及反向角度 rev_cad_deg_text（cad_deg+180 % 360）。
    返回 {
      "dms_text": "DD° MM′ SS″",
      "deg_text": "...",
      "cad_deg_text": "...",
      "rev_cad_deg_text": "..."
    }
    """
    parts = text.strip().split()
    try:
        d = Decimal(parts[0]) if parts and parts[0] else Decimal(0)
        m = Decimal(parts[1]) if len(parts) > 1 else Decimal(0)
        s = Decimal(parts[2]) if len(parts) > 2 else Decimal(0)
        getcontext().prec = 10

        # 1) 原始十进制度数
        deg = d + m/Decimal(60) + s/Decimal(3600)

        # 2) 归一化到 [0,360)
        deg_norm = deg % Decimal(360)

        # 3) 正向 CAD 角度（0°=东，逆时针为正）
        cad_deg = (Decimal(90) - deg_norm) % Decimal(360)

        # 4) 反向 CAD 角度：在正向角度上加 180°（并归一化）
        rev_cad_deg = (cad_deg + Decimal(180)) % Decimal(360)

        # 5) 构造 DMS 文本
        def pad(v):
            vs = str(int(v))
            return vs.zfill(2)
        dms_str = f"{pad(d)}° {pad(m)}′ {pad(s)}″"

        return {
            "dms_text": dms_str,
            "deg_text":       f"{deg:.3f}",
            "cad_deg_text":   f"{cad_deg:.3f}",
            "rev_cad_deg_text": f"{rev_cad_deg:.3f}"
        }
    except Exception:
        # 出错时也返回四个字段，保证调用处不报 KeyError
        return {
            "dms_text": text,
            "deg_text": "",
            "cad_deg_text": "",
            "rev_cad_deg_text": ""
        }


def load_annotations(task_json: dict) -> tuple[list, list]:
    """
    从 Task JSON 提取标注与关系。
    返回 (annotations, relations)。
    """
    annotations, relations = [], []
    rect_map, text_map, label_map = {}, {}, {}
    results = task_json.get('annotations', [{}])[0].get('result', [])
    for item in results:
        if item.get('type') == 'relation':
            relations.append({'from_id': item['from_id'], 'to_id': item['to_id']})
            continue
        if 'id' not in item:
            continue
        eid, t = item['id'], item['type']
        if t in ('rectangle', 'polygon'):
            rect_map[eid] = item['value']
        elif t == 'labels':
            labs = item['value'].get('labels', [])
            if labs: label_map[eid] = labs[0]
        elif t == 'textarea':
            text_map[eid] = ''.join(item['value'].get('text', []))
    for eid, val in rect_map.items():
        annotations.append({'id': eid, 'type': 'rectangle', 'value': val,
                            'text': text_map.get(eid, ''), 'label': label_map.get(eid)})
    return annotations, relations


def annotate_image_to_pdf(
    image: Image.Image,
    annotations: list,
    relations: list,
    output_buffer: BytesIO,
    color_map: dict,
    pdf_title: str
):
    # 获取图像原始宽高
    image_width, image_height = image.size

    # 限制最大图像尺寸，防止太大导致PDF异常
    max_dimension = 6000
    if max(image_width, image_height) > max_dimension:
        resize_ratio = max_dimension / max(image_width, image_height)
        image = image.resize(
            (int(image_width * resize_ratio), int(image_height * resize_ratio)), 
            Image.LANCZOS
        )
        image_width, image_height = image.size

    # 创建 PDF 画布
    pdf_canvas = canvas.Canvas(output_buffer, pagesize=(image_width, image_height), pageCompression=True)
    pdf_canvas.setTitle(pdf_title)

    # 将原始图像绘制到PDF底层
    image_buffer = BytesIO()
    image.save(image_buffer, format='JPEG', quality=80, optimize=True)
    image_buffer.seek(0)
    pdf_canvas.drawImage(ImageReader(image_buffer), 0, 0, width=image_width, height=image_height)



    # 构建 ID -> 关联ID 的字典（如长度和方向的配对关系）
    annotation_relation_map = {relation['from_id']: relation['to_id'] for relation in relations}

    for annotation in annotations:
        # 只处理矩形和多边形类型的标注
        if annotation['type'] not in ('rectangle', 'polygon'):
            continue

        raw_text = annotation['text']
        label = annotation['label']

        # 根据类型转换文本，如长度单位或角度
        if label == 'Length':
            display_text = convert_length_text(raw_text)['meters_text']
        elif label == 'Bearing':
            display_text = convert_bearing_text(raw_text)['deg_text']
        else:
            display_text = raw_text

        # 如果是长度且有关联的方向信息，拼接方向信息
        if label == 'Length' and annotation['id'] in annotation_relation_map:
            bearing_id = annotation_relation_map[annotation['id']]
            bearing_annotation = next(
                (a for a in annotations if a['id'] == bearing_id and a['label'] == 'Bearing'),
                None
            )
            if bearing_annotation:
                bearing_text = convert_bearing_text(bearing_annotation['text'])['deg_text']
                display_text = f"@{display_text}<{bearing_text}"

        # 获取颜色设置（含透明度）
        base_color = color_map.get(label, '#00ff00')
        fill_color = parse_html_color(base_color, alpha=0.15)
        border_color = parse_html_color(base_color, alpha=0.5)
        text_bg_color = parse_html_color(base_color, alpha=0.6)
        text_border_color = parse_html_color(base_color, alpha=0.5)
        font_color = parse_html_color('white', alpha=0.8)

        # 解析位置和大小百分比为实际坐标
        value = annotation['value']
        center_x = value['x'] / 100 * image_width
        center_y = image_height - (value['y'] / 100 * image_height)
        box_width = value['width'] / 100 * image_width
        box_height = value['height'] / 100 * image_height
        rotation = -value.get('rotation', 0)  # 注意是负值

        # 保存当前画布状态以便恢复
        pdf_canvas.saveState()
        pdf_canvas.translate(center_x, center_y)
        pdf_canvas.rotate(rotation)
        pdf_canvas.translate(box_width / 2, 0)

        # 绘制主标注矩形区域（透明背景）
        pdf_canvas.setFillColor(fill_color)
        pdf_canvas.setStrokeColor(border_color)
        pdf_canvas.rect(-box_width / 2, -box_height, box_width, box_height, fill=1, stroke=1)


        if label == 'Length' :
            
            # 设置字体大小和文字边距
            font_size = 12
            padding = 1

            # 第二层文字 识别原始文字
            # 计算文本框尺寸
            text_width = stringWidth(convert_length_text(raw_text)['feet_inch_text'], 'DejaVuSans', font_size)
            text_height = font_size
            box_total_width = max(text_width + 2 * padding, box_width)
            box_total_height = text_height + 2 * padding
            # text_box_y_offset = 0
            text_box_y_offset = -box_total_height

            pdf_canvas.setFillColor(parse_html_color(base_color, alpha=0.3))
            pdf_canvas.setStrokeColor(parse_html_color(base_color, alpha=0.4))
            pdf_canvas.rect(-box_total_width / 2, -box_height, box_width, box_height, fill=1, stroke=0)
            # pdf_canvas.rect(-box_total_width/2 + text_width/2, -box_total_height + padding, text_width, text_height, fill=1, stroke=1)
            pdf_canvas.setFillColor(parse_html_color('white', alpha=0.8))
            pdf_canvas.setFont('DejaVuSans', font_size)
            pdf_canvas.drawCentredString(0, text_box_y_offset, convert_length_text(raw_text)['feet_inch_text'])

            # 第三层文字 米换算值
            # 计算文本框尺寸
            text_width = stringWidth(display_text, 'DejaVuSans', font_size)
            text_height = font_size
            box_total_width = max(text_width + 2 * padding, box_width)
            box_total_height = text_height + 2 * padding
            # text_box_y_offset = -box_height - padding
            text_box_y_offset = -box_height
            if box_height < 28 :
                text_box_y_offset = -box_height - box_total_height

            pdf_canvas.setFillColor(parse_html_color(base_color, alpha=0.4))
            pdf_canvas.setStrokeColor(text_border_color)
            pdf_canvas.rect(-box_total_width / 2, text_box_y_offset, box_total_width, box_total_height, fill=1, stroke=1)
            pdf_canvas.setFillColor(parse_html_color('white', alpha=0.8))
            pdf_canvas.setFont('DejaVuSans', font_size)
            pdf_canvas.drawCentredString(0, text_box_y_offset + padding*3, display_text)

        else:
            
            font_size=32
            text_width = stringWidth(display_text, 'DejaVuSans', font_size)
            box_total_width = text_width + 5 * padding
            text_height = font_size
            box_total_height = text_height + 2 * padding
            text_box_y_offset = -box_height / 2 + box_total_height
            
            # http://127.0.0.1:5001/download?tab=21&task=15&project=27

            # 第一层文字背景框和文字(居中的)
            pdf_canvas.setFillColor(parse_html_color(base_color, alpha=0.5))
            pdf_canvas.setStrokeColor(parse_html_color(base_color, alpha=0.5))
            pdf_canvas.rect(-box_total_width / 2, text_box_y_offset, box_total_width, box_total_height, fill=1, stroke=0)
            pdf_canvas.setFillColor(parse_html_color('white', alpha=0.9))
            pdf_canvas.setFont('DejaVuSans', font_size)
            pdf_canvas.drawCentredString(0, text_box_y_offset + padding*6, display_text)

        

        # 恢复画布状态（防止旋转影响下一个标注）
        pdf_canvas.restoreState()

    # 保存 PDF 页面
    pdf_canvas.showPage()
    pdf_canvas.save()

@app.route('/')
def index():
    return jsonify({"message": "Welcome to Xu's Label Studio PDF Exportor 🚅"})

@app.route('/download')
def download():
    project_id = request.args.get('project'); task_id = request.args.get('task')
    if not project_id or not task_id:
        return jsonify({"error": "请通过 ?project=<id>&task=<id> 指定参数"}), 400
    headers = {'Authorization': f"Token {LABEL_STUDIO_TOKEN}"}
    proj = requests.get(f"{LABEL_STUDIO_HOST}/api/projects/{project_id}", headers=headers)
    proj.raise_for_status(); pd = proj.json(); title = pd.get('title', f'project_{project_id}')
    task = requests.get(f"{LABEL_STUDIO_HOST}/api/tasks/{task_id}", headers=headers)
    task.raise_for_status(); td = task.json()
    # 时间转换
    updated = td.get('updated_at')
    try:
        dt = parser.isoparse(updated);
        if dt.tzinfo is None: dt = dt.replace(tzinfo=tz.tzutc())
        ts = dt.astimezone(SYDNEY_TZ).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        ts = updated
    pdf_title = f"{title} / Task ID: {task_id} / Last Modified (Sydney Time): {ts}"
    fname = f"{title}[task-{task_id}].pdf"
    ocr = td.get('data',{}).get('ocr')
    if not ocr:
        return jsonify({"error": "Task JSON 中未找到 data['ocr']"}), 500
    img = requests.get(f"{LABEL_STUDIO_HOST}{ocr}", headers=headers)
    img.raise_for_status(); image = Image.open(BytesIO(img.content)).convert('RGB')
    annotations, relations = load_annotations(td)
    color_map = {lbl: attrs.get('background', '#00ff00')
                 for lbl, attrs in pd.get('parsed_label_config', {}).get('label', {}).get('labels_attrs', {}).items()}
    buf = BytesIO()
    annotate_image_to_pdf(image, annotations, relations, buf, color_map, pdf_title)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=fname, mimetype='application/pdf')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)



## Debug URLs
# http://127.0.0.1:5001/download?tab=21&task=14&project=27
# http://127.0.0.1:5001/download?task=7&project=21
# http://127.0.0.1:5001/download?tab=18&task=9&project=22


# http://127.0.0.1:5001/download?tab=21&task=15&project=27
