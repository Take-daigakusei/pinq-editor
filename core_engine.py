"""
サークル誌「ぴん球」PDF自動編集・結合エンジン
- 表紙・本文・裏表紙の結合
- 各種用紙サイズ（A4, B5, A5等）へのアスペクト比維持リサイズ＆センタリング
- 編集後記ページの美麗な自動組版
- マウス指定矩形による不可逆な完全黒塗り（Redaction / 墨消し）
"""

import os
import datetime
from typing import List, Dict, Tuple, Optional
import pymupdf

# 主要用紙サイズ（ポイント単位: 1pt = 1/72 inch）
PAPER_SIZES = {
    "A4縦 (210 × 297 mm)": (595.28, 841.89),
    "B5縦 (182 × 257 mm)": (515.91, 728.50),
    "A5縦 (148 × 210 mm)": (419.53, 595.28),
    "A4横 (297 × 210 mm)": (841.89, 595.28),
}

DEFAULT_PAPER_SIZE = "A4縦 (210 × 297 mm)"

# Windows標準日本語フォントの検索
def get_japanese_font_path() -> Optional[str]:
    candidates = [
        r"C:\Windows\Fonts\meiryo.ttc",
        r"C:\Windows\Fonts\msgothic.ttc",
        r"C:\Windows\Fonts\YuGothM.ttc",
        r"C:\Windows\Fonts\msmincho.ttc",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def create_afterword_page(
    target_width: float,
    target_height: float,
    title: str = "編集後記",
    body: str = "",
    editor: str = "",
    date_str: Optional[str] = None,
    magazine_name: str = "会内報（ぴん球）",
    issue_name: str = "〜早慶戦号〜",
    publisher: str = "",
    comments: Optional[List[Dict[str, str]]] = None,
) -> pymupdf.Document:
    """見本画像（会内報様式）に完全に準拠した編集後記ページを生成する"""
    doc = pymupdf.open()
    page = doc.new_page(width=target_width, height=target_height)

    font_path = get_japanese_font_path()
    font_name = "jpfont"
    if font_path:
        try:
            page.insert_font(fontname=font_name, fontfile=font_path)
        except Exception:
            font_name = "helv"
    else:
        font_name = "helv"

    # 1. タイトル「編  集  後  記」（上部中央・大きめ）
    title_y = target_height * 0.14
    page.insert_textbox(
        pymupdf.Rect(0, title_y - 25, target_width, title_y + 35),
        "編  集  後  記",
        fontname=font_name,
        fontsize=22,
        color=(0, 0, 0),
        align=pymupdf.TEXT_ALIGN_CENTER,
    )

    # 2. 本文コメントエリア（マージン約 16%）
    margin_x = target_width * 0.16
    content_width = target_width - margin_x * 2
    cur_y = title_y + 60.0

    if not comments:
        comments = [
            {
                "body": "このサークル野球好き多くない？毎回野球の話についていけない総務の悲痛な叫びです。はまそうの文章も野球知ってればもっと面白いんだろうな...🥺　ちなみに早慶戦には行けません。野球に興味がないからではなく日本酒のイベントに行くからです。早稲田が勝ったら教えてくださいね。アテにします。",
                "author": "総務担当 Ａ"
            },
            {
                "body": "ストライクとボールが何度聞いても理解できません。とりあえず打って走ればいいんでしたっけ、野球のルールがなんとなくしか分かりませんが、早慶戦観戦を今年も楽しみにしています。みんな熱中症には気をつけてね。",
                "author": "総務担当 Ｂ"
            }
        ]

    for c in comments:
        c_body = c.get("body", "").strip()
        c_author = c.get("author", "").strip()
        if not c_body and not c_author:
            continue

        rect_text = pymupdf.Rect(margin_x, cur_y, margin_x + content_width, cur_y + 120)
        page.insert_textbox(
            rect_text,
            c_body,
            fontname=font_name,
            fontsize=10.5,
            color=(0.1, 0.1, 0.1),
        )
        cur_y += 70.0

        if c_author:
            page.insert_textbox(
                pymupdf.Rect(margin_x, cur_y - 5, target_width - margin_x, cur_y + 30),
                c_author,
                fontname=font_name,
                fontsize=11,
                color=(0, 0, 0),
                align=pymupdf.TEXT_ALIGN_RIGHT,
            )
            cur_y += 38.0
        else:
            cur_y += 20.0

    # 3. 右下の奥付ボックス（四角い枠線）
    box_w = 165.0
    box_h = 105.0
    box_margin_right = target_width * 0.14
    box_margin_bottom = target_height * 0.14
    box_x = target_width - box_margin_right - box_w
    box_y = target_height - box_margin_bottom - box_h

    # 枠線
    page.draw_rect(
        pymupdf.Rect(box_x, box_y, box_x + box_w, box_y + box_h),
        color=(0, 0, 0),
        width=1.0,
    )

    # 枠内テキスト（上3行は中央揃え、下2行は左揃え）
    if not date_str:
        today = datetime.date.today()
        date_str = f"{today.year}年{today.month}月{today.day}日発行"

    top_text = f"{magazine_name}\n{issue_name}\n{date_str}"
    page.insert_textbox(
        pymupdf.Rect(box_x, box_y + 8, box_x + box_w, box_y + 65),
        top_text,
        fontname=font_name,
        fontsize=9.5,
        color=(0, 0, 0),
        align=pymupdf.TEXT_ALIGN_CENTER,
    )

    bottom_text = f"発行責任者：{publisher or '　　　　'}\n編集責任者：{editor or '　　　　'}"
    page.insert_textbox(
        pymupdf.Rect(box_x + 16, box_y + 65, box_x + box_w - 8, box_y + box_h - 6),
        bottom_text,
        fontname=font_name,
        fontsize=9.5,
        color=(0, 0, 0),
    )

    return doc


def add_normalized_page(
    target_doc: pymupdf.Document,
    src_doc: pymupdf.Document,
    src_page_num: int,
    target_width: float,
    target_height: float,
) -> pymupdf.Page:
    """元ページのアスペクト比を維持し、指定サイズの中央に配置して追加する"""
    src_page = src_doc[src_page_num]
    src_rect = src_page.rect
    src_w = src_rect.width
    src_h = src_rect.height

    scale = min(target_width / src_w, target_height / src_h)
    fit_w = src_w * scale
    fit_h = src_h * scale

    margin_x = (target_width - fit_w) / 2.0
    margin_y = (target_height - fit_h) / 2.0

    target_page = target_doc.new_page(width=target_width, height=target_height)
    target_rect = pymupdf.Rect(
        margin_x, margin_y, margin_x + fit_w, margin_y + fit_h
    )

    target_page.show_pdf_page(target_rect, src_doc, src_page_num)
    return target_page


def build_unified_pdf(
    cover_path: Optional[str],
    body_paths: List[str],
    back_cover_path: Optional[str],
    paper_size_name: str = DEFAULT_PAPER_SIZE,
    include_afterword: bool = False,
    afterword_data: Optional[Dict[str, str]] = None,
) -> Tuple[pymupdf.Document, List[Dict[str, str]]]:
    """
    表紙、本文、編集後記、裏表紙を結合し、用紙サイズを統一したDocumentオブジェクトを作成する。
    各ページの出どころ情報（メタデータ）のリストも返す。
    """
    target_w, target_h = PAPER_SIZES.get(paper_size_name, PAPER_SIZES[DEFAULT_PAPER_SIZE])
    out_doc = pymupdf.open()
    page_metadata: List[Dict[str, str]] = []

    # 1. 表紙
    if cover_path and os.path.isfile(cover_path):
        try:
            doc_c = pymupdf.open(cover_path)
            for i in range(len(doc_c)):
                add_normalized_page(out_doc, doc_c, i, target_w, target_h)
                page_metadata.append({"type": "表紙", "source": os.path.basename(cover_path), "page": i + 1})
        except Exception as e:
            print(f"Error reading cover PDF: {e}")

    # 2. 本文
    for path in body_paths:
        if path and os.path.isfile(path):
            try:
                doc_b = pymupdf.open(path)
                for i in range(len(doc_b)):
                    add_normalized_page(out_doc, doc_b, i, target_w, target_h)
                    page_metadata.append({"type": "本文", "source": os.path.basename(path), "page": i + 1})
            except Exception as e:
                print(f"Error reading body PDF {path}: {e}")

    # 3. 編集後記（裏表紙の直前）
    if include_afterword and afterword_data:
        doc_a = create_afterword_page(
            target_width=target_w,
            target_height=target_h,
            title=afterword_data.get("title", "編集後記"),
            body=afterword_data.get("body", ""),
            editor=afterword_data.get("editor", ""),
            date_str=afterword_data.get("date_str", ""),
        )
        add_normalized_page(out_doc, doc_a, 0, target_w, target_h)
        page_metadata.append({"type": "編集後記", "source": "自動生成", "page": 1})

    # 4. 裏表紙
    if back_cover_path and os.path.isfile(back_cover_path):
        try:
            doc_bc = pymupdf.open(back_cover_path)
            for i in range(len(doc_bc)):
                add_normalized_page(out_doc, doc_bc, i, target_w, target_h)
                page_metadata.append({"type": "裏表紙", "source": os.path.basename(back_cover_path), "page": i + 1})
        except Exception as e:
            print(f"Error reading back cover PDF: {e}")

    return out_doc, page_metadata


def apply_redactions_and_save(
    doc: pymupdf.Document,
    redactions: Dict[int, List[Tuple[float, float, float, float]]],
    output_path: str,
) -> None:
    """
    指定された各ページの矩形座標（x0, y0, x1, y1）に墨消し（Redaction）を施し、
    文字データを完全に抹消した上で保存する。
    """
    for page_idx, rect_list in redactions.items():
        if 0 <= page_idx < len(doc):
            page = doc[page_idx]
            for r in rect_list:
                rect = pymupdf.Rect(r[0], r[1], r[2], r[3])
                # fill=(0, 0, 0) で黒塗り
                page.add_redact_annot(rect, fill=(0, 0, 0))
            page.apply_redactions()

    # ディレクトリ作成
    out_dir = os.path.dirname(output_path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    # 最適化して保存（ゴミデータ除去、圧縮）
    doc.save(output_path, garbage=4, deflate=True)
