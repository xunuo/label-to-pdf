#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask 应用：一键拉取 Label Studio 私有图像和标注，生成带注释的 PDF 并下载。

使用前请在环境变量中配置：
  label_studio_host=https://itag.app
  label_studio_api_token=<你的 API Token>

客户端下载时，可通过 ?timezone=<IANA 时区 或 ±HH:MM> 指定时区（如 Asia/Tokyo 或 +09:00），
若未指定，则使用服务器本地时区。
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

# ----------------------------------
# 初始化与配置
# ----------------------------------
# 获取脚本所在目录，以便加载字体文件
BASE_DIR = os.path.dirname(__file__)
FONT_PATH = os.path.join(BASE_DIR, 'DejaVuSans.ttf')
# 注册中文支持字体
pdfmetrics.registerFont(TTFont("DejaVuSans", FONT_PATH))

app = Flask(__name__)

# Label Studio API 设置
LABEL_STUDIO_HOST  = os.getenv('label_studio_host', 'https://itag.app')
LABEL_STUDIO_TOKEN = os.getenv('label_studio_api_token')
if not LABEL_STUDIO_TOKEN:
    raise RuntimeError("请先在环境变量中配置 label_studio_api_token")


# ----------------------------------
# 辅助函数：颜色解析
# ----------------------------------
def parse_html_color(col, alpha=None):
    """
    将 CSS/HTML 颜色字符串或 RGB 列表/元组转换为 reportlab.lib.colors.Color 对象
    支持 HEX (#RRGGBB, #RRGGBBAA)、CSS 名称、0-255 或 0-1 范围值
    alpha 参数可覆盖透明度。
    """
    from reportlab.lib import colors
    # 如果已经是 Color 对象，直接设置透明度
    if isinstance(col, Color):
        return Color(col.red, col.green, col.blue, alpha or col.alpha)
    # 支持列表或元组形式 [r,g,b,(a)]
    if isinstance(col, (tuple, list)):
        vals = list(col)
        if max(vals) > 1:
            vals = [v/255 for v in vals]  # 归一化到 [0,1]
        r, g, b = vals[:3]
        a = vals[3] if len(vals) == 4 else (alpha or 1.0)
        return Color(r, g, b, alpha=a)
    # 字符串模式：HEX 或 CSS 名称
    s = col.strip().lower()
    if s.startswith('#') or all(c in '0123456789abcdef' for c in s):
        hs = s.lstrip('#')
        # 6 位 RGB
        if len(hs) == 6:
            r = int(hs[0:2],16)/255
            g = int(hs[2:4],16)/255
            b = int(hs[4:6],16)/255
            a = alpha or 1.0
        # 8 位 RGBA
        elif len(hs) == 8:
            r = int(hs[0:2],16)/255
            g = int(hs[2:4],16)/255
            b = int(hs[4:6],16)/255
            a = (int(hs[6:8],16)/255) if alpha is None else alpha
        else:
            raise ValueError(f"Invalid hex color: {col}")
        return Color(r, g, b, alpha=a)
    # CSS 名称查找
    try:
        base = getattr(colors, s)
        return parse_html_color(base, alpha=alpha)
    except Exception:
        raise ValueError(f"Unknown color name: {col}")


# ----------------------------------
# 文本转换：长度与方位角
# ----------------------------------
def convert_length_text(text: str) -> str:
    """
    将英尺英寸格式（含分数）转换为米，并生成示例：
      155' 5½" = 47.123 m
    """
    frac_map = { (1,2): '½', (1,3): '⅓', (2,3): '⅔', (1,4): '¼', (3,4): '¾',
                 (1,5): '⅕', (2,5): '⅖', (3,5): '⅗', (4,5): '⅘', (1,6): '⅙',
                 (5,6): '⅚', (1,8): '⅛', (3,8): '⅜', (5,8): '⅝', (7,8): '⅞' }
    getcontext().prec = 10
    FOOT_TO_M  = Decimal('0.3048')
    INCH_TO_M = Decimal('0.0254')

    s = text.strip()
    try:
        # 匹配 feet' inches numerator/denominator" 格式
        m = re.match(r"^(\d+)\s*'\s*(\d+)?(?:\s+(\d+)\s*/\s*(\d+))?\"?$", s)
        if m:
            feet, inches = int(m.group(1)), int(m.group(2) or 0)
            num, den = int(m.group(3) or 0), int(m.group(4) or 0)
        else:
            # 空格分割 fallback
            parts = s.split()
            if not 1 <= len(parts) <= 3 or not all(p.replace('/','').isdigit() for p in parts):
                raise ValueError
            feet = int(parts[0]); inches = int(parts[1]) if len(parts)>=2 else 0
            num, den = (map(int, parts[2].split('/',1)) if '/' in parts[2] else (int(parts[2][:-1]), int(parts[2][-1]))) if len(parts)==3 else (0,0)
        # 计算米
        total_m = Decimal(feet)*FOOT_TO_M + Decimal(inches)*INCH_TO_M
        if num and den:
            total_m += (Decimal(num)/Decimal(den))*INCH_TO_M
        # 格式化输出
        meters_str = f"{total_m:.3f}"
        out = f"{feet}'"
        if inches or (num and den): out += f" {inches}"
        if num and den: out += frac_map.get((num,den), f"{num}/{den}")
        if inches or (num and den): out += '"'
        return f"{out} = {meters_str} m"
    except Exception:
        return text


def convert_bearing_text(text: str) -> str:
    """
    将度 分 秒 转换为格式化字符串并计算十进制度数：
      30° 15′ 20.5″ = 30.256°
    """
    parts = text.strip().split()
    try:
        d,m,s = parts[0], parts[1] if len(parts)>1 else '0', parts[2] if len(parts)>2 else '0'
        dms_str = f"{d}° {m}′ {s}″"
        getcontext().prec = 10
        deg = Decimal(d) + Decimal(m)/Decimal(60) + Decimal(s)/Decimal(3600)
        return f"{dms_str} = {deg:.3f}°"
    except Exception:
        return text


# ----------------------------------
# 加载 Label Studio 标注
# ----------------------------------
def load_annotations(task_json: dict) -> list:
    """
    从 Task JSON 提取矩形/多边形、标签、以及 textarea 文本
    返回列表：[{type, value, text, label}, ...]
    """
    annots, rects, texts, labels = [], {}, {}, {}
    for e in task_json.get('annotations', [{}])[0].get('result', []):
        eid, t = e['id'], e['type']
        if t in ('rectangle', 'polygon'):
            rects[eid] = e['value']
        elif t == 'labels':
            labs = e['value'].get('labels', [])
            labels[eid] = labs[0] if labs else None
        elif t == 'textarea':
            texts[eid] = ''.join(e['value'].get('text', []))
    # 组装最终列表
    for eid, val in rects.items():
        annots.append({'type':'rectangle','value':val,'text':texts.get(eid,''),'label':labels.get(eid)})
    return annots


# ----------------------------------
# 在 PDF 上绘制图像与标注
# ----------------------------------
def annotate_image_to_pdf(
    img: Image.Image,
    annots: list,
    buf: BytesIO,
    label_color_map: dict,
    pdf_title: str
):
    """
    将 PIL Image 与标注绘制到 PDF 中，并设置元数据 title
    """
    # 限制最大尺寸以避免 OOM
    w, h = img.size
    if max(w, h) > 6000:
        ratio = 6000 / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        w, h = img.size

    # 创建 PDF 页面并设置 title 元数据
    c = canvas.Canvas(buf, pagesize=(w, h), pageCompression=True)
    c.setTitle(pdf_title)

    # 绘制底图
    img_bio = BytesIO()
    img.save(img_bio, format='JPEG', quality=80, optimize=True)
    img_bio.seek(0)
    c.drawImage(ImageReader(img_bio), 0, 0, width=w, height=h)

    # 文本样式参数
    font_size = 10
    padding = font_size * 0.2

    # 逐个绘制标注
    for ann in annots:
        if ann['type'] not in ('rectangle', 'polygon'): continue
        val, label, raw_text = ann['value'], ann.get('label'), ann.get('text', '')
        # 根据标签格式化文本
        if label == 'Length':
            icon, text = '↦ ', convert_length_text(raw_text)
        elif label == 'Bearing':
            icon, text = '∠ ', convert_bearing_text(raw_text)
        else:
            icon, text = '', raw_text
        display_text = icon + text

        # 颜色映射
        bg = label_color_map.get(label, 'green')
        box_fill = parse_html_color(bg, alpha=0.15)
        box_stroke = parse_html_color(bg, alpha=0.5)
        text_bg = parse_html_color(bg, alpha=0.4)
        text_stroke = parse_html_color(bg, alpha=0.5)
        font_color = parse_html_color('white', alpha=0.8)

        # 计算位置和尺寸
        xc = val['x']/100 * w
        yc = h - (val['y']/100 * h)
        rw = val['width']/100 * w
        rh = val['height']/100 * h

        # 计算文本背景大小
        tw = stringWidth(display_text, "DejaVuSans", font_size)
        bw = max(tw + 2 * padding, rw)
        bh = font_size + 2 * padding

        # 保存状态并进行旋转/平移
        c.saveState()
        c.translate(xc, yc)
        c.rotate(-val.get('rotation', 0))
        c.translate(rw / 2, 0)

        # 绘制标注框
        c.setFillColor(box_fill)
        c.setStrokeColor(box_stroke)
        c.rect(-rw/2, -rh, rw, rh, fill=1, stroke=1)

        # 绘制文本背景
        c.setFillColor(text_bg)
        c.setStrokeColor(text_stroke)
        c.rect(-bw/2, -rh, bw, bh, fill=1, stroke=1)

        # 绘制文字
        c.setFillColor(font_color)
        c.setFont("DejaVuSans", font_size)
        c.drawCentredString(0, -rh + font_size/2 - padding/2, display_text)
        c.restoreState()

    # 完成页面并保存
    c.showPage()
    c.save()

# ----------------------------------
# 路由定义
# ----------------------------------
@app.route('/')
def index():
    """根路径：简单欢迎信息"""
    return jsonify({"Choo Choo": "Welcome to Xu's Label Studio PDF Exportor 🚅"})

@app.route('/download')
def download():
    """
    下载入口：拉取项目和任务数据，生成注释 PDF 并返回。
    支持 timezone 参数调整 updated_at 时区。
    """
    # 获取必需参数
    project_id = request.args.get('project')
    task_id = request.args.get('task')
    if not project_id or not task_id:
        return jsonify({"error": "请通过 ?project=<id>&task=<id> 指定参数"}), 400

    # 解析并设置目标时区
    tz_param = request.args.get('timezone')
    tz_target = tz.gettz(tz_param) if tz_param else tz.tzlocal()

    headers = {'Authorization': f"Token {LABEL_STUDIO_TOKEN}"}

    # 获取项目元信息
    pj = requests.get(f"{LABEL_STUDIO_HOST}/api/projects/{project_id}", headers=headers)
    pj.raise_for_status()
    pj_json = pj.json()
    title = pj_json.get('title', f'project_{project_id}')

    # 获取任务与 updated_at
    tj = requests.get(f"{LABEL_STUDIO_HOST}/api/tasks/{task_id}", headers=headers)
    tj.raise_for_status()
    task_json = tj.json()
    updated = task_json.get('updated_at')

    # 转换 updated_at 到指定时区
    try:
        dt = parser.isoparse(updated)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz.tzutc())
        dt_local = dt.astimezone(tz_target)
        ts = dt_local.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        ts = updated

    # 构造文件名与 PDF 标题（含时间戳）
    base_name = f"{title}[{task_id} {ts}]"
    filename = f"{base_name}.pdf"

    # 获取 OCR 图像路径，并下载
    ocr_path = task_json.get('data', {}).get('ocr')
    if not ocr_path:
        return jsonify({"error": "Task JSON 中未找到 data['ocr']"}), 500
    ir = requests.get(f"{LABEL_STUDIO_HOST}{ocr_path}", headers=headers)
    ir.raise_for_status()
    img = Image.open(BytesIO(ir.content)).convert('RGB')

    # 加载标注并生成 PDF
    annots = load_annotations(task_json)
    pdf_buf = BytesIO()
    color_map = {lbl: attrs.get('background', '#00ff00')
                 for lbl, attrs in pj_json.get('parsed_label_config', {})
                                    .get('label', {})
                                    .get('labels_attrs', {}).items()}
    annotate_image_to_pdf(img, annots, pdf_buf, color_map, pdf_title=base_name)
    pdf_buf.seek(0)

    # 发送 PDF 文件
    return send_file(
        pdf_buf,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

if __name__ == '__main__':
    # 启动 Flask 应用
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
