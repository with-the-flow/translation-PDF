#!/usr/bin/env python3
"""
PDF Translator CLI - 专为 GitHub Actions 设计
用法: python pdf_translator_cli.py <input.pdf> [output_prefix] [--lang zh-cn]

GitHub Actions 示例:
  - name: Translate PDF
    run: python pdf_translator_cli.py "Make Your Own Neural Network.pdf" "translated/neural_network" --lang zh-cn
"""

import sys
import os
import argparse
import time
from pathlib import Path

# 尝试导入依赖，如果失败给出友好提示
try:
    from PyPDF2 import PdfReader
except ImportError:
    print("[ERROR] 缺少 PyPDF2，请安装: pip install PyPDF2")
    sys.exit(1)

try:
    from googletrans import Translator
except ImportError:
    print("[ERROR] 缺少 googletrans，请安装: pip install googletrans==4.0.0-rc1")
    sys.exit(1)

try:
    from fpdf import FPDF
except ImportError:
    print("[ERROR] 缺少 fpdf，请安装: pip install fpdf")
    sys.exit(1)


def log(msg, level="INFO"):
    """带时间戳的日志输出"""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")


def extract_text_from_pdf(pdf_path):
    """从 PDF 提取所有文本"""
    log(f"正在读取 PDF: {pdf_path}")
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    log(f"共 {total_pages} 页")

    full_text = ""
    for i, page in enumerate(reader.pages, 1):
        text = page.extract_text()
        if text:
            full_text += text + "\n\n"
        if i % 10 == 0 or i == total_pages:
            log(f"  已提取 {i}/{total_pages} 页")

    log(f"提取完成，共 {len(full_text)} 字符")
    return full_text


def translate_text(text, target_lang="zh-cn", chunk_size=3000):
    """分段翻译文本，避免 API 限制"""
    translator = Translator()

    # 按 chunk_size 分段
    chunks = []
    current_chunk = ""
    for line in text.split("\n"):
        if len(current_chunk) + len(line) > chunk_size:
            chunks.append(current_chunk)
            current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"
    if current_chunk:
        chunks.append(current_chunk)

    total_chunks = len(chunks)
    log(f"文本已分 {total_chunks} 段进行翻译")

    translated = ""
    for idx, chunk in enumerate(chunks, 1):
        log(f"  正在翻译第 {idx}/{total_chunks} 段...")
        try:
            result = translator.translate(chunk, dest=target_lang)
            translated += result.text + "\n"
            # 简单防限流
            if idx < total_chunks:
                time.sleep(0.5)
        except Exception as e:
            log(f"  第 {idx} 段翻译失败: {e}", "WARN")
            translated += f"[翻译失败段落 {idx}]\n{chunk}\n"
            time.sleep(2)

    return translated


def save_txt(text, output_path):
    """保存为 TXT 文件"""
    txt_path = output_path + ".txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)
    log(f"TXT 已保存: {txt_path}")
    return txt_path


def save_pdf(text, output_path, font_path=None):
    """保存为 PDF 文件"""
    pdf_path = output_path + ".pdf"
    pdf = FPDF()
    pdf.add_page()

    # 尝试加载中文字体
    if font_path and os.path.exists(font_path):
        pdf.add_font("CustomFont", "", font_path)
        pdf.set_font("CustomFont", size=12)
        log(f"使用字体: {font_path}")
    else:
        # 尝试常见系统字体
        system_fonts = [
            "NotoSansSC-Regular.ttf",
            "simhei.ttf",
            "msyh.ttf",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ]
        font_loaded = False
        for font in system_fonts:
            if os.path.exists(font):
                try:
                    pdf.add_font("CustomFont", "", font)
                    pdf.set_font("CustomFont", size=12)
                    log(f"使用系统字体: {font}")
                    font_loaded = True
                    break
                except:
                    continue

        if not font_loaded:
            pdf.set_font("Arial", size=12)
            log("警告: 未找到中文字体，PDF 中文显示可能异常", "WARN")

    # 写入文本（处理换行）
    for line in text.split("\n"):
        # fpdf 的 multi_cell 自动换行
        pdf.multi_cell(0, 10, txt=line)

    pdf.output(pdf_path)
    log(f"PDF 已保存: {pdf_path}")
    return pdf_path


def main():
    parser = argparse.ArgumentParser(description="PDF 翻译器 CLI")
    parser.add_argument("input", help="输入 PDF 文件路径")
    parser.add_argument("output", nargs="?", help="输出文件前缀（不含扩展名）")
    parser.add_argument("--lang", default="zh-cn", help="目标语言 (默认: zh-cn)")
    parser.add_argument("--format", choices=["txt", "pdf", "both"], default="both",
                        help="输出格式: txt, pdf, both (默认: both)")
    parser.add_argument("--font", help="自定义字体文件路径")
    parser.add_argument("--chunk-size", type=int, default=3000,
                        help="翻译分段大小 (默认: 3000)")

    args = parser.parse_args()

    # 检查输入文件
    input_path = Path(args.input)
    if not input_path.exists():
        log(f"文件不存在: {input_path}", "ERROR")
        sys.exit(1)

    # 确定输出路径
    if args.output:
        output_prefix = args.output
    else:
        output_prefix = str(input_path.with_suffix("")) + "_translated"

    # 确保输出目录存在
    output_dir = Path(output_prefix).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    log("=" * 50)
    log(f"输入文件: {input_path}")
    log(f"输出前缀: {output_prefix}")
    log(f"目标语言: {args.lang}")
    log(f"输出格式: {args.format}")
    log("=" * 50)

    # 1. 提取文本
    full_text = extract_text_from_pdf(str(input_path))

    # 2. 翻译
    log("开始翻译...")
    translated_text = translate_text(full_text, target_lang=args.lang, chunk_size=args.chunk_size)

    # 3. 保存结果
    saved_files = []
    if args.format in ("txt", "both"):
        txt_file = save_txt(translated_text, output_prefix)
        saved_files.append(txt_file)

    if args.format in ("pdf", "both"):
        pdf_file = save_pdf(translated_text, output_prefix, font_path=args.font)
        saved_files.append(pdf_file)

    log("=" * 50)
    log("翻译完成！")
    for f in saved_files:
        log(f"  -> {f}")
    log("=" * 50)


if __name__ == "__main__":
    main()
