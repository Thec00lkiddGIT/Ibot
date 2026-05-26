"""macOS tkinter helpers - Canvas embedding fixes dark backgrounds."""

from __future__ import annotations

import tkinter as tk


def make_panel(
    parent: tk.Misc,
    *,
    bg: str,
) -> tuple[tk.Frame, tk.Frame]:
    """Create outer (packable) + inner (child widgets) frame pair."""
    outer = tk.Frame(parent, bg=bg, highlightthickness=0)

    canvas = tk.Canvas(
        outer,
        bg=bg,
        highlightthickness=0,
        borderwidth=0,
    )
    canvas.pack(fill=tk.BOTH, expand=True)

    inner = tk.Frame(canvas, bg=bg, highlightthickness=0)
    win = canvas.create_window(0, 0, window=inner, anchor="nw")

    def _on_resize(event: tk.Event) -> None:
        if event.widget is not outer:
            return
        w, h = event.width, event.height
        if w < 2 or h < 2:
            return
        canvas.configure(width=w, height=h)
        canvas.itemconfig(win, width=w, height=h)

    outer.bind("<Configure>", _on_resize)
    return outer, inner


def add_panel(
    parent: tk.Misc,
    *,
    bg: str,
    **pack_kw,
) -> tk.Frame:
    """Add a canvas-backed panel; returns inner frame for widgets."""
    outer, inner = make_panel(parent, bg=bg)
    outer.pack(**pack_kw)
    inner._panel_outer = outer  # type: ignore[attr-defined]
    return inner


def show_panel(inner: tk.Frame) -> None:
    outer = getattr(inner, "_panel_outer", None)
    if outer is not None:
        outer.pack(fill=tk.BOTH, expand=True)


def hide_panel(inner: tk.Frame) -> None:
    outer = getattr(inner, "_panel_outer", None)
    if outer is not None:
        outer.pack_forget()
