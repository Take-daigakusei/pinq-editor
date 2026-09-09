"""
統合自動検証スクリプト
結合・用紙サイズ統一・黒塗り・編集後記が正しく機能するかを自動テストします。
"""

import os
import sys
import pymupdf
import core_engine

# Windows環境での日本語・絵文字出力対応
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def run_verification():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    sample_dir = os.path.join(base_dir, "samples")
    cover_path = os.path.join(sample_dir, "01_表紙.pdf")
    art1_path = os.path.join(sample_dir, "02_本文_夏合宿.pdf")
    art2_path = os.path.join(sample_dir, "03_本文_大会結果.pdf")
    back_path = os.path.join(sample_dir, "04_裏表紙.pdf")

    afterword_data = {
        "title": "編集後記（検証号）",
        "body": "サークル誌「ぴん球」制作に関わった皆様、お疲れ様でした！",
        "editor": "ぴん球編集部",
        "date_str": "2026年9月9日",
    }

    # 1. 結合＆サイズ統一
    doc, meta = core_engine.build_unified_pdf(
        cover_path=cover_path,
        body_paths=[art1_path, art2_path],
        back_cover_path=back_path,
        paper_size_name="A4縦 (210 × 297 mm)",
        include_afterword=True,
        afterword_data=afterword_data,
    )

    print(f"[TEST 1] 総ページ数検証: 期待値=5, 実際={len(doc)}")
    assert len(doc) == 5, f"Expected 5 pages, got {len(doc)}"

    expected_types = ["表紙", "本文", "本文", "編集後記", "裏表紙"]
    actual_types = [m["type"] for m in meta]
    print(f"[TEST 2] ページ構成検証: {actual_types}")
    assert actual_types == expected_types, f"Page types mismatch: {actual_types}"

    # 2. 全ページの用紙サイズがA4（595.28 x 841.89）か検証
    target_w, target_h = core_engine.PAPER_SIZES["A4縦 (210 × 297 mm)"]
    for i, p in enumerate(doc):
        w = round(p.rect.width, 2)
        h = round(p.rect.height, 2)
        print(f"[TEST 3-{i+1}] ページ {i+1} サイズ: {w} x {h} pt (A4={target_w} x {target_h})")
        assert abs(w - target_w) < 0.1 and abs(h - target_h) < 0.1, f"Page {i+1} size mismatch: {w}x{h}"

    # 3. 黒塗りの適用
    # ページ2（インデックス2: 3ページ目、本文_大会結果）にある「090-1234-5678」を検索
    p2 = doc[2]
    rects = p2.search_for("090-1234-5678")
    print(f"[TEST 4] 機密文字列 '090-1234-5678' の検出矩形: {rects}")
    assert len(rects) > 0, "Could not find target secret text to redact"

    target_rect = rects[0]
    # 少し広めにマージンをとって黒塗り矩形を定義（GUIでマウスドラッグした想定）
    redact_box = (target_rect.x0 - 5, target_rect.y0 - 3, target_rect.x1 + 5, target_rect.y1 + 3)
    redactions = {2: [redact_box]}

    output_path = os.path.join(base_dir, "output", "ぴん球_テスト完成版.pdf")
    core_engine.apply_redactions_and_save(doc, redactions, output_path)
    print(f"[TEST 5] 完成版PDFを保存しました: {output_path}")

    # 4. 出力ファイルの安全検証（不可逆な墨消しが確認できるか）
    chk_doc = pymupdf.open(output_path)
    chk_p2_text = chk_doc[2].get_text()
    print(f"[TEST 6] 墨消し後ページ2のテキスト:\n---\n{chk_p2_text.strip()}\n---")
    assert "090-1234-5678" not in chk_p2_text, "Secret text was NOT redacted completely!"
    assert "Doubles Tournament" in chk_p2_text, "Other text should remain intact!"
    print("✅ 機密情報（電話番号）の完全消去と他テキストの維持を確認！")

    # 5. 編集後記ページのテキスト検証
    chk_p3_text = chk_doc[3].get_text()
    print(f"[TEST 7] 編集後記ページのテキスト:\n---\n{chk_p3_text.strip()}\n---")
    assert "編集後記" in chk_p3_text, "Afterword title not found!"
    assert "ぴん球編集部" in chk_p3_text, "Editor not found!"
    print("✅ 編集後記の自動挿入・テキスト確認OK！")

    print("\n🎉 すべての自動テストが正常にパスしました！")

if __name__ == "__main__":
    run_verification()
