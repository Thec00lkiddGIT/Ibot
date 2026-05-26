"""Native macOS GUI - stable layout (no canvas delete crashes)."""

from __future__ import annotations

import os
import tkinter as tk
from datetime import datetime
from tkinter import font as tkfont

from ibot.gui.commands_list import COMMANDS
from ibot.gui.icons import load_tk_icons
from ibot.runtime import get_runtime

BG = "#060a12"
BG2 = "#0c1220"
GLASS = "#121c30"
BORDER = "#243b5a"
TEXT = "#e8eef8"
MUTED = "#8b9bb8"
ACCENT = "#3b82f6"
SUCCESS = "#22c55e"
ERROR = "#ef4444"
INFO = "#60a5fa"
INPUT = "#0a101c"
VERSION = "1.0.0"


def _name() -> str:
    return os.environ.get("IBOT_DISPLAY_NAME", "Ibot")


from ibot.hostinfo import computer_handle


def _ago(iso: str) -> str:
    try:
        sec = max(0, int((datetime.now().astimezone() - datetime.fromisoformat(iso)).total_seconds()))
    except ValueError:
        return iso
    if sec < 60:
        return f"{sec}s ago"
    m = sec // 60
    return f"{m}m ago" if m < 60 else f"{m // 60}h ago"


class ClickLabel(tk.Label):
    def __init__(self, master, text, command, *, bg, fg=TEXT, hover=None, disabled=False, font=None) -> None:
        super().__init__(
            master, text=text, bg=bg, fg=fg if not disabled else MUTED,
            font=font, padx=14, pady=8,
            cursor="" if disabled else "hand2",
            highlightthickness=1, highlightbackground=BORDER,
        )
        self._cmd = command
        self._bg, self._hover = bg, hover or bg
        self._disabled = disabled
        if not disabled:
            self.bind("<Button-1>", lambda _e: command())
            self.bind("<Enter>", lambda _e: self.configure(bg=self._hover))
            self.bind("<Leave>", lambda _e: self.configure(bg=self._bg))

    def set_disabled(self, on: bool) -> None:
        self._disabled = on
        self.configure(fg=MUTED if on else TEXT, cursor="" if on else "hand2")
        if on:
            self.unbind("<Button-1>")
        else:
            self.bind("<Button-1>", lambda _e: self._cmd())


class IbotApp:
    def __init__(self) -> None:
        self.rt = get_runtime()
        self.last_event_id = 0
        self.page = "dashboard"

        self.root = tk.Tk()
        self.root.title("Ibot")
        self.root.geometry("1020x660")
        self.root.minsize(880, 540)
        self.root.configure(bg=BG)

        self.f_title = tkfont.Font(family="Helvetica Neue", size=22, weight="bold")
        self.f_head = tkfont.Font(family="Helvetica Neue", size=14, weight="bold")
        self.f_body = tkfont.Font(family="Helvetica Neue", size=12)
        self.f_small = tkfont.Font(family="Helvetica Neue", size=10)
        self.f_mono = tkfont.Font(family="Menlo", size=11)

        self._icons = load_tk_icons()
        if "win" in self._icons:
            try:
                self.root.iconphoto(True, self._icons["win"])
            except tk.TclError:
                pass

        # Canvas holds one inner frame - macOS paints Frame bg correctly this way.
        self.cv = tk.Canvas(self.root, bg=BG, highlightthickness=0, bd=0)
        self.cv.pack(fill=tk.BOTH, expand=True)
        self.body = tk.Frame(self.cv, bg=BG2, highlightthickness=0)
        self._body_win = self.cv.create_window(0, 0, window=self.body, anchor="nw")
        self.cv.bind("<Configure>", self._resize)

        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.after(400, self._tick)

    def _resize(self, event: tk.Event) -> None:
        self.cv.itemconfig(self._body_win, width=event.width, height=event.height)

    def _frame(self, parent, bg=BG2) -> tk.Frame:
        return tk.Frame(parent, bg=bg, highlightthickness=0)

    def _lbl(self, parent, text, *, fg=TEXT, bg=BG2, font_key="body", **kw) -> tk.Label:
        fonts = {"title": self.f_title, "heading": self.f_head, "body": self.f_body, "small": self.f_small}
        return tk.Label(
            parent, text=text, fg=fg, bg=bg,
            font=fonts.get(font_key, self.f_body),
            highlightthickness=0, **kw,
        )

    def _build(self) -> None:
        # Title bar
        bar = self._frame(self.body, "#0a0f18")
        bar.pack(fill=tk.X)
        dots = self._frame(bar, "#0a0f18")
        dots.pack(side=tk.LEFT, padx=14, pady=10)
        for c in ("#ef4444", "#eab308", "#22c55e"):
            tk.Label(dots, text="●", fg=c, bg="#0a0f18", font=self.f_small).pack(side=tk.LEFT, padx=3)
        title = self._frame(bar, "#0a0f18")
        title.pack(side=tk.LEFT, padx=8)
        if "title" in self._icons:
            tk.Label(title, image=self._icons["title"], bg="#0a0f18").pack(side=tk.LEFT)
        self._lbl(title, " Ibot", bg="#0a0f18", font_key="heading").pack(side=tk.LEFT)

        shell = self._frame(self.body, BG2)
        shell.pack(fill=tk.BOTH, expand=True)

        # Sidebar
        side = self._frame(shell, "#080e18")
        side.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        self.nav_btns: dict[str, tk.Label] = {}
        for key, icon in (("dashboard", "▦"), ("commands", "⌘"), ("perms", "⛨")):
            b = tk.Label(
                side, text=icon, width=2, pady=10, cursor="hand2",
                bg=GLASS if key == "dashboard" else "#080e18",
                fg=ACCENT if key == "dashboard" else MUTED,
                font=self.f_head,
            )
            b.pack(pady=4, padx=6, fill=tk.X)
            b.bind("<Button-1>", lambda _e, k=key: self._page(k))
            self.nav_btns[key] = b

        self.main = self._frame(shell, BG2)
        self.main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.pages: dict[str, tk.Frame] = {
            "dashboard": self._page_dashboard(),
            "commands": self._page_commands(),
            "perms": self._page_perms(),
        }
        self._page("dashboard")

    def _page(self, name: str) -> None:
        self.page = name
        for k, b in self.nav_btns.items():
            b.configure(bg=GLASS if k == name else "#080e18", fg=ACCENT if k == name else MUTED)
        for k, f in self.pages.items():
            f.pack(fill=tk.BOTH, expand=True) if k == name else f.pack_forget()

    def _page_dashboard(self) -> tk.Frame:
        p = self._frame(self.main, BG2)
        self._lbl(p, f"Hello, {_name()} 👋", bg=BG2, font_key="title").pack(anchor=tk.W, pady=(0, 12))

        row = self._frame(p, BG2)
        row.pack(fill=tk.BOTH, expand=True)
        row.columnconfigure(0, weight=3)
        row.columnconfigure(1, weight=2)
        row.rowconfigure(0, weight=1)

        left = self._frame(row, GLASS)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8), ipadx=16, ipady=16)

        head = self._frame(left, GLASS)
        head.pack(fill=tk.X)
        if "avatar" in self._icons:
            tk.Label(head, image=self._icons["avatar"], bg=GLASS).pack(side=tk.LEFT)
        else:
            tk.Label(head, text=_name()[:2].upper(), bg=ACCENT, fg="white", font=self.f_head, width=4, height=2).pack(side=tk.LEFT)
        meta = self._frame(head, GLASS)
        meta.pack(side=tk.LEFT, padx=12)
        self._lbl(meta, _name(), bg=GLASS, font_key="heading").pack(anchor=tk.W)
        self._lbl(meta, f"@{computer_handle()}", fg=MUTED, bg=GLASS, font_key="small").pack(anchor=tk.W)
        badges = self._frame(meta, GLASS)
        badges.pack(anchor=tk.W, pady=(8, 0))
        self.lbl_status = self._lbl(badges, "Stopped", fg=MUTED, bg=GLASS, font_key="small")
        self.lbl_status.pack(side=tk.LEFT, padx=(0, 10))
        self.lbl_fda = self._lbl(badges, "FDA ...", fg=MUTED, bg=GLASS, font_key="small")
        self.lbl_fda.pack(side=tk.LEFT)

        actions = self._frame(left, GLASS)
        actions.pack(fill=tk.X, pady=14)
        self.btn_start = ClickLabel(actions, "Start bot", self._start, bg=ACCENT, fg="white", hover="#2563eb", font=self.f_body)
        self.btn_start.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_stop = ClickLabel(actions, "Stop", self._stop, bg=GLASS, hover="#1a2740", font=self.f_body, disabled=True)
        self.btn_stop.pack(side=tk.LEFT)

        self.lbl_rowid = self._lbl(left, "Last ROWID: -", fg=MUTED, bg=GLASS, font_key="small")
        self.lbl_rowid.pack(anchor=tk.W)
        self.lbl_host = self._lbl(left, "Host app: -", fg=MUTED, bg=GLASS, font_key="small")
        self.lbl_host.pack(anchor=tk.W, pady=(4, 0))
        self.lbl_counts = self._lbl(left, "0 commands · 0 seen", bg=GLASS)
        self.lbl_counts.pack(anchor=tk.W, pady=(8, 0))

        right = self._frame(row, GLASS)
        right.grid(row=0, column=1, sticky="nsew", ipadx=14, ipady=14)
        self._lbl(right, "🔔 Notification Center", bg=GLASS, font_key="heading").pack(anchor=tk.W, pady=(0, 8))
        self.notify = tk.Text(
            right, bg=INPUT, fg=TEXT, font=self.f_small, wrap=tk.WORD, relief=tk.FLAT,
            padx=12, pady=10, state=tk.DISABLED, highlightthickness=1, highlightbackground=BORDER,
        )
        self.notify.pack(fill=tk.BOTH, expand=True)
        self.notify.tag_configure("info", foreground=INFO)
        self.notify.tag_configure("success", foreground=SUCCESS)
        self.notify.tag_configure("error", foreground=ERROR)
        self.notify.tag_configure("meta", foreground=MUTED)

        bottom = self._frame(p, GLASS)
        bottom.pack(fill=tk.X, pady=(12, 0), ipadx=12, ipady=10)
        self.lbl_ver = self._lbl(bottom, f"v{VERSION}", fg=MUTED, bg=GLASS, font_key="small")
        self.lbl_ver.pack(side=tk.LEFT)

        self.var_self = tk.BooleanVar(value=False)
        self.var_verbose = tk.BooleanVar(value=True)
        self.var_catchup = tk.BooleanVar(value=False)
        toggles = self._frame(bottom, GLASS)
        toggles.pack(side=tk.RIGHT)
        for text, var, key in (
            ("React to my messages (--self)", self.var_self, "include_self"),
            ("Verbose logging", self.var_verbose, "verbose"),
            ("Catch up from saved state", self.var_catchup, "catch_up"),
        ):
            tk.Checkbutton(
                toggles, text=text, variable=var,
                command=lambda k=key, v=var: self.rt.update_settings(**{k: v.get()}),
                bg=GLASS, fg=TEXT, selectcolor=INPUT,
                activebackground=GLASS, activeforeground=TEXT,
                font=self.f_small, highlightthickness=0,
            ).pack(side=tk.LEFT, padx=8)

        return p

    def _page_commands(self) -> tk.Frame:
        p = self._frame(self.main, BG2)
        self._lbl(p, "Commands", bg=BG2, font_key="title").pack(anchor=tk.W)
        box = tk.Text(p, bg=GLASS, fg=TEXT, font=self.f_mono, relief=tk.FLAT, padx=14, pady=12,
                      highlightthickness=1, highlightbackground=BORDER)
        box.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        for n, h in COMMANDS:
            box.insert(tk.END, f"!{n:<12} {h}\n")
        box.configure(state=tk.DISABLED)
        return p

    def _page_perms(self) -> tk.Frame:
        p = self._frame(self.main, BG2)
        self._lbl(p, "Permissions", bg=BG2, font_key="title").pack(anchor=tk.W, pady=(0, 8))
        self.perm_box = tk.Text(
            p, bg=GLASS, fg=TEXT, font=self.f_body, relief=tk.FLAT, padx=14, pady=12,
            wrap=tk.WORD, highlightthickness=1, highlightbackground=BORDER,
        )
        self.perm_box.pack(fill=tk.BOTH, expand=True)
        return p

    def _start(self) -> None:
        self.rt.start()

    def _stop(self) -> None:
        self.rt.stop()

    def _refresh(self) -> None:
        s = self.rt.status()
        running = s["running"]
        self.btn_start.set_disabled(running)
        self.btn_stop.set_disabled(not running)
        self.lbl_status.configure(text="Running" if running else "Stopped", fg=ACCENT if running else MUTED)
        self.lbl_fda.configure(
            text="FDA OK" if s["fda_ok"] else "FDA missing",
            fg=SUCCESS if s["fda_ok"] else ERROR,
        )
        self.lbl_rowid.configure(text=f"Last ROWID: {s['last_rowid']}")
        self.lbl_host.configure(text=f"Host app: {s['fda_host']}")
        self.lbl_counts.configure(text=f"{s['commands_used']} commands · {s['messages_seen']} seen")
        self.lbl_ver.configure(text=f"v{VERSION}  ·  {s['commands_used']} commands used")
        self.var_self.set(bool(s.get("include_self")))
        self.var_verbose.set(bool(s.get("verbose", True)))
        self.var_catchup.set(bool(s.get("catch_up")))

        self.perm_box.configure(state=tk.NORMAL)
        self.perm_box.delete("1.0", tk.END)
        self.perm_box.insert("1.0", (
            f"Full Disk Access\n"
            f"{'OK - chat.db readable' if s['fda_ok'] else 'Missing - add ' + s['fda_host']}\n\n"
            f"Automation (Messages)\n{s['automation_msg']}\n"
        ))
        self.perm_box.configure(state=tk.DISABLED)

        for ev in self.rt.events_since(self.last_event_id):
            self.last_event_id = max(self.last_event_id, ev["id"])
            kind = ev.get("kind", "info")
            tag = kind if kind in ("success", "error") else "info"
            self.notify.configure(state=tk.NORMAL)
            self.notify.insert(tk.END, f"{ev['title']}\n", tag)
            self.notify.insert(tk.END, f"{ev['body']}\n", "meta")
            self.notify.insert(tk.END, f"{ev.get('source', 'Ibot')} · {_ago(ev['ts'])}\n\n", "meta")
            self.notify.see(tk.END)
            self.notify.configure(state=tk.DISABLED)

    def _tick(self) -> None:
        try:
            self._refresh()
        except Exception as exc:  # noqa: BLE001
            self.notify.configure(state=tk.NORMAL)
            self.notify.insert(tk.END, f"Error: {exc}\n", "error")
            self.notify.configure(state=tk.DISABLED)
        self.root.after(800, self._tick)

    def _close(self) -> None:
        self.rt.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def run_app() -> None:
    IbotApp().run()
