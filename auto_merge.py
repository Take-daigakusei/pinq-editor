"""
フォルダ一括処理スクリプト (auto_merge.py)
input/ フォルダ配下の各フォルダにPDFを入れて実行するだけで、
自動で結合・サイズ統一（A4縦）を行い、output/ に完成版PDFを出力します。
"""

import os
import sys
import glob
import datetime
import core_engine

# Windows環境での日本語・絵文字出力対応
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def run_auto_merge():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_dir = os.path.join(base_dir, "input")
    dir_cover = os.path.join(input_dir, "01_表紙")
    dir_body = os.path.join(input_dir, "02_本文")
    dir_back = os.path.join(input_dir, "03_裏表紙")
    output_dir = os.path.join(base_dir, "output")

    os.makedirs(dir_cover, exist_ok=True)
    os.makedirs(dir_body, exist_ok=True)
    os.makedirs(dir_back, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    # 表紙の検出（1つ目）
    covers = sorted(glob.glob(os.path.join(dir_cover, "*.pdf")))
    cover_path = covers[0] if covers else None

    # 本文の検出（ファイル名順）
    body_paths = sorted(glob.glob(os.path.join(dir_body, "*.pdf")))

    # 裏表紙の検出（1つ目）
    backs = sorted(glob.glob(os.path.join(dir_back, "*.pdf")))
    back_cover_path = backs[0] if backs else None

    if not cover_path and not body_paths and not back_cover_path:
        print("[お知らせ] input フォルダ内にPDFファイルが見つかりませんでした。")
        print(f"以下のフォルダに対象のPDFを配置してください:")
        print(f"  - 表紙: {dir_cover}")
        print(f"  - 本文: {dir_body}")
        print(f"  - 裏表紙: {dir_back}")
        return

    print("=== サークル誌「ぴん球」フォルダ一括処理 ===")
    print(f"・表紙: {os.path.basename(cover_path) if cover_path else '（なし）'}")
    print(f"・本文: {len(body_paths)} 件")
    for bp in body_paths:
        print(f"    - {os.path.basename(bp)}")
    print(f"・裏表紙: {os.path.basename(back_cover_path) if back_cover_path else '（なし）'}")

    today_str = datetime.date.today().strftime("%Y%m%d")
    out_filename = f"ぴん球_完成版_{today_str}.pdf"
    out_path = os.path.join(output_dir, out_filename)

    doc, meta = core_engine.build_unified_pdf(
        cover_path=cover_path,
        body_paths=body_paths,
        back_cover_path=back_cover_path,
        paper_size_name=core_engine.DEFAULT_PAPER_SIZE,
        include_afterword=False,
    )

    core_engine.apply_redactions_and_save(doc, {}, out_path)

    print("\n==============================================")
    print(f"✅ 完成版PDFを出力しました！")
    print(f"保存先: {out_path}")
    print(f"総ページ数: {len(doc)} ページ (全ページ A4縦 に統一)")
    print("==============================================")

if __name__ == "__main__":
    run_auto_merge()
