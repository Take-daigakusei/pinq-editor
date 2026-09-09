"""
テスト用サンプルPDF生成スクリプト
異なるサイズ、向き、テキストを含む表紙・本文・裏表紙のPDFを生成します。
"""

import os
import pymupdf
import core_engine

def generate_samples(sample_dir: str):
    os.makedirs(sample_dir, exist_ok=True)
    font_path = core_engine.get_japanese_font_path()

    # 1. 表紙 (A4 縦 595.28 x 841.89 pt)
    doc_cover = pymupdf.open()
    p_cov = doc_cover.new_page(width=595.28, height=841.89)
    p_cov.draw_rect(pymupdf.Rect(30, 30, 565.28, 811.89), color=(0.15, 0.35, 0.75), width=3)
    p_cov.insert_text((80, 240), "CIRCLE MAGAZINE: PIN-Q", fontsize=28, color=(0.1, 0.2, 0.5))
    if font_path:
        p_cov.insert_font(fontname="jp", fontfile=font_path)
        p_cov.insert_text((80, 290), "サークル誌「ぴん球」 2026年秋号", fontname="jp", fontsize=20, color=(0.2, 0.2, 0.2))
        p_cov.insert_text((80, 720), "発行: 卓球サークル ぴん球編集部", fontname="jp", fontsize=14, color=(0.3, 0.3, 0.3))
    cover_path = os.path.join(sample_dir, "01_表紙.pdf")
    doc_cover.save(cover_path)

    # 2. 本文1 (異なるサイズ: 横長 700x500 pt)
    doc_art1 = pymupdf.open()
    p_art1 = doc_art1.new_page(width=700, height=500)
    p_art1.insert_text((50, 60), "Article 1: Summer Training Camp Report", fontsize=18, color=(0.1, 0.1, 0.1))
    if font_path:
        p_art1.insert_font(fontname="jp", fontfile=font_path)
        p_art1.insert_text((50, 100), "合宿での熱戦の記録とメンバーの感想を掲載！", fontname="jp", fontsize=14, color=(0.2, 0.2, 0.2))
    art1_path = os.path.join(sample_dir, "02_本文_夏合宿.pdf")
    doc_art1.save(art1_path)

    # 3. 本文2 (異なるサイズ: B5サイズ 515.91x728.50 pt、黒塗り対象のシークレット情報入り)
    doc_art2 = pymupdf.open()
    p_art2 = doc_art2.new_page(width=515.91, height=728.50)
    p_art2.insert_text((40, 60), "Article 2: Tournament Results & Contact", fontsize=16, color=(0.1, 0.1, 0.1))
    p_art2.insert_text((40, 110), "Doubles Tournament: Champion Team Pin-Q!", fontsize=12, color=(0.2, 0.2, 0.2))
    # 機密情報行（黒塗り対象）
    p_art2.insert_text((40, 160), "Secret Contact Phone: 090-1234-5678 (Private)", fontsize=12, color=(0.8, 0.1, 0.1))
    p_art2.insert_text((40, 210), "Next practice: Next Wednesday 18:00", fontsize=12, color=(0.2, 0.2, 0.2))
    art2_path = os.path.join(sample_dir, "03_本文_大会結果.pdf")
    doc_art2.save(art2_path)

    # 4. 裏表紙 (A4 縦)
    doc_back = pymupdf.open()
    p_back = doc_back.new_page(width=595.28, height=841.89)
    p_back.draw_rect(pymupdf.Rect(40, 40, 555.28, 801.89), color=(0.7, 0.7, 0.7), width=1)
    p_back.insert_text((180, 420), "Pin-Q Editorial Board 2026", fontsize=16, color=(0.4, 0.4, 0.4))
    back_path = os.path.join(sample_dir, "04_裏表紙.pdf")
    doc_back.save(back_path)

    print(f"Generated sample files in: {sample_dir}")
    return cover_path, [art1_path, art2_path], back_path

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    sample_dir = os.path.join(base_dir, "samples")
    generate_samples(sample_dir)
