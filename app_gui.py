"""
サークル誌「ぴん球」PDFエディタ
GUI アプリケーション (Tkinter + PyMuPDF + Pillow)
- 表紙・本文・編集後記・裏表紙の結合
- 用紙サイズ統一（A4/B5等へのリサイズ＆余白調整）
- プレビュー画面上でのマウスドラッグによる黒塗り（墨消し）
- 編集後記の自動生成
- ワンクリックでの完成版PDF発行
"""

import os
import sys
import datetime
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import List, Dict, Tuple, Optional
from PIL import Image, ImageTk
import pymupdf

import core_engine


class PingQEditorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("サークル誌「ぴん球」PDFエディタ - 結合・サイズ統一・校正")
        self.root.geometry("1240 x 860")
        self.root.minsize(1000, 700)

        # アプリ内状態
        self.cover_path: Optional[str] = None
        self.body_paths: List[str] = []
        self.back_cover_path: Optional[str] = None
        
        # 統合ドキュメント＆メタデータ
        self.current_doc: Optional[pymupdf.Document] = None
        self.current_metadata: List[Dict[str, str]] = []
        self.current_page_idx: int = 0
        
        # ページごとの黒塗り領域: {page_idx: [(x0, y0, x1, y1), ...]} (PDFポイント座標系)
        self.redactions: Dict[int, List[Tuple[float, float, float, float]]] = {}
        
        # プレビュー描画関連
        self.preview_image: Optional[Image.Image] = None
        self.preview_photo: Optional[ImageTk.PhotoImage] = None
        self.canvas_scale_x: float = 1.0
        self.canvas_scale_y: float = 1.0
        self.canvas_offset_x: float = 0.0
        self.canvas_offset_y: float = 0.0
        self.drag_start: Optional[Tuple[int, int]] = None
        self.drag_rect_id: Optional[int] = None

        self._setup_style()
        self._build_ui()

    def _setup_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # 色定義
        self.COLOR_BG = "#F4F5F7"
        self.COLOR_PANEL = "#FFFFFF"
        self.COLOR_PRIMARY = "#2563EB"     # 鮮やかな青
        self.COLOR_PRIMARY_HOVER = "#1D4ED8"
        self.COLOR_SUCCESS = "#059669"     # 発行用グリーン
        self.COLOR_TEXT = "#1F2937"
        self.COLOR_TEXT_MUTED = "#6B7280"
        self.COLOR_BORDER = "#E5E7EB"

        self.root.configure(bg=self.COLOR_BG)

    def _build_ui(self):
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # 左パネル: 設定＆操作 (幅 480固定寄り)
        left_container = ttk.Frame(main_paned, width=480)
        main_paned.add(left_container, weight=0)

        # 右パネル: プレビュー＆校正 (伸縮)
        right_container = ttk.Frame(main_paned)
        main_paned.add(right_container, weight=1)

        self._build_left_panel(left_container)
        self._build_right_panel(right_container)

    # -------------------------------------------------------------
    # 左パネル: ドキュメント構成＆設定
    # -------------------------------------------------------------
    def _build_left_panel(self, parent: ttk.Frame):
        # スクロール可能なCanvas
        canvas = tk.Canvas(parent, bg=self.COLOR_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        def on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", on_canvas_configure)

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # マウスホイールでスクロール
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        pad_x = 12
        pad_y = 6

        # --- タイトルヘッダー ---
        header_frame = tk.Frame(scrollable_frame, bg="#1E293B", padx=14, pady=10)
        header_frame.pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            header_frame,
            text="🏓 ぴん球 PDF編集・発行",
            font=("Segoe UI", 13, "bold"),
            fg="#FFFFFF",
            bg="#1E293B",
        ).pack(anchor="w")
        tk.Label(
            header_frame,
            text="結合・用紙サイズ統一・黒塗り校正・編集後記作成",
            font=("Segoe UI", 9),
            fg="#94A3B8",
            bg="#1E293B",
        ).pack(anchor="w")

        # --- 1. 表紙 ---
        group_cover = ttk.LabelFrame(scrollable_frame, text=" 1. 表紙 PDF ")
        group_cover.pack(fill=tk.X, padx=pad_x, pady=pad_y)

        cover_btn_frame = ttk.Frame(group_cover)
        cover_btn_frame.pack(fill=tk.X, padx=8, pady=6)
        ttk.Button(cover_btn_frame, text="📁 表紙を選択...", command=self._select_cover).pack(side=tk.LEFT)
        ttk.Button(cover_btn_frame, text="クリア", command=self._clear_cover).pack(side=tk.LEFT, padx=6)

        self.lbl_cover = tk.Label(
            group_cover,
            text="（未選択）",
            fg=self.COLOR_TEXT_MUTED,
            bg=self.COLOR_BG,
            anchor="w",
            padx=8,
            pady=4,
            relief=tk.RIDGE,
        )
        self.lbl_cover.pack(fill=tk.X, padx=8, pady=(0, 8))

        # --- 2. 本文 ---
        group_body = ttk.LabelFrame(scrollable_frame, text=" 2. 本文 PDF（順番通りに配置） ")
        group_body.pack(fill=tk.X, padx=pad_x, pady=pad_y)

        body_btn_frame = ttk.Frame(group_body)
        body_btn_frame.pack(fill=tk.X, padx=8, pady=6)
        ttk.Button(body_btn_frame, text="＋ PDFを追加...", command=self._add_body_files).pack(side=tk.LEFT)
        ttk.Button(body_btn_frame, text="▲ 上へ", command=self._move_body_up).pack(side=tk.LEFT, padx=4)
        ttk.Button(body_btn_frame, text="▼ 下へ", command=self._move_body_down).pack(side=tk.LEFT)
        ttk.Button(body_btn_frame, text="✕ 削除", command=self._remove_selected_body).pack(side=tk.LEFT, padx=4)
        ttk.Button(body_btn_frame, text="全クリア", command=self._clear_all_body).pack(side=tk.RIGHT)

        # リストボックス
        list_container = ttk.Frame(group_body)
        list_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.body_listbox = tk.Listbox(
            list_container,
            height=6,
            selectmode=tk.SINGLE,
            font=("Segoe UI", 9),
            activestyle="none",
        )
        body_sb = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.body_listbox.yview)
        self.body_listbox.configure(yscrollcommand=body_sb.set)
        self.body_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        body_sb.pack(side=tk.RIGHT, fill=tk.Y)

        # --- 3. 編集後記 ---
        group_afterword = ttk.LabelFrame(scrollable_frame, text=" 3. 編集後記（裏表紙の直前に自動挿入） ")
        group_afterword.pack(fill=tk.X, padx=pad_x, pady=pad_y)

        self.var_use_afterword = tk.BooleanVar(value=True)
        chk_afterword = ttk.Checkbutton(
            group_afterword,
            text="編集後記ページを作成して挿入する",
            variable=self.var_use_afterword,
            command=self._toggle_afterword_inputs,
        )
        chk_afterword.pack(anchor="w", padx=8, pady=4)

        self.frame_afterword_inputs = ttk.Frame(group_afterword)
        self.frame_afterword_inputs.pack(fill=tk.X, padx=8, pady=(0, 8))

        # タイトル
        lbl_f = ttk.Frame(self.frame_afterword_inputs)
        lbl_f.pack(fill=tk.X, pady=2)
        ttk.Label(lbl_f, text="タイトル:", width=8).pack(side=tk.LEFT)
        self.entry_afterword_title = ttk.Entry(lbl_f)
        self.entry_afterword_title.insert(0, "編 集 後 記")
        self.entry_afterword_title.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 本文
        ttk.Label(self.frame_afterword_inputs, text="本文:").pack(anchor="w", pady=(4, 2))
        self.text_afterword_body = tk.Text(
            self.frame_afterword_inputs,
            height=5,
            font=("Segoe UI", 9),
            wrap=tk.WORD,
        )
        self.text_afterword_body.insert(
            "1.0",
            "サークル誌「ぴん球」をお読みいただきありがとうございます！\n"
            "各担当者からの力作が集まり、素晴らしい1冊になりました。\n"
            "次号もぜひお楽しみに！",
        )
        self.text_afterword_body.pack(fill=tk.X, pady=2)

        # 執筆者・発行日
        row_info = ttk.Frame(self.frame_afterword_inputs)
        row_info.pack(fill=tk.X, pady=2)
        ttk.Label(row_info, text="編集者:").pack(side=tk.LEFT)
        self.entry_afterword_editor = ttk.Entry(row_info, width=18)
        self.entry_afterword_editor.insert(0, "サークル「ぴん球」編集部")
        self.entry_afterword_editor.pack(side=tk.LEFT, padx=(2, 8))

        ttk.Label(row_info, text="発行日:").pack(side=tk.LEFT)
        self.entry_afterword_date = ttk.Entry(row_info, width=14)
        today = datetime.date.today()
        self.entry_afterword_date.insert(0, today.strftime("%Y年%m月%d日"))
        self.entry_afterword_date.pack(side=tk.LEFT, padx=2)

        # --- 4. 裏表紙 ---
        group_back_cover = ttk.LabelFrame(scrollable_frame, text=" 4. 裏表紙 PDF ")
        group_back_cover.pack(fill=tk.X, padx=pad_x, pady=pad_y)

        back_btn_frame = ttk.Frame(group_back_cover)
        back_btn_frame.pack(fill=tk.X, padx=8, pady=6)
        ttk.Button(back_btn_frame, text="📁 裏表紙を選択...", command=self._select_back_cover).pack(side=tk.LEFT)
        ttk.Button(back_btn_frame, text="クリア", command=self._clear_back_cover).pack(side=tk.LEFT, padx=6)

        self.lbl_back_cover = tk.Label(
            group_back_cover,
            text="（未選択）",
            fg=self.COLOR_TEXT_MUTED,
            bg=self.COLOR_BG,
            anchor="w",
            padx=8,
            pady=4,
            relief=tk.RIDGE,
        )
        self.lbl_back_cover.pack(fill=tk.X, padx=8, pady=(0, 8))

        # --- 5. 用紙サイズ設定 ---
        group_setting = ttk.LabelFrame(scrollable_frame, text=" 5. 統一用紙サイズ ")
        group_setting.pack(fill=tk.X, padx=pad_x, pady=pad_y)

        setting_inner = ttk.Frame(group_setting)
        setting_inner.pack(fill=tk.X, padx=8, pady=6)
        ttk.Label(setting_inner, text="サイズ:").pack(side=tk.LEFT)
        self.combo_paper_size = ttk.Combobox(
            setting_inner,
            values=list(core_engine.PAPER_SIZES.keys()),
            state="readonly",
            width=26,
        )
        self.combo_paper_size.set(core_engine.DEFAULT_PAPER_SIZE)
        self.combo_paper_size.pack(side=tk.LEFT, padx=6)

        # --- アクション実行エリア ---
        action_frame = tk.Frame(scrollable_frame, bg=self.COLOR_BG, padx=pad_x, pady=12)
        action_frame.pack(fill=tk.X)

        btn_refresh = tk.Button(
            action_frame,
            text="🔄 プレビューを更新",
            font=("Segoe UI", 10, "bold"),
            bg="#E2E8F0",
            fg="#1E293B",
            activebackground="#CBD5E1",
            relief=tk.RAISED,
            pady=6,
            command=self.refresh_preview,
        )
        btn_refresh.pack(fill=tk.X, pady=(0, 8))

        btn_export = tk.Button(
            action_frame,
            text="🚀 完成版PDFを発行して保存",
            font=("Segoe UI", 12, "bold"),
            bg=self.COLOR_SUCCESS,
            fg="#FFFFFF",
            activebackground="#047857",
            activeforeground="#FFFFFF",
            relief=tk.RAISED,
            pady=10,
            command=self.export_pdf,
        )
        btn_export.pack(fill=tk.X)

    def _toggle_afterword_inputs(self):
        state = tk.NORMAL if self.var_use_afterword.get() else tk.DISABLED
        self.entry_afterword_title.configure(state=state)
        self.text_afterword_body.configure(state=state)
        self.entry_afterword_editor.configure(state=state)
        self.entry_afterword_date.configure(state=state)

    # -------------------------------------------------------------
    # 右パネル: プレビュー＆黒塗り校正
    # -------------------------------------------------------------
    def _build_right_panel(self, parent: ttk.Frame):
        # ツールバー
        toolbar = tk.Frame(parent, bg="#E2E8F0", padx=10, pady=8)
        toolbar.pack(fill=tk.X)

        # ページ送り
        btn_prev = ttk.Button(toolbar, text="◀ 前のページ", command=self._prev_page)
        btn_prev.pack(side=tk.LEFT)

        self.lbl_page_info = tk.Label(
            toolbar,
            text="ページ: 0 / 0",
            font=("Segoe UI", 10, "bold"),
            bg="#E2E8F0",
            padx=12,
        )
        self.lbl_page_info.pack(side=tk.LEFT)

        btn_next = ttk.Button(toolbar, text="次のページ ▶", command=self._next_page)
        btn_next.pack(side=tk.LEFT)

        # セパレータ
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=12)

        # 黒塗り管理
        btn_undo_redact = ttk.Button(toolbar, text="⤺ 直前の黒塗りを取消", command=self._undo_redaction)
        btn_undo_redact.pack(side=tk.LEFT)

        btn_clear_redact = ttk.Button(toolbar, text="🗑 このページの黒塗りを全消去", command=self._clear_current_page_redactions)
        btn_clear_redact.pack(side=tk.LEFT, padx=6)

        self.lbl_redact_count = tk.Label(
            toolbar,
            text="黒塗り: 0 箇所",
            font=("Segoe UI", 9),
            fg="#B91C1C",
            bg="#E2E8F0",
            padx=6,
        )
        self.lbl_redact_count.pack(side=tk.LEFT)

        # ヒントバー
        hint_bar = tk.Frame(parent, bg="#FEF3C7", padx=10, pady=4)
        hint_bar.pack(fill=tk.X)
        tk.Label(
            hint_bar,
            text="💡 マウスをドラッグして囲むと、その部分を「黒塗り（墨消し）」できます（出力時に文字データも完全に抹消されます）",
            font=("Segoe UI", 9),
            fg="#92400E",
            bg="#FEF3C7",
        ).pack(side=tk.LEFT)

        # ページ元情報バー
        self.lbl_source_meta = tk.Label(
            parent,
            text="ファイル未読み込み（左側でPDFを選択して「プレビューを更新」を押してください）",
            font=("Segoe UI", 9),
            fg=self.COLOR_TEXT_MUTED,
            bg=self.COLOR_BG,
            anchor="w",
            padx=10,
            pady=4,
        )
        self.lbl_source_meta.pack(fill=tk.X)

        # プレビュー用キャンバス
        preview_container = ttk.Frame(parent)
        preview_container.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.canvas_preview = tk.Canvas(preview_container, bg="#475569", highlightthickness=0)
        self.canvas_preview.pack(fill=tk.BOTH, expand=True)

        # キャンバスクリック＆ドラッグイベント（黒塗り用）
        self.canvas_preview.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas_preview.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas_preview.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas_preview.bind("<Configure>", self._on_preview_resize)

    # -------------------------------------------------------------
    # ファイル操作ハンドラ
    # -------------------------------------------------------------
    def _select_cover(self):
        file_path = filedialog.askopenfilename(
            title="表紙PDFを選択",
            filetypes=[("PDF files", "*.pdf")],
        )
        if file_path:
            self.cover_path = file_path
            self.lbl_cover.configure(text=os.path.basename(file_path), fg="#1E293B")
            self.refresh_preview()

    def _clear_cover(self):
        self.cover_path = None
        self.lbl_cover.configure(text="（未選択）", fg=self.COLOR_TEXT_MUTED)
        self.refresh_preview()

    def _add_body_files(self):
        file_paths = filedialog.askopenfilenames(
            title="本文PDFを選択（複数選択可）",
            filetypes=[("PDF files", "*.pdf")],
        )
        if file_paths:
            for p in file_paths:
                if p not in self.body_paths:
                    self.body_paths.append(p)
                    self.body_listbox.insert(tk.END, os.path.basename(p))
            self.refresh_preview()

    def _move_body_up(self):
        sel = self.body_listbox.curselection()
        if not sel or sel[0] == 0:
            return
        idx = sel[0]
        # swap
        self.body_paths[idx], self.body_paths[idx - 1] = self.body_paths[idx - 1], self.body_paths[idx]
        item = self.body_listbox.get(idx)
        self.body_listbox.delete(idx)
        self.body_listbox.insert(idx - 1, item)
        self.body_listbox.selection_set(idx - 1)
        self.refresh_preview()

    def _move_body_down(self):
        sel = self.body_listbox.curselection()
        if not sel or sel[0] >= len(self.body_paths) - 1:
            return
        idx = sel[0]
        self.body_paths[idx], self.body_paths[idx + 1] = self.body_paths[idx + 1], self.body_paths[idx]
        item = self.body_listbox.get(idx)
        self.body_listbox.delete(idx)
        self.body_listbox.insert(idx + 1, item)
        self.body_listbox.selection_set(idx + 1)
        self.refresh_preview()

    def _remove_selected_body(self):
        sel = self.body_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        del self.body_paths[idx]
        self.body_listbox.delete(idx)
        self.refresh_preview()

    def _clear_all_body(self):
        self.body_paths.clear()
        self.body_listbox.delete(0, tk.END)
        self.refresh_preview()

    def _select_back_cover(self):
        file_path = filedialog.askopenfilename(
            title="裏表紙PDFを選択",
            filetypes=[("PDF files", "*.pdf")],
        )
        if file_path:
            self.back_cover_path = file_path
            self.lbl_back_cover.configure(text=os.path.basename(file_path), fg="#1E293B")
            self.refresh_preview()

    def _clear_back_cover(self):
        self.back_cover_path = None
        self.lbl_back_cover.configure(text="（未選択）", fg=self.COLOR_TEXT_MUTED)
        self.refresh_preview()

    # -------------------------------------------------------------
    # プレビュー生成＆描画
    # -------------------------------------------------------------
    def refresh_preview(self):
        # 編集後記データ準備
        afterword_data = {
            "title": self.entry_afterword_title.get(),
            "body": self.text_afterword_body.get("1.0", tk.END),
            "editor": self.entry_afterword_editor.get(),
            "date_str": self.entry_afterword_date.get(),
        }

        paper_size = self.combo_paper_size.get()

        # 一時的にドキュメントを構築
        try:
            doc, meta = core_engine.build_unified_pdf(
                cover_path=self.cover_path,
                body_paths=self.body_paths,
                back_cover_path=self.back_cover_path,
                paper_size_name=paper_size,
                include_afterword=self.var_use_afterword.get(),
                afterword_data=afterword_data,
            )
            self.current_doc = doc
            self.current_metadata = meta

            if len(self.current_doc) == 0:
                self.current_page_idx = 0
                self.canvas_preview.delete("all")
                self.lbl_page_info.configure(text="ページ: 0 / 0")
                self.lbl_source_meta.configure(text="表示できるPDFがありません。")
                self.lbl_redact_count.configure(text="黒塗り: 0 箇所")
                return

            if self.current_page_idx >= len(self.current_doc):
                self.current_page_idx = max(0, len(self.current_doc) - 1)

            self._render_current_page()
        except Exception as e:
            messagebox.showerror("プレビューエラー", f"プレビューの生成中にエラーが発生しました:\n{e}")

    def _render_current_page(self):
        if not self.current_doc or len(self.current_doc) == 0:
            return

        page = self.current_doc[self.current_page_idx]
        meta = self.current_metadata[self.current_page_idx] if self.current_page_idx < len(self.current_metadata) else {}

        # ツールバー＆メタ情報更新
        total_pages = len(self.current_doc)
        self.lbl_page_info.configure(text=f"ページ: {self.current_page_idx + 1} / {total_pages}")
        source_desc = f"【{meta.get('type', '')}】 {meta.get('source', '')} (P.{meta.get('page', 1)})"
        self.lbl_source_meta.configure(text=source_desc)

        # 黒塗り件数表示
        cur_redacts = self.redactions.get(self.current_page_idx, [])
        self.lbl_redact_count.configure(text=f"黒塗り: {len(cur_redacts)} 箇所")

        # キャンバスサイズ取得
        canv_w = self.canvas_preview.winfo_width()
        canv_h = self.canvas_preview.winfo_height()
        if canv_w <= 10 or canv_h <= 10:
            canv_w, canv_h = 700, 800

        # 余白を設けてPDFページを収める
        pad = 20
        target_canv_w = max(100, canv_w - pad * 2)
        target_canv_h = max(100, canv_h - pad * 2)

        pdf_w = page.rect.width
        pdf_h = page.rect.height

        scale = min(target_canv_w / pdf_w, target_canv_h / pdf_h)
        # DPIの計算: 通常の72dpiに対してscale倍
        zoom = scale
        mat = pymupdf.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self.preview_image = img
        self.preview_photo = ImageTk.PhotoImage(img)

        self.canvas_scale_x = zoom
        self.canvas_scale_y = zoom
        self.canvas_offset_x = (canv_w - pix.width) / 2
        self.canvas_offset_y = (canv_h - pix.height) / 2

        self.canvas_preview.delete("all")
        # 影の描画
        self.canvas_preview.create_rectangle(
            self.canvas_offset_x + 3,
            self.canvas_offset_y + 3,
            self.canvas_offset_x + pix.width + 3,
            self.canvas_offset_y + pix.height + 3,
            fill="#1E293B",
            outline="",
        )
        # ページ画像
        self.canvas_preview.create_image(
            self.canvas_offset_x,
            self.canvas_offset_y,
            anchor="nw",
            image=self.preview_photo,
        )

        # 登録済みの黒塗り矩形を描画
        for r in cur_redacts:
            x0 = self.canvas_offset_x + r[0] * self.canvas_scale_x
            y0 = self.canvas_offset_y + r[1] * self.canvas_scale_y
            x1 = self.canvas_offset_x + r[2] * self.canvas_scale_x
            y1 = self.canvas_offset_y + r[3] * self.canvas_scale_y
            self.canvas_preview.create_rectangle(x0, y0, x1, y1, fill="black", outline="#EF4444", width=1)

    def _on_preview_resize(self, event):
        self._render_current_page()

    def _prev_page(self):
        if self.current_doc and self.current_page_idx > 0:
            self.current_page_idx -= 1
            self._render_current_page()

    def _next_page(self):
        if self.current_doc and self.current_page_idx < len(self.current_doc) - 1:
            self.current_page_idx += 1
            self._render_current_page()

    # -------------------------------------------------------------
    # 黒塗り（校正ドラッグ操作）
    # -------------------------------------------------------------
    def _on_canvas_press(self, event):
        if not self.current_doc or len(self.current_doc) == 0:
            return
        self.drag_start = (event.x, event.y)
        if self.drag_rect_id:
            self.canvas_preview.delete(self.drag_rect_id)
            self.drag_rect_id = None

    def _on_canvas_drag(self, event):
        if not self.drag_start:
            return
        x0, y0 = self.drag_start
        x1, y1 = event.x, event.y
        if self.drag_rect_id:
            self.canvas_preview.coords(self.drag_rect_id, x0, y0, x1, y1)
        else:
            self.drag_rect_id = self.canvas_preview.create_rectangle(
                x0, y0, x1, y1,
                fill="#334155",
                stipple="gray50",
                outline="#EF4444",
                width=1.5,
            )

    def _on_canvas_release(self, event):
        if not self.drag_start:
            return
        x0, y0 = self.drag_start
        x1, y1 = event.x, event.y
        self.drag_start = None

        if self.drag_rect_id:
            self.canvas_preview.delete(self.drag_rect_id)
            self.drag_rect_id = None

        # 微小なクリックミスは無視
        if abs(x1 - x0) < 5 or abs(y1 - y0) < 5:
            return

        # 左上・右下に整列
        min_x, max_x = min(x0, x1), max(x0, x1)
        min_y, max_y = min(y0, y1), max(y0, y1)

        # PDF座標への逆変換
        pdf_x0 = (min_x - self.canvas_offset_x) / self.canvas_scale_x
        pdf_y0 = (min_y - self.canvas_offset_y) / self.canvas_scale_y
        pdf_x1 = (max_x - self.canvas_offset_x) / self.canvas_scale_x
        pdf_y1 = (max_y - self.canvas_offset_y) / self.canvas_scale_y

        if self.current_page_idx not in self.redactions:
            self.redactions[self.current_page_idx] = []
        self.redactions[self.current_page_idx].append((pdf_x0, pdf_y0, pdf_x1, pdf_y1))

        # 画面を再描画して確定した黒塗りを表示
        self._render_current_page()

    def _undo_redaction(self):
        if self.current_page_idx in self.redactions and self.redactions[self.current_page_idx]:
            self.redactions[self.current_page_idx].pop()
            self._render_current_page()

    def _clear_current_page_redactions(self):
        if self.current_page_idx in self.redactions:
            self.redactions[self.current_page_idx].clear()
            self._render_current_page()

    # -------------------------------------------------------------
    # 発行（完成版PDF保存）
    # -------------------------------------------------------------
    def export_pdf(self):
        if not self.cover_path and not self.body_paths and not self.back_cover_path:
            messagebox.showwarning("警告", "結合するPDFが1つも選択されていません。")
            return

        today_str = datetime.date.today().strftime("%Y%m%d")
        default_filename = f"ぴん球_完成版_{today_str}.pdf"

        save_path = filedialog.asksaveasfilename(
            title="完成版PDFの保存先を指定",
            initialfile=default_filename,
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
        )
        if not save_path:
            return

        try:
            # 1. 結合・サイズ統一ドキュメントの再構築
            afterword_data = {
                "title": self.entry_afterword_title.get(),
                "body": self.text_afterword_body.get("1.0", tk.END),
                "editor": self.entry_afterword_editor.get(),
                "date_str": self.entry_afterword_date.get(),
            }
            paper_size = self.combo_paper_size.get()

            out_doc, _ = core_engine.build_unified_pdf(
                cover_path=self.cover_path,
                body_paths=self.body_paths,
                back_cover_path=self.back_cover_path,
                paper_size_name=paper_size,
                include_afterword=self.var_use_afterword.get(),
                afterword_data=afterword_data,
            )

            # 2. 黒塗り適用 & 最適化保存
            core_engine.apply_redactions_and_save(
                doc=out_doc,
                redactions=self.redactions,
                output_path=save_path,
            )

            # 3. 完了通知 & フォルダを開く確認
            resp = messagebox.askyesno(
                "発行完了！",
                f"サークル誌「ぴん球」完成版PDFを出力しました！\n\n保存先: {save_path}\n\n保存先のフォルダを開きますか？",
            )
            if resp:
                folder_dir = os.path.dirname(os.path.abspath(save_path))
                if sys.platform == "win32":
                    subprocess.Popen(["explorer", folder_dir])

        except Exception as e:
            messagebox.showerror("発行エラー", f"PDFの発行中にエラーが発生しました:\n{e}")


def main():
    root = tk.Tk()
    app = PingQEditorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
