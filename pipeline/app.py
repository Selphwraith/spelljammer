"""Main Tkinter application for Game Launch Pipeline."""
import json
import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Optional

from .api import ClaudeAPIError, ClaudeClient
from .generator import FileGenerator, fmt_size
from .prompts import (
    analytics_js,
    itch_config,
    key_art,
    press_release,
    social_media,
    steam_config,
    store_listing,
)
from .scanner import scan_game_path
from .state import STAGES, PipelineState

# ─────────────────────────────────────────────────────────────────────────────
# Color palette + typography
# ─────────────────────────────────────────────────────────────────────────────

class C:
    BG      = "#0d1117"
    PANEL   = "#161b22"
    PANEL2  = "#21262d"
    BORDER  = "#30363d"
    ACCENT  = "#58a6ff"
    SUCCESS = "#3fb950"
    WARNING = "#d29922"
    ERROR   = "#f85149"
    TEXT    = "#e6edf3"
    DIM     = "#8b949e"
    PURPLE  = "#bc8cff"
    ORANGE  = "#ffa657"
    BTN_G   = "#238636"   # green primary
    BTN_B   = "#1f6feb"   # blue secondary
    BTN_D   = "#21262d"   # dark neutral
    BTN_R   = "#8b0000"   # red danger
    HDR     = "#010409"   # header strip


_FF = "Courier" if sys.platform != "darwin" else "Menlo"


# ─────────────────────────────────────────────────────────────────────────────
# Widget factory helpers
# ─────────────────────────────────────────────────────────────────────────────

def _lighten(h: str, amt: int = 22) -> str:
    h = h.lstrip("#")
    r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:], 16)
    return "#{:02x}{:02x}{:02x}".format(min(255, r+amt), min(255, g+amt), min(255, b+amt))


def frm(parent, bg=C.PANEL, **kw) -> tk.Frame:
    return tk.Frame(parent, bg=bg, **kw)


def lbl(parent, text="", size=11, weight="normal", fg=C.TEXT, bg=None, **kw) -> tk.Label:
    bg = bg if bg is not None else parent.cget("bg")
    return tk.Label(parent, text=text, fg=fg, bg=bg,
                    font=(_FF, size, weight), **kw)


def btn(parent, text: str, command, style: str = "dark", **kw) -> tk.Button:
    bgs = {"green": C.BTN_G, "blue": C.BTN_B, "dark": C.BTN_D, "red": C.BTN_R}
    bg = bgs.get(style, C.BTN_D)
    b = tk.Button(
        parent, text=text, command=command,
        bg=bg, fg=C.TEXT, activebackground=_lighten(bg), activeforeground=C.TEXT,
        relief="flat", cursor="hand2", font=(_FF, 10, "bold"),
        padx=kw.pop("padx", 14), pady=kw.pop("pady", 7), **kw,
    )
    b.bind("<Enter>", lambda _: b.config(bg=_lighten(bg)))
    b.bind("<Leave>", lambda _: b.config(bg=bg))
    return b


def sep(parent, orient="h") -> tk.Frame:
    if orient == "h":
        return tk.Frame(parent, bg=C.BORDER, height=1)
    return tk.Frame(parent, bg=C.BORDER, width=1)


def entry(parent, textvariable=None, **kw) -> tk.Entry:
    e = tk.Entry(
        parent, textvariable=textvariable,
        bg=C.PANEL2, fg=C.TEXT, insertbackground=C.TEXT,
        relief="flat", font=(_FF, 10),
        highlightthickness=1, highlightbackground=C.BORDER, highlightcolor=C.ACCENT,
        **kw,
    )
    return e


def textarea(parent, height=5, **kw) -> tk.Text:
    t = tk.Text(
        parent, height=height,
        bg=C.PANEL2, fg=C.TEXT, insertbackground=C.TEXT,
        relief="flat", font=(_FF, 10), wrap="word",
        highlightthickness=1, highlightbackground=C.BORDER, highlightcolor=C.ACCENT,
        selectbackground=C.ACCENT, selectforeground=C.HDR,
        **kw,
    )
    return t


# ─────────────────────────────────────────────────────────────────────────────
# ScrollableFrame
# ─────────────────────────────────────────────────────────────────────────────

class ScrollableFrame(tk.Frame):
    def __init__(self, parent, bg=C.PANEL, **kw):
        super().__init__(parent, bg=bg, **kw)
        c = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(self, orient="vertical", command=c.yview,
                          bg=C.PANEL, troughcolor=C.PANEL2, width=10)
        self.inner = tk.Frame(c, bg=bg)
        self._win = c.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda _: c.configure(
            scrollregion=c.bbox("all")))
        c.configure(yscrollcommand=sb.set)
        c.bind("<Configure>", lambda e: c.itemconfig(self._win, width=e.width))
        c.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        c.bind_all("<MouseWheel>", lambda e: c.yview_scroll(
            int(-1 * (e.delta / 120)), "units"))


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline timeline header
# ─────────────────────────────────────────────────────────────────────────────

_STAGES_META = [
    ("dev",         "👨‍💻", "Dev"),
    ("marketing",   "📢", "Marketing"),
    ("store_setup", "⚙️",  "Store Setup"),
    ("deploy",      "🚀", "Deploy"),
]


class PipelineTimeline(tk.Frame):
    def __init__(self, parent, app, **kw):
        super().__init__(parent, bg=C.HDR, **kw)
        self.app = app
        self._stage_widgets: dict[str, dict] = {}
        self._build()

    def _build(self):
        title_row = frm(self, bg=C.HDR)
        title_row.pack(fill="x", padx=20, pady=(12, 6))
        lbl(title_row, "🎮  GAME LAUNCH PIPELINE", 15, "bold", bg=C.HDR).pack(side="left")
        self._game_lbl = lbl(title_row, "", 10, bg=C.HDR, fg=C.DIM)
        self._game_lbl.pack(side="right")

        stages_row = frm(self, bg=C.HDR)
        stages_row.pack(fill="x", padx=30, pady=(0, 12))

        for i, (sid, emoji, label) in enumerate(_STAGES_META):
            if i > 0:
                connector = frm(stages_row, bg=C.BORDER, height=2, width=50)
                connector.pack(side="left", padx=2, pady=20)

            sf = frm(stages_row, bg=C.HDR, cursor="hand2")
            sf.pack(side="left", padx=6)

            dot = lbl(sf, "◉", 20, bg=C.HDR, fg=C.BORDER)
            dot.pack()
            elbl = tk.Label(sf, text=emoji, font=("", 14), bg=C.HDR)
            elbl.pack()
            nlbl = lbl(sf, label, 9, bg=C.HDR, fg=C.DIM)
            nlbl.pack()
            slbl = lbl(sf, "pending", 8, bg=C.HDR, fg=C.DIM)
            slbl.pack()

            self._stage_widgets[sid] = {"dot": dot, "nlbl": nlbl, "slbl": slbl, "frame": sf}

            def _click(s=sid):
                if not self.app.state:
                    return
                st = self.app.state.stages.get(s, {}).get("status", "pending")
                if st in ("complete", "in_progress"):
                    self.app.show_phase(s)

            for w in [sf, dot, elbl, nlbl, slbl]:
                w.bind("<Button-1>", lambda _, s=sid: _click(s))

        sep(self, "h").pack(fill="x")

    def update(self, state: Optional[PipelineState]):
        if state is None:
            return
        name = state.game_info.get("name", "")
        if name:
            self._game_lbl.config(text=f"  //  {name}")
        for sid, w in self._stage_widgets.items():
            status = state.stages.get(sid, {}).get("status", "pending")
            if status == "complete":
                w["dot"].config(fg=C.SUCCESS)
                w["nlbl"].config(fg=C.TEXT, font=(_FF, 9, "normal"))
                w["slbl"].config(text="✓ done", fg=C.SUCCESS)
            elif status == "in_progress":
                w["dot"].config(fg=C.ACCENT)
                w["nlbl"].config(fg=C.ACCENT, font=(_FF, 9, "bold"))
                w["slbl"].config(text="● active", fg=C.ACCENT)
            elif status == "awaiting_approval":
                w["dot"].config(fg=C.WARNING)
                w["nlbl"].config(fg=C.WARNING, font=(_FF, 9, "normal"))
                w["slbl"].config(text="⚠ review", fg=C.WARNING)
            else:
                w["dot"].config(fg=C.BORDER)
                w["nlbl"].config(fg=C.DIM, font=(_FF, 9, "normal"))
                w["slbl"].config(text="pending", fg=C.DIM)


# ─────────────────────────────────────────────────────────────────────────────
# Status bar
# ─────────────────────────────────────────────────────────────────────────────

class StatusBar(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=C.HDR, height=26, **kw)
        sep(self, "h").pack(fill="x", side="top")
        self._msg = lbl(self, "  Ready.", 9, bg=C.HDR, fg=C.DIM)
        self._msg.pack(side="left", padx=10, pady=3)
        self._right = lbl(self, "", 9, bg=C.HDR, fg=C.DIM)
        self._right.pack(side="right", padx=10)

    def set(self, msg: str, color: str = C.DIM):
        self._msg.config(text=f"  {msg}", fg=color)

    def set_right(self, msg: str):
        self._right.config(text=msg)


# ─────────────────────────────────────────────────────────────────────────────
# Dev Phase
# ─────────────────────────────────────────────────────────────────────────────

class DevPhase(tk.Frame):
    def __init__(self, parent, app: "GameLaunchApp", **kw):
        super().__init__(parent, bg=C.BG, **kw)
        self.app = app
        self._scan_info: dict = {}
        self._build()
        # Pre-fill if we have state or a game_path
        if app.state and app.state.game_info.get("name"):
            self._populate_from_state()
        elif app.game_path:
            self._path_var.set(app.game_path)
            self.after(100, self._do_scan)

    def _build(self):
        # ── header ──
        hdr = frm(self, bg=C.BG)
        hdr.pack(fill="x", padx=20, pady=(18, 0))
        lbl(hdr, "👨‍💻  Developer Stage", 17, "bold", bg=C.BG).pack(side="left")
        lbl(hdr, "  Scan your game project and confirm details", 10, bg=C.BG, fg=C.DIM).pack(
            side="left", pady=6)

        # ── path input ──
        path_panel = frm(self, bg=C.PANEL)
        path_panel.pack(fill="x", padx=20, pady=14)
        lbl(path_panel, "  Game Folder Path", 9, fg=C.DIM, bg=C.PANEL).pack(
            anchor="w", padx=10, pady=(10, 4))

        path_row = frm(path_panel, bg=C.PANEL)
        path_row.pack(fill="x", padx=10, pady=(0, 10))
        self._path_var = tk.StringVar()
        e = entry(path_row, textvariable=self._path_var)
        e.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        e.bind("<Return>", lambda _: self._do_scan())
        btn(path_row, "Browse", self._browse).pack(side="left", padx=(0, 6))
        btn(path_row, "Scan →", self._do_scan, style="blue").pack(side="left")

        # ── scan results ──
        self._result_panel = frm(self, bg=C.PANEL)
        self._result_panel.pack(fill="both", expand=True, padx=20, pady=(0, 14))

        inner = frm(self._result_panel, bg=C.PANEL)
        inner.pack(fill="both", expand=True, padx=14, pady=12)

        lbl(inner, "Scan Results", 10, "bold", fg=C.DIM, bg=C.PANEL).pack(anchor="w", pady=(0, 8))
        self._placeholder = lbl(inner, "Enter a game folder path above and click Scan.",
                                 10, fg=C.DIM, bg=C.PANEL)
        self._placeholder.pack(anchor="w")
        self._info_grid = frm(inner, bg=C.PANEL)
        self._info_grid.pack(fill="x", anchor="w")

        sep(inner, "h").pack(fill="x", pady=10)

        # editable fields
        fields = frm(inner, bg=C.PANEL)
        fields.pack(fill="both", expand=True)
        fields.columnconfigure(0, weight=1)
        fields.columnconfigure(1, weight=3)

        lbl(fields, "Game Name:", 9, fg=C.DIM, bg=C.PANEL).grid(
            row=0, column=0, sticky="nw", pady=2)
        self._name_var = tk.StringVar()
        entry(fields, textvariable=self._name_var).grid(
            row=0, column=1, sticky="ew", padx=(6, 0), ipady=6, pady=2)

        lbl(fields, "Description:", 9, fg=C.DIM, bg=C.PANEL).grid(
            row=1, column=0, sticky="nw", pady=(8, 0))
        self._desc = textarea(inner, height=4)
        self._desc.pack(fill="x", pady=(6, 0))

        lbl(inner, "  Tip: Description is used as context for all Claude API marketing calls.", 9,
            fg=C.DIM, bg=C.PANEL).pack(anchor="w", pady=(4, 0))

        # ── bottom actions ──
        acts = frm(self, bg=C.BG)
        acts.pack(fill="x", padx=20, pady=(0, 18))
        self._ready_btn = btn(acts, "  ✓  Build Ready  →  ", self._build_ready, style="green")
        self._ready_btn.pack(side="right")
        self._ready_btn.config(state="disabled")

    def _populate_from_state(self):
        gi = self.app.state.game_info
        self._path_var.set(gi.get("path", self.app.game_path or ""))
        self._name_var.set(gi.get("name", ""))
        self._desc.delete("1.0", "end")
        self._desc.insert("1.0", gi.get("description", ""))
        self._show_info({
            "path": gi.get("path", ""),
            "main_file": gi.get("main_file"),
            "all_files": [""] * gi.get("file_count", 0),
            "size_bytes": gi.get("size_bytes", 0),
            "file_types": gi.get("file_types", []),
        })
        self._ready_btn.config(state="normal")

    def _browse(self):
        p = filedialog.askdirectory(title="Select Game Folder")
        if p:
            self._path_var.set(p)
            self._do_scan()

    def _do_scan(self):
        path = self._path_var.get().strip()
        if not path:
            messagebox.showwarning("No Path", "Please enter a game folder path.")
            return
        self._placeholder.config(text="Scanning…", fg=C.ACCENT)
        self.app.statusbar.set("Scanning folder…", C.ACCENT)
        self._clear_info()

        def _run():
            try:
                info = scan_game_path(path)
                self.after(0, lambda: self._on_scan_done(info))
            except Exception as exc:
                self.after(0, lambda: self._on_scan_err(str(exc)))

        threading.Thread(target=_run, daemon=True).start()

    def _on_scan_done(self, info: dict):
        self._scan_info = info
        self._show_info(info)
        self._name_var.set(info.get("name", ""))
        self._desc.delete("1.0", "end")
        self._desc.insert("1.0", info.get("description", ""))
        self._ready_btn.config(state="normal")
        n = len(info.get("all_files", []))
        sz = fmt_size(info.get("size_bytes", 0))
        self.app.statusbar.set(f"Scanned: {n} files  |  {sz}", C.SUCCESS)

    def _on_scan_err(self, msg: str):
        self._placeholder.config(text=f"✗ {msg}", fg=C.ERROR)
        self.app.statusbar.set(f"Scan error: {msg}", C.ERROR)

    def _clear_info(self):
        for w in self._info_grid.winfo_children():
            w.destroy()

    def _show_info(self, info: dict):
        self._placeholder.pack_forget()
        self._clear_info()
        rows = [
            ("Path", info.get("path", "—")),
            ("Main File", info.get("main_file") or "(not detected)"),
            ("Files", str(len(info.get("all_files", [])))),
            ("Size", fmt_size(info.get("size_bytes", 0))),
            ("Types", ", ".join(info.get("file_types", [])[:10]) or "—"),
        ]
        for label, value in rows:
            row = frm(self._info_grid, bg=C.PANEL)
            row.pack(fill="x", pady=1)
            lbl(row, f"  {label}", 9, fg=C.DIM, bg=C.PANEL).pack(side="left", width=100, anchor="w")
            vc = C.SUCCESS if label == "Main File" and value != "(not detected)" else C.TEXT
            if label == "Main File" and value == "(not detected)":
                vc = C.WARNING
            lbl(row, value, 9, fg=vc, bg=C.PANEL).pack(side="left")

    def _build_ready(self):
        path = self._path_var.get().strip()
        name = self._name_var.get().strip()
        desc = self._desc.get("1.0", "end").strip()
        if not path:
            messagebox.showwarning("Missing Path", "Please scan a game folder first.")
            return
        if not name:
            messagebox.showwarning("Missing Name", "Please provide a game name.")
            return
        # Initialise state
        if not self.app.state:
            self.app.state = PipelineState(path)
            self.app.state.load()
        self.app.state.update_game_info({
            "name": name,
            "description": desc,
            "path": path,
            "main_file": self._scan_info.get("main_file"),
            "file_count": len(self._scan_info.get("all_files", [])),
            "size_bytes": self._scan_info.get("size_bytes", 0),
            "file_types": self._scan_info.get("file_types", []),
        })
        self.app.state.complete_stage("dev")
        self.app.file_generator = FileGenerator(path)
        self.app.timeline.update(self.app.state)
        self.app.show_phase("marketing")
        self.app.statusbar.set("Dev complete — launching marketing generation…", C.SUCCESS)


# ─────────────────────────────────────────────────────────────────────────────
# Variant tab (used inside MarketingPhase notebook)
# ─────────────────────────────────────────────────────────────────────────────

class VariantTab(tk.Frame):
    """Displays 5 generated variants with a selector and editable preview."""

    def __init__(self, parent, content_type: str, app: "GameLaunchApp",
                 on_approve=None, bg=C.PANEL, **kw):
        super().__init__(parent, bg=bg, **kw)
        self.content_type = content_type
        self.app = app
        self._on_approve_cb = on_approve
        self._variants: list[str] = []
        self._sel = tk.IntVar(value=0)
        self._editing = False
        self._build()

    def _build(self):
        self._status_lbl = lbl(self, "⏳ Waiting for generation…", 10, fg=C.DIM, bg=self.cget("bg"))
        self._status_lbl.pack(anchor="w", padx=14, pady=(12, 6))

        # selector row
        self._sel_row = frm(self, bg=self.cget("bg"))
        self._sel_row.pack(fill="x", padx=14)
        self._radios: list[tk.Radiobutton] = []
        for i in range(5):
            rb = tk.Radiobutton(
                self._sel_row, text=f"  V{i+1}  ", variable=self._sel, value=i,
                command=self._on_select,
                bg=self.cget("bg"), fg=C.DIM, selectcolor=C.PANEL2,
                activebackground=self.cget("bg"), activeforeground=C.TEXT,
                font=(_FF, 9, "bold"), relief="flat", cursor="hand2",
                indicatoron=False, borderwidth=1,
                highlightthickness=0,
            )
            rb.pack(side="left", padx=2)
            self._radios.append(rb)

        # text area
        ta_frame = frm(self, bg=self.cget("bg"))
        ta_frame.pack(fill="both", expand=True, padx=14, pady=8)
        self._ta = textarea(ta_frame, height=10)
        self._ta.pack(fill="both", expand=True)
        self._ta.config(state="disabled")

        # actions row
        act = frm(self, bg=self.cget("bg"))
        act.pack(fill="x", padx=14, pady=(0, 10))
        self._edit_btn = btn(act, "✎ Edit", self._toggle_edit, style="dark")
        self._edit_btn.pack(side="left", padx=(0, 8))
        self._approve_btn = btn(act, "✓ Use This", self._approve, style="green")
        self._approve_btn.pack(side="left")
        self._approved_lbl = lbl(act, "", 9, fg=C.SUCCESS, bg=self.cget("bg"))
        self._approved_lbl.pack(side="left", padx=12)

    def set_variants(self, variants: list[str]):
        self._variants = variants
        self._sel.set(0)
        for i, rb in enumerate(self._radios):
            rb.config(fg=C.TEXT if i < len(variants) else C.DIM,
                      state="normal" if i < len(variants) else "disabled")
        self._status_lbl.config(text=f"✓ {len(variants)} variants generated — pick the best one",
                                 fg=C.SUCCESS)
        self._show_variant(0)

    def _show_variant(self, idx: int):
        if idx >= len(self._variants):
            return
        self._ta.config(state="normal")
        self._ta.delete("1.0", "end")
        self._ta.insert("1.0", self._variants[idx])
        if not self._editing:
            self._ta.config(state="disabled")
        # Highlight selected radio
        for i, rb in enumerate(self._radios):
            rb.config(
                bg=C.ACCENT if i == idx else self.cget("bg"),
                fg=C.HDR if i == idx else (C.TEXT if i < len(self._variants) else C.DIM),
            )

    def _on_select(self):
        self._show_variant(self._sel.get())

    def _toggle_edit(self):
        self._editing = not self._editing
        self._ta.config(state="normal" if self._editing else "disabled")
        self._edit_btn.config(text="✓ Done" if self._editing else "✎ Edit")

    def _approve(self):
        text = self._ta.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("Empty", "No content to approve.")
            return
        self.app.state.set_marketing_selection(self.content_type, self._sel.get(), text)
        self._approved_lbl.config(text=f"  ✓ Approved — {len(text)} chars")
        self._editing = False
        self._ta.config(state="disabled")
        self._edit_btn.config(text="✎ Edit")
        if self._on_approve_cb:
            self._on_approve_cb()

    def set_error(self, msg: str):
        self._status_lbl.config(text=f"✗ Error: {msg}", fg=C.ERROR)

    def set_generating(self):
        self._status_lbl.config(text="⏳ Generating with Claude…", fg=C.ACCENT)

    def is_approved(self) -> bool:
        return bool(self.app.state and
                    self.app.state.marketing.get(self.content_type, {}).get("final_text"))

    def restore_from_state(self):
        if not self.app.state:
            return
        m = self.app.state.marketing.get(self.content_type, {})
        variants = m.get("variants", [])
        if variants:
            self.set_variants(variants)
            idx = m.get("selected_index", 0)
            self._sel.set(idx)
            self._show_variant(idx)
        final = m.get("final_text", "")
        if final:
            self._approved_lbl.config(text=f"  ✓ Approved — {len(final)} chars")


# ─────────────────────────────────────────────────────────────────────────────
# Marketing Phase
# ─────────────────────────────────────────────────────────────────────────────

_MKT_TABS = [
    ("store_listing", "🏪 Store Listing",    "itch.io style, 500 chars"),
    ("social_media",  "🐦 Social Thread",     "3-tweet announcement thread"),
    ("press_release", "📰 Press Release",     "150-200 word snippet"),
    ("key_art",       "🎨 Key Art Briefs",    "Artist direction for key images"),
]


class MarketingPhase(tk.Frame):
    def __init__(self, parent, app: "GameLaunchApp", **kw):
        super().__init__(parent, bg=C.BG, **kw)
        self.app = app
        self._tabs: dict[str, VariantTab] = {}
        self._pending = set()
        self._build()
        self._restore_or_generate()

    def _build(self):
        hdr = frm(self, bg=C.BG)
        hdr.pack(fill="x", padx=20, pady=(18, 0))
        lbl(hdr, "📢  Marketing Phase", 17, "bold", bg=C.BG).pack(side="left")
        lbl(hdr, "  Claude generates 5 variants of each asset — you pick the best", 10,
            bg=C.BG, fg=C.DIM).pack(side="left", pady=6)

        # progress bar area
        prog_row = frm(self, bg=C.BG)
        prog_row.pack(fill="x", padx=20, pady=(6, 0))
        self._prog_lbl = lbl(prog_row, "0 / 4 generated", 9, fg=C.DIM, bg=C.BG)
        self._prog_lbl.pack(side="left")
        self._retry_btn = btn(prog_row, "↺ Retry All", self._start_generation, style="dark")
        self._retry_btn.pack(side="right")
        self._retry_btn.pack_forget()

        # notebook
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.TNotebook", background=C.BG, borderwidth=0, tabmargins=0)
        style.configure("Dark.TNotebook.Tab", background=C.PANEL2, foreground=C.DIM,
                        padding=[14, 5], borderwidth=0, font=(_FF, 9, "bold"))
        style.map("Dark.TNotebook.Tab",
                  background=[("selected", C.PANEL), ("active", C.BORDER)],
                  foreground=[("selected", C.TEXT), ("active", C.TEXT)])

        self._nb = ttk.Notebook(self, style="Dark.TNotebook")
        self._nb.pack(fill="both", expand=True, padx=20, pady=8)

        for ct, tab_label, _ in _MKT_TABS:
            vt = VariantTab(self._nb, ct, self.app,
                            on_approve=self._update_progress, bg=C.PANEL)
            self._nb.add(vt, text=f"  {tab_label}  ")
            self._tabs[ct] = vt

        # actions
        acts = frm(self, bg=C.BG)
        acts.pack(fill="x", padx=20, pady=(0, 18))
        btn(acts, "← Back to Dev", lambda: self.app.show_phase("dev"), style="dark").pack(
            side="left")
        self._complete_btn = btn(acts, "  Marketing Complete  →  ",
                                 self._marketing_complete, style="green")
        self._complete_btn.pack(side="right")
        self._complete_btn.config(state="disabled")

    def _restore_or_generate(self):
        if not self.app.state:
            return
        # Check if we have cached variants
        any_missing = False
        for ct, _, _ in _MKT_TABS:
            m = self.app.state.marketing.get(ct, {})
            if m.get("variants"):
                self._tabs[ct].restore_from_state()
            else:
                any_missing = True
        if any_missing:
            self._start_generation()
        else:
            self._update_progress()

    def _start_generation(self):
        if not self.app.api_client:
            messagebox.showerror("No API Key",
                "API key not configured. Please add your key to config.json.")
            return
        gi = self.app.state.game_info
        name = gi.get("name", "Untitled Game")
        desc = gi.get("description", "")
        ftypes = gi.get("file_types", [])

        self._pending = set()
        tasks = [
            ("store_listing", store_listing(name, desc, ftypes)),
            ("social_media",  social_media(name, desc)),
            ("press_release", press_release(name, desc)),
            ("key_art",       key_art(name, desc)),
        ]
        for ct, prompt in tasks:
            m = self.app.state.marketing.get(ct, {})
            if not m.get("variants"):
                self._pending.add(ct)
                self._tabs[ct].set_generating()
                self._launch_api_call(ct, prompt)
        self._retry_btn.pack_forget()

    def _launch_api_call(self, content_type: str, prompt: str):
        q: queue.Queue = queue.Queue()

        def _run():
            try:
                data = self.app.api_client.generate_json(prompt, max_tokens=3000)
                q.put(("ok", data))
            except Exception as exc:
                q.put(("err", str(exc)))

        threading.Thread(target=_run, daemon=True).start()
        self._poll(content_type, q)

    def _poll(self, content_type: str, q: queue.Queue):
        if not q.empty():
            result = q.get()
            if result[0] == "ok":
                self._on_api_done(content_type, result[1])
            else:
                self._on_api_err(content_type, result[1])
        else:
            self.after(200, lambda: self._poll(content_type, q))

    def _on_api_done(self, content_type: str, data: dict):
        raw_variants = data.get("variants", [])
        # Social media variants may be lists of tweets — convert to display strings
        variants = []
        for v in raw_variants:
            if isinstance(v, list):
                variants.append("\n\n".join(
                    f"🐦 Tweet {i+1}/{len(v)}:\n{t}" for i, t in enumerate(v)))
            else:
                variants.append(str(v))

        self.app.state.update_marketing_variants(content_type, variants)
        self._tabs[content_type].set_variants(variants)
        self._pending.discard(content_type)
        self._update_progress()

    def _on_api_err(self, content_type: str, msg: str):
        self._tabs[content_type].set_error(msg)
        self._pending.discard(content_type)
        self._update_progress()
        self.app.statusbar.set(f"Error generating {content_type}: {msg}", C.ERROR)
        self._retry_btn.pack(side="right")

    def _update_progress(self):
        done = sum(
            1 for ct, _, _ in _MKT_TABS
            if self.app.state and self.app.state.marketing.get(ct, {}).get("variants")
        )
        self._prog_lbl.config(
            text=f"{done} / 4 generated",
            fg=C.SUCCESS if done == 4 else C.ACCENT,
        )
        approved = sum(1 for ct, _, _ in _MKT_TABS if self._tabs[ct].is_approved())
        if approved == 4:
            self._complete_btn.config(state="normal")
            self.app.statusbar.set("All marketing copy approved!", C.SUCCESS)
        else:
            self.app.statusbar.set(
                f"{approved}/4 content types approved — pick a variant for each tab", C.DIM)

    def _marketing_complete(self):
        if not self.app.state.all_marketing_complete():
            messagebox.showwarning(
                "Not Done", "Please approve a variant in each of the 4 tabs before continuing.")
            return
        self.app.state.complete_stage("marketing")
        self.app.timeline.update(self.app.state)
        self.app.show_phase("store_setup")
        self.app.statusbar.set("Marketing complete — generating store configs…", C.SUCCESS)


# ─────────────────────────────────────────────────────────────────────────────
# Config panel (used inside StoreSetupPhase)
# ─────────────────────────────────────────────────────────────────────────────

class ConfigPanel(tk.Frame):
    def __init__(self, parent, config_type: str, title: str, app: "GameLaunchApp",
                 on_approve=None, bg=C.PANEL2, **kw):
        super().__init__(parent, bg=bg, **kw)
        self.config_type = config_type
        self.app = app
        self._on_approve_cb = on_approve
        self._build(title)

    def _build(self, title: str):
        # header bar
        hdr = frm(self, bg=self.cget("bg"))
        hdr.pack(fill="x", padx=10, pady=(10, 4))
        lbl(hdr, title, 11, "bold", bg=self.cget("bg")).pack(side="left")
        self._status_lbl = lbl(hdr, "pending", 9, fg=C.DIM, bg=self.cget("bg"))
        self._status_lbl.pack(side="left", padx=12)
        self._approve_btn = btn(hdr, "✓ Approve", self._approve, style="green")
        self._approve_btn.pack(side="right")
        self._approve_btn.config(state="disabled")

        # text area
        self._ta = textarea(self, height=10)
        self._ta.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def set_content(self, text: str):
        self._ta.config(state="normal")
        self._ta.delete("1.0", "end")
        self._ta.insert("1.0", text)
        self._approve_btn.config(state="normal")
        self._status_lbl.config(text="⚠ review needed", fg=C.WARNING)

    def set_generating(self):
        self._status_lbl.config(text="⏳ generating…", fg=C.ACCENT)
        self._approve_btn.config(state="disabled")

    def set_error(self, msg: str):
        self._status_lbl.config(text=f"✗ {msg}", fg=C.ERROR)

    def _approve(self):
        text = self._ta.get("1.0", "end").strip()
        self.app.state.set_store_config(self.config_type, text, approved=True)
        self._status_lbl.config(text="✓ approved", fg=C.SUCCESS)
        if self._on_approve_cb:
            self._on_approve_cb()

    def is_approved(self) -> bool:
        return bool(self.app.state and
                    self.app.state.store_configs.get(self.config_type, {}).get("approved"))

    def restore_from_state(self):
        if not self.app.state:
            return
        sc = self.app.state.store_configs.get(self.config_type, {})
        if sc.get("content"):
            self.set_content(sc["content"])
        if sc.get("approved"):
            self._status_lbl.config(text="✓ approved", fg=C.SUCCESS)


# ─────────────────────────────────────────────────────────────────────────────
# Store Setup Phase
# ─────────────────────────────────────────────────────────────────────────────

_CFG_TABS = [
    ("itch_io",   "🟣 Itch.io Config"),
    ("steam",     "🔵 Steam Config"),
    ("analytics", "📊 Analytics Setup"),
]


class StoreSetupPhase(tk.Frame):
    def __init__(self, parent, app: "GameLaunchApp", **kw):
        super().__init__(parent, bg=C.BG, **kw)
        self.app = app
        self._panels: dict[str, ConfigPanel] = {}
        self._build()
        self._restore_or_generate()

    def _build(self):
        hdr = frm(self, bg=C.BG)
        hdr.pack(fill="x", padx=20, pady=(18, 0))
        lbl(hdr, "⚙️  Store Setup Phase", 17, "bold", bg=C.BG).pack(side="left")
        lbl(hdr, "  Review and approve generated platform configs", 10,
            bg=C.BG, fg=C.DIM).pack(side="left", pady=6)

        prog_row = frm(self, bg=C.BG)
        prog_row.pack(fill="x", padx=20, pady=(4, 0))
        self._prog_lbl = lbl(prog_row, "0 / 3 approved", 9, fg=C.DIM, bg=C.BG)
        self._prog_lbl.pack(side="left")
        self._approve_all_btn = btn(prog_row, "✓ Approve All", self._approve_all, style="green")
        self._approve_all_btn.pack(side="right")

        style = ttk.Style()
        style.configure("Store.TNotebook", background=C.BG, borderwidth=0)
        style.configure("Store.TNotebook.Tab", background=C.PANEL2, foreground=C.DIM,
                        padding=[14, 5], borderwidth=0, font=(_FF, 9, "bold"))
        style.map("Store.TNotebook.Tab",
                  background=[("selected", C.PANEL), ("active", C.BORDER)],
                  foreground=[("selected", C.TEXT), ("active", C.TEXT)])

        nb = ttk.Notebook(self, style="Store.TNotebook")
        nb.pack(fill="both", expand=True, padx=20, pady=8)

        for ct, tab_label in _CFG_TABS:
            cp = ConfigPanel(nb, ct, tab_label, self.app,
                             on_approve=self._update_progress, bg=C.PANEL)
            nb.add(cp, text=f"  {tab_label}  ")
            self._panels[ct] = cp

        acts = frm(self, bg=C.BG)
        acts.pack(fill="x", padx=20, pady=(0, 18))
        btn(acts, "← Marketing", lambda: self.app.show_phase("marketing"), style="dark").pack(
            side="left")
        self._next_btn = btn(acts, "  Store Setup Complete  →  ",
                             self._store_complete, style="green")
        self._next_btn.pack(side="right")
        self._next_btn.config(state="disabled")

    def _restore_or_generate(self):
        if not self.app.state:
            return
        any_missing = False
        for ct, _ in _CFG_TABS:
            sc = self.app.state.store_configs.get(ct, {})
            if sc.get("content"):
                self._panels[ct].restore_from_state()
            else:
                any_missing = True
        if any_missing:
            self._start_generation()
        self._update_progress()

    def _start_generation(self):
        if not self.app.api_client:
            messagebox.showerror("No API Key", "API key not configured.")
            return
        gi = self.app.state.game_info
        name = gi.get("name", "Untitled")
        desc = gi.get("description", "")
        store_copy = (self.app.state.marketing.get("store_listing", {}).get("final_text") or desc)

        gen_map = {
            "itch_io":   itch_config(name, desc, store_copy),
            "steam":     steam_config(name, desc, store_copy),
            "analytics": analytics_js(name),
        }
        for ct, prompt in gen_map.items():
            sc = self.app.state.store_configs.get(ct, {})
            if not sc.get("content"):
                self._panels[ct].set_generating()
                self._launch_api_call(ct, prompt)

    def _launch_api_call(self, config_type: str, prompt: str):
        q: queue.Queue = queue.Queue()
        is_js = config_type == "analytics"

        def _run():
            try:
                if is_js:
                    text = self.app.api_client.generate(prompt, max_tokens=2000)
                else:
                    data = self.app.api_client.generate_json(prompt, max_tokens=2000)
                    text = json.dumps(data, indent=2)
                q.put(("ok", text))
            except Exception as exc:
                q.put(("err", str(exc)))

        threading.Thread(target=_run, daemon=True).start()
        self._poll(config_type, q)

    def _poll(self, config_type: str, q: queue.Queue):
        if not q.empty():
            result = q.get()
            if result[0] == "ok":
                self._panels[config_type].set_content(result[1])
                self.app.state.set_store_config(config_type, result[1], approved=False)
                self._update_progress()
            else:
                self._panels[config_type].set_error(result[1])
                self.app.statusbar.set(f"Error: {result[1]}", C.ERROR)
        else:
            self.after(200, lambda: self._poll(config_type, q))

    def _approve_all(self):
        for ct, cp in self._panels.items():
            text = cp._ta.get("1.0", "end").strip()
            if text:
                self.app.state.set_store_config(ct, text, approved=True)
                cp._status_lbl.config(text="✓ approved", fg=C.SUCCESS)
        self._update_progress()

    def _update_progress(self):
        approved = sum(1 for cp in self._panels.values() if cp.is_approved())
        self._prog_lbl.config(
            text=f"{approved} / 3 approved",
            fg=C.SUCCESS if approved == 3 else C.ACCENT,
        )
        if approved == 3:
            self._next_btn.config(state="normal")
            self.app.statusbar.set("All configs approved!", C.SUCCESS)

    def _store_complete(self):
        if not self.app.state.all_configs_approved():
            messagebox.showwarning("Not Done", "Please approve all 3 configs first.")
            return
        self.app.file_generator.save_all(self.app.state.to_dict())
        self.app.state.complete_stage("store_setup")
        self.app.timeline.update(self.app.state)
        self.app.show_phase("deploy")
        self.app.statusbar.set("Configs saved — deploy checklist ready!", C.SUCCESS)


# ─────────────────────────────────────────────────────────────────────────────
# Deploy Phase (checklist)
# ─────────────────────────────────────────────────────────────────────────────

class DeployPhase(tk.Frame):
    def __init__(self, parent, app: "GameLaunchApp", **kw):
        super().__init__(parent, bg=C.BG, **kw)
        self.app = app
        self._build()

    def _build(self):
        hdr = frm(self, bg=C.BG)
        hdr.pack(fill="x", padx=20, pady=(18, 0))
        lbl(hdr, "🚀  Deploy Readiness", 17, "bold", bg=C.BG).pack(side="left")
        lbl(hdr, "  All green = ready to ship", 10, bg=C.BG, fg=C.DIM).pack(side="left", pady=6)

        # scroll area for checklist
        sf = ScrollableFrame(self, bg=C.BG)
        sf.pack(fill="both", expand=True, padx=20, pady=8)
        inner = sf.inner

        self._check_rows: list[dict] = []
        self._populate_checklist(inner)

        # output files section
        sep(inner, "h").pack(fill="x", pady=12)
        lbl(inner, "  📁 Generated Output Files", 11, "bold", fg=C.DIM, bg=C.BG).pack(
            anchor="w", pady=(0, 6))
        self._files_frame = frm(inner, bg=C.BG)
        self._files_frame.pack(fill="x", padx=4)
        self._populate_files()

        # next steps
        sep(inner, "h").pack(fill="x", pady=12)
        lbl(inner, "  ▶ Next Steps", 11, "bold", fg=C.DIM, bg=C.BG).pack(anchor="w", pady=(0, 6))
        steps_text = (
            "  1. Run your build script / export from your engine\n"
            "  2. Upload the build + game-launch/marketing/ assets to Itch.io\n"
            "  3. Apply game-launch/configs/itch-io-config.json settings\n"
            "  4. (Optional) Create Steam App using game-launch/configs/steam-config.json\n"
            "  5. Add game-launch/configs/analytics-setup.js to your build\n"
            "  6. Announce using the approved social thread and press release\n"
        )
        lbl(inner, steps_text, 10, fg=C.TEXT, bg=C.BG, justify="left").pack(anchor="w")

        # actions
        acts = frm(self, bg=C.BG)
        acts.pack(fill="x", padx=20, pady=(0, 18))
        btn(acts, "← Store Setup", lambda: self.app.show_phase("store_setup"), style="dark").pack(
            side="left")
        self._deploy_btn = btn(acts, "  🚀  READY TO DEPLOY  ", self._deploy, style="green")
        self._deploy_btn.pack(side="right")
        self._deploy_btn.config(state="disabled")
        self._refresh_btn = btn(acts, "↺ Refresh", self._refresh, style="dark")
        self._refresh_btn.pack(side="right", padx=(0, 10))

        self._refresh()

    def _populate_checklist(self, parent):
        if not self.app.state:
            return

        checks = [
            ("Game name set",          bool(self.app.state.game_info.get("name"))),
            ("Game description set",   bool(self.app.state.game_info.get("description"))),
            ("Store listing approved", bool(self.app.state.marketing.get("store_listing", {}).get("final_text"))),
            ("Social copy approved",   bool(self.app.state.marketing.get("social_media", {}).get("final_text"))),
            ("Press release approved", bool(self.app.state.marketing.get("press_release", {}).get("final_text"))),
            ("Key art briefs approved",bool(self.app.state.marketing.get("key_art", {}).get("final_text"))),
            ("Itch.io config approved",bool(self.app.state.store_configs.get("itch_io", {}).get("approved"))),
            ("Steam config approved",  bool(self.app.state.store_configs.get("steam", {}).get("approved"))),
            ("Analytics config approved", bool(self.app.state.store_configs.get("analytics", {}).get("approved"))),
        ]
        # Check output files exist
        output_files = self.app.file_generator.list_output_files() if self.app.file_generator else []
        checks.append(("Output files generated", len(output_files) > 0))

        lbl(parent, "  Deployment Checklist", 11, "bold", fg=C.DIM, bg=C.BG).pack(
            anchor="w", pady=(0, 8))

        check_panel = frm(parent, bg=C.PANEL)
        check_panel.pack(fill="x", pady=(0, 8))

        for label, passed in checks:
            row = frm(check_panel, bg=C.PANEL)
            row.pack(fill="x", padx=12, pady=3)
            icon = "✓" if passed else "✗"
            color = C.SUCCESS if passed else C.ERROR
            lbl(row, f" {icon} ", 12, "bold", fg=color, bg=C.PANEL).pack(side="left")
            lbl(row, label, 10, fg=C.TEXT if passed else C.DIM, bg=C.PANEL).pack(side="left")
            self._check_rows.append({"label": label, "passed": passed})

    def _populate_files(self):
        for w in self._files_frame.winfo_children():
            w.destroy()
        if not self.app.file_generator:
            return
        files = self.app.file_generator.list_output_files()
        if not files:
            lbl(self._files_frame, "  No output files yet — complete store setup to generate them.",
                10, fg=C.DIM, bg=C.BG).pack(anchor="w")
            return
        size = self.app.file_generator.output_size()
        lbl(self._files_frame, f"  {len(files)} files  |  {fmt_size(size)}",
            9, fg=C.DIM, bg=C.BG).pack(anchor="w", pady=(0, 4))
        for f in files:
            lbl(self._files_frame, f"  📄 {f}", 9, fg=C.TEXT, bg=C.BG).pack(anchor="w")

    def _refresh(self):
        for w in self.winfo_children():
            if isinstance(w, ScrollableFrame):
                for c in w.inner.winfo_children():
                    c.destroy()
                self._check_rows = []
                self._populate_checklist(w.inner)
                sep(w.inner, "h").pack(fill="x", pady=12)
                lbl(w.inner, "  📁 Generated Output Files", 11, "bold", fg=C.DIM, bg=C.BG).pack(
                    anchor="w", pady=(0, 6))
                self._files_frame = frm(w.inner, bg=C.BG)
                self._files_frame.pack(fill="x", padx=4)
                self._populate_files()
                break

        all_green = all(r["passed"] for r in self._check_rows)
        self._deploy_btn.config(state="normal" if all_green else "disabled")
        if all_green:
            self._deploy_btn.config(text="  🚀  READY TO DEPLOY  ")
            self.app.statusbar.set("All systems green — ready to ship!", C.SUCCESS)
        else:
            remaining = sum(1 for r in self._check_rows if not r["passed"])
            self.app.statusbar.set(f"{remaining} items need attention before deploy", C.WARNING)

    def _deploy(self):
        gi = self.app.state.game_info
        name = gi.get("name", "your game")
        msg = (
            f"🚀 All systems ready for {name}!\n\n"
            "This pipeline is complete. Your next steps:\n\n"
            "  1. Export / build your game binary\n"
            "  2. Upload to Itch.io using game-launch/configs/itch-io-config.json\n"
            "  3. Deploy marketing assets from game-launch/marketing/\n"
            "  4. Fire the launch tweet from social-media.txt\n"
            "  5. Send press-release.txt to gaming press\n\n"
            "Good luck — ship it! 🎮"
        )
        messagebox.showinfo("🚀 Ready to Deploy", msg)
        self.app.state.complete_stage("deploy")
        self.app.timeline.update(self.app.state)
        self.app.statusbar.set(f"✓ {name} launch pipeline complete!", C.SUCCESS)


# ─────────────────────────────────────────────────────────────────────────────
# API key dialog
# ─────────────────────────────────────────────────────────────────────────────

class APIKeyDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("API Key Required")
        self.configure(bg=C.PANEL)
        self.resizable(False, False)
        self.result: Optional[str] = None
        self._build()
        self.transient(parent)
        self.grab_set()
        self.wait_window()

    def _build(self):
        frm(self, bg=C.PANEL, height=8).pack(fill="x")
        lbl(self, "  Anthropic API Key", 13, "bold", bg=C.PANEL).pack(anchor="w", padx=20)
        lbl(self, "  Enter your key from console.anthropic.com", 10, fg=C.DIM, bg=C.PANEL).pack(
            anchor="w", padx=20, pady=(4, 12))
        self._var = tk.StringVar()
        e = entry(self, textvariable=self._var, show="•", width=50)
        e.pack(padx=20, ipady=8, fill="x")
        e.bind("<Return>", lambda _: self._ok())
        row = frm(self, bg=C.PANEL)
        row.pack(fill="x", padx=20, pady=14)
        btn(row, "Save Key", self._ok, style="green").pack(side="right")
        btn(row, "Cancel", self.destroy, style="dark").pack(side="right", padx=(0, 8))
        lbl(self, "  Your key is saved to config.json in the pipeline folder.", 9,
            fg=C.DIM, bg=C.PANEL).pack(anchor="w", padx=20, pady=(0, 10))

    def _ok(self):
        v = self._var.get().strip()
        if not v:
            return
        self.result = v
        self.destroy()


# ─────────────────────────────────────────────────────────────────────────────
# Main application window
# ─────────────────────────────────────────────────────────────────────────────

_PHASE_MAP = {
    "dev":         DevPhase,
    "marketing":   MarketingPhase,
    "store_setup": StoreSetupPhase,
    "deploy":      DeployPhase,
}


class GameLaunchApp(tk.Tk):
    def __init__(self, game_path: Optional[str] = None):
        super().__init__()
        self.title("🎮 Game Launch Pipeline")
        self.geometry("1120x780")
        self.minsize(920, 620)
        self.configure(bg=C.BG)

        self.game_path = game_path
        self.state: Optional[PipelineState] = None
        self.api_client: Optional[ClaudeClient] = None
        self.file_generator: Optional[FileGenerator] = None
        self._current_phase: Optional[tk.Frame] = None

        self._configure_ttk()
        self._build_layout()
        self._load_config()

        # If a game path was given, try to resume existing state
        if game_path:
            self._try_resume(game_path)

    # ─── layout ───────────────────────────────────────────────────────────────

    def _configure_ttk(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TScrollbar", background=C.PANEL2, troughcolor=C.PANEL,
                    borderwidth=0, arrowcolor=C.DIM)

    def _build_layout(self):
        self.timeline = PipelineTimeline(self, self)
        self.timeline.pack(fill="x", side="top")

        self.statusbar = StatusBar(self)
        self.statusbar.pack(fill="x", side="bottom")

        self._content = frm(self, bg=C.BG)
        self._content.pack(fill="both", expand=True)

        # Default: show dev phase
        self.show_phase("dev")

    def show_phase(self, phase: str):
        if self._current_phase:
            self._current_phase.destroy()
            self._current_phase = None

        cls = _PHASE_MAP.get(phase, DevPhase)
        frame = cls(self._content, self)
        frame.pack(fill="both", expand=True)
        self._current_phase = frame

        if self.state:
            self.timeline.update(self.state)
            self.statusbar.set_right(f"Stage: {phase.replace('_', ' ').title()}")

    # ─── config & API key ─────────────────────────────────────────────────────

    def _config_path(self) -> Path:
        here = Path(__file__).resolve().parent.parent
        return here / "config.json"

    def _load_config(self):
        # 1. Try config.json
        cfg_path = self._config_path()
        if cfg_path.exists():
            try:
                cfg = json.loads(cfg_path.read_text())
                key = cfg.get("api_key", "")
                model = cfg.get("model", "claude-sonnet-4-6")
                if key and not key.startswith("sk-ant-YOUR"):
                    self.api_client = ClaudeClient(key, model)
                    self.statusbar.set("API key loaded from config.json", C.SUCCESS)
                    return
            except Exception:
                pass

        # 2. Try environment variable
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if key:
            self.api_client = ClaudeClient(key)
            self.statusbar.set("API key loaded from ANTHROPIC_API_KEY env var", C.SUCCESS)
            return

        # 3. Prompt user
        self.statusbar.set("No API key found — click here to add one", C.WARNING)
        self.after(300, self._prompt_api_key)

    def _prompt_api_key(self):
        dialog = APIKeyDialog(self)
        if dialog.result:
            self._save_api_key(dialog.result)
            self.api_client = ClaudeClient(dialog.result)
            self.statusbar.set("API key saved!", C.SUCCESS)

    def _save_api_key(self, key: str):
        cfg_path = self._config_path()
        cfg = {"api_key": key, "model": "claude-sonnet-4-6"}
        try:
            if cfg_path.exists():
                cfg = json.loads(cfg_path.read_text())
                cfg["api_key"] = key
        except Exception:
            pass
        cfg_path.write_text(json.dumps(cfg, indent=2))

    # ─── state resume ─────────────────────────────────────────────────────────

    def _try_resume(self, game_path: str):
        state = PipelineState(game_path)
        if state.load():
            self.state = state
            self.file_generator = FileGenerator(game_path)
            self.timeline.update(state)
            phase = state.current_stage
            self.show_phase(phase)
            self.statusbar.set(f"Resumed: {state.game_info.get('name', game_path)}", C.SUCCESS)
        else:
            # Fresh start — DevPhase will pick up game_path automatically
            self.show_phase("dev")
