#!/usr/bin/env -S python3 -u
"""tt - Terminal Translator using Google Translate."""

import argparse
import json
import os
import platform
import readline  # noqa: F401 - enables input() line editing
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
TIMEOUT = 5
MAX_RETRIES = 2

THEMES = {
    "gruvbox-dark": {
        "bg": "#1d2021", "bg2": "#282828", "fg": "#ebdbb2",
        "fg_dim": "#928374", "accent": "#83a598", "select": "#3c3836",
    },
    "gruvbox-light": {
        "bg": "#fbf1c7", "bg2": "#f2e5bc", "fg": "#3c3836",
        "fg_dim": "#928374", "accent": "#427b58", "select": "#d5c4a1",
    },
    "dracula": {
        "bg": "#21222c", "bg2": "#282a36", "fg": "#f8f8f2",
        "fg_dim": "#6272a4", "accent": "#bd93f9", "select": "#44475a",
    },
    "nord": {
        "bg": "#2e3440", "bg2": "#3b4252", "fg": "#eceff4",
        "fg_dim": "#4c566a", "accent": "#88c0d0", "select": "#434c5e",
    },
    "catppuccin-mocha": {
        "bg": "#1e1e2e", "bg2": "#313244", "fg": "#cdd6f4",
        "fg_dim": "#6c7086", "accent": "#cba6f7", "select": "#45475a",
    },
    "catppuccin-latte": {
        "bg": "#eff1f5", "bg2": "#e6e9ef", "fg": "#4c4f69",
        "fg_dim": "#9ca0b0", "accent": "#8839ef", "select": "#ccd0da",
    },
    "solarized-dark": {
        "bg": "#002b36", "bg2": "#073642", "fg": "#839496",
        "fg_dim": "#586e75", "accent": "#268bd2", "select": "#073642",
    },
    "solarized-light": {
        "bg": "#fdf6e3", "bg2": "#eee8d5", "fg": "#657b83",
        "fg_dim": "#93a1a1", "accent": "#268bd2", "select": "#eee8d5",
    },
    "tokyo-night": {
        "bg": "#1a1b26", "bg2": "#24283b", "fg": "#c0caf5",
        "fg_dim": "#565f89", "accent": "#7aa2f7", "select": "#33467c",
    },
    "rose-pine": {
        "bg": "#191724", "bg2": "#1f1d2e", "fg": "#e0def4",
        "fg_dim": "#6e6a86", "accent": "#c4a7e7", "select": "#26233a",
    },
    "kanagawa": {
        "bg": "#1f1f28", "bg2": "#2a2a37", "fg": "#dcd7ba",
        "fg_dim": "#727169", "accent": "#7e9cd8", "select": "#2d4f67",
    },
    "everforest": {
        "bg": "#272e33", "bg2": "#2d353b", "fg": "#d3c6aa",
        "fg_dim": "#859289", "accent": "#a7c080", "select": "#3d484d",
    },
}
DEFAULT_THEME = "gruvbox-dark"
DEFAULT_FONT_SIZE = 20
CONFIG_PATH = os.path.expanduser("~/.config/tt/config.json")


def load_config():
    """Load config from ~/.config/tt/config.json. Returns {} if not found."""
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def translate(text, target="ko", source="auto"):
    """Translate text. Returns (translated_text, detected_source_lang)."""
    params = urllib.parse.urlencode({
        "client": "gtx",
        "sl": source,
        "tl": target,
        "dt": "t",
        "q": text,
    })
    url = f"{TRANSLATE_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    last_err = None
    for _ in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
            translated = "".join(part[0] for part in data[0] if part[0])
            detected = data[2] if len(data) > 2 else source
            return translated, detected
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RuntimeError("rate limited by Google Translate, try again later") from e
            raise RuntimeError(f"HTTP {e.code} from Google Translate") from e
        except urllib.error.URLError as e:
            last_err = RuntimeError(f"network error: {e.reason}")
            time.sleep(0.3)
        except socket.timeout:
            last_err = RuntimeError("request timed out")
            time.sleep(0.3)
        except (json.JSONDecodeError, IndexError, TypeError) as e:
            raise RuntimeError("unexpected response from Google Translate") from e
        except Exception as e:
            last_err = RuntimeError(f"translation failed: {e}")
            time.sleep(0.3)
    raise last_err


def auto_target(text):
    """Determine target language: ko input -> en, otherwise -> ko."""
    for ch in text:
        if "\uac00" <= ch <= "\ud7a3":  # Hangul syllables
            return "en"
    return "ko"


def translate_auto(text, fixed_target=None):
    """Translate with auto-toggle unless fixed_target is set."""
    target = fixed_target if fixed_target else auto_target(text)
    translated, detected = translate(text, target=target)
    return translated


def repl(fixed_target=None):
    """Interactive REPL mode."""
    label = fixed_target if fixed_target else "auto"
    print(f"tt ({label}) | :q to quit")
    while True:
        try:
            text = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if not text:
            continue
        if text == ":q":
            break
        try:
            print(translate_auto(text, fixed_target))
        except Exception as e:
            print(f"[error] {e}", file=sys.stderr)


def _ensure_display():
    """Set DISPLAY and XAUTHORITY for xclip in tmux/tty sessions."""
    if platform.system() != "Linux":
        return
    if not os.environ.get("DISPLAY"):
        try:
            out = subprocess.run(
                ["pgrep", "-a", "Xorg"], capture_output=True, text=True, timeout=2
            ).stdout
            for line in out.splitlines():
                for token in line.split():
                    if token.startswith(":"):
                        os.environ["DISPLAY"] = token.split()[0]
                        break
                if os.environ.get("DISPLAY"):
                    break
            else:
                os.environ["DISPLAY"] = ":0"
        except Exception:
            os.environ["DISPLAY"] = ":0"
    if not os.environ.get("XAUTHORITY"):
        # GDM stores Xauthority here; other DMs may differ
        candidates = [
            f"/run/user/{os.getuid()}/gdm/Xauthority",
            os.path.expanduser("~/.Xauthority"),
        ]
        for path in candidates:
            if os.path.exists(path):
                os.environ["XAUTHORITY"] = path
                break


def get_clipboard():
    """Read clipboard content. Supports macOS and Linux."""
    system = platform.system()
    try:
        if system == "Darwin":
            return subprocess.run(
                ["pbpaste"], capture_output=True, text=True, timeout=2
            ).stdout
        else:
            _ensure_display()
            return subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True, text=True, timeout=2
            ).stdout
    except FileNotFoundError:
        cmd = "pbpaste" if system == "Darwin" else "xclip"
        print(f"[error] {cmd} not found", file=sys.stderr)
        sys.exit(1)
    except Exception:
        return ""


def gui(fixed_target=None, clip_mode=False, theme_name=None, config=None):
    """Tkinter GUI mode."""
    import tkinter as tk
    import tkinter.font as tkfont
    import threading

    config = config or {}
    effective_theme = theme_name or config.get("theme", DEFAULT_THEME)
    theme = [THEMES.get(effective_theme, THEMES[DEFAULT_THEME])]
    BG = theme[0]["bg"]
    BG2 = theme[0]["bg2"]
    FG = theme[0]["fg"]
    FG_DIM = theme[0]["fg_dim"]
    ACCENT = theme[0]["accent"]
    SELECT = theme[0]["select"]

    root = tk.Tk()
    root.title("tt")
    root.geometry("700x500")
    root.minsize(300, 100)
    root.configure(bg=BG)

    # Font setup - prefer good CJK fonts
    font_size = [config.get("font_size", DEFAULT_FONT_SIZE)]
    font_family = "monospace"
    candidates = ["JetBrains Mono", "Noto Sans Mono CJK KR", "DejaVu Sans Mono"]
    if "font_family" in config:
        candidates.insert(0, config["font_family"])
    for candidate in candidates:
        if candidate in tkfont.families():
            font_family = candidate
            break

    def text_font():
        return (font_family, font_size[0])

    def ui_font(size=0):
        return (font_family, size or max(font_size[0] - 2, 9))

    # Top bar
    top_frame = tk.Frame(root, bg=BG, pady=6)
    top_frame.pack(fill="x", padx=12)

    target_label = tk.Label(top_frame, text="target:", bg=BG, fg=FG_DIM,
                            font=ui_font())
    target_label.pack(side="left")
    lang_var = tk.StringVar(value=fixed_target or "auto")
    lang_entry = tk.Entry(top_frame, textvariable=lang_var, width=6,
                          bg=BG2, fg=FG, insertbackground=FG,
                          font=ui_font(), bd=0, relief="flat",
                          highlightthickness=1, highlightbackground=BG2,
                          highlightcolor=ACCENT)
    lang_entry.pack(side="left", padx=(4, 0))

    clip_var = tk.BooleanVar(value=clip_mode)
    clip_check = tk.Checkbutton(top_frame, text="clipboard", variable=clip_var,
                                bg=BG, fg=FG_DIM, selectcolor=BG2,
                                activebackground=BG, activeforeground=FG,
                                font=ui_font(), highlightthickness=0)
    clip_check.pack(side="right")

    theme_var = tk.StringVar(value=theme_name or DEFAULT_THEME)
    theme_menu = tk.OptionMenu(top_frame, theme_var, *THEMES.keys())
    theme_menu.config(bg=BG2, fg=FG, font=ui_font(), bd=0, relief="flat",
                      highlightthickness=0, activebackground=BG2, activeforeground=FG)
    theme_menu["menu"].config(bg=BG2, fg=FG, font=ui_font(),
                              activebackground=ACCENT, activeforeground=FG, bd=0)
    theme_menu.pack(side="right", padx=(0, 8))

    # Paned window for resizable input/output split
    paned = tk.PanedWindow(root, orient="vertical", bg=FG_DIM,
                           sashwidth=4, sashrelief="flat", bd=0,
                           opaqueresize=True)
    paned.pack(fill="both", expand=True, padx=12, pady=(4, 0))

    text_opts = dict(bg=BG2, fg=FG, insertbackground=FG,
                     selectbackground=SELECT, selectforeground=FG,
                     font=text_font(), bd=0, relief="flat",
                     highlightthickness=0, wrap="word",
                     padx=10, pady=8)

    # Input pane
    input_frame = tk.Frame(paned, bg=BG2)
    input_text = tk.Text(input_frame, **text_opts)
    input_scroll = tk.Scrollbar(input_frame, command=input_text.yview,
                                bg=BG2, troughcolor=BG2, highlightthickness=0,
                                bd=0, width=8)
    input_text.config(yscrollcommand=input_scroll.set)
    input_scroll.pack(side="right", fill="y")
    input_text.pack(fill="both", expand=True)
    paned.add(input_frame, minsize=60)

    # Output pane
    output_frame = tk.Frame(paned, bg=BG2)
    output_text = tk.Text(output_frame, state="disabled", **text_opts)
    output_scroll = tk.Scrollbar(output_frame, command=output_text.yview,
                                 bg=BG2, troughcolor=BG2, highlightthickness=0,
                                 bd=0, width=8)
    output_text.config(yscrollcommand=output_scroll.set)
    output_scroll.pack(side="right", fill="y")
    output_text.pack(fill="both", expand=True)
    paned.add(output_frame, minsize=60)

    # Status bar
    status_var = tk.StringVar(value="Enter to translate | Shift+Enter for newline")
    status_label = tk.Label(root, textvariable=status_var, bg=BG,
                            fg=FG_DIM, font=ui_font(10), anchor="w", pady=4)
    status_label.pack(fill="x", padx=12, side="bottom")

    def set_output(text):
        output_text.config(state="normal")
        output_text.delete("1.0", "end")
        output_text.insert("1.0", text)
        output_text.config(state="disabled")

    def get_target():
        lang = lang_var.get().strip()
        return lang if lang and lang != "auto" else None

    def do_translate(_event=None):
        text = input_text.get("1.0", "end").strip()
        if not text:
            return "break"
        target = get_target()
        status_var.set("translating...")

        def run():
            try:
                result = translate_auto(text, target)
                root.after(0, lambda: set_output(result))
                root.after(0, lambda: status_var.set("done"))
            except Exception as e:
                root.after(0, lambda: set_output(f"[error] {e}"))
                root.after(0, lambda: status_var.set("error"))

        threading.Thread(target=run, daemon=True).start()
        return "break"

    # Clipboard monitoring
    prev_clip = [get_clipboard() if clip_mode else ""]

    def poll_clipboard():
        if not clip_var.get():
            prev_clip[0] = ""
            root.after(500, poll_clipboard)
            return
        current = get_clipboard()
        if current and current != prev_clip[0]:
            prev_clip[0] = current
            text = current.strip()
            if text:
                input_text.delete("1.0", "end")
                input_text.insert("1.0", text)
                target = get_target()
                status_var.set("clipboard → translating...")

                def run():
                    try:
                        result = translate_auto(text, target)
                        root.after(0, lambda: set_output(result))
                        root.after(0, lambda: status_var.set("clipboard → done"))
                    except Exception as e:
                        root.after(0, lambda: set_output(f"[error] {e}"))
                        root.after(0, lambda: status_var.set("clipboard → error"))

                threading.Thread(target=run, daemon=True).start()
        root.after(500, poll_clipboard)

    root.after(500, poll_clipboard)

    def apply_zoom():
        f = text_font()
        uf = ui_font()
        input_text.config(font=f)
        output_text.config(font=f)
        target_label.config(font=uf)
        lang_entry.config(font=uf)
        clip_check.config(font=uf)
        status_label.config(font=ui_font(max(font_size[0] - 3, 8)))
        status_var.set(f"font size: {font_size[0]}")

    def zoom(event):
        if event.delta > 0 or event.num == 4:
            font_size[0] = min(font_size[0] + 1, 40)
        else:
            font_size[0] = max(font_size[0] - 1, 8)
        apply_zoom()

    def zoom_in(_event=None):
        font_size[0] = min(font_size[0] + 1, 40)
        apply_zoom()
        return "break"

    def zoom_out(_event=None):
        font_size[0] = max(font_size[0] - 1, 8)
        apply_zoom()
        return "break"

    def zoom_reset(_event=None):
        font_size[0] = config.get("font_size", DEFAULT_FONT_SIZE)
        apply_zoom()
        return "break"

    def apply_theme(*_args):
        t = THEMES.get(theme_var.get(), THEMES[DEFAULT_THEME])
        theme[0] = t
        bg, bg2, fg = t["bg"], t["bg2"], t["fg"]
        fg_dim, accent, select = t["fg_dim"], t["accent"], t["select"]
        root.configure(bg=bg)
        top_frame.configure(bg=bg)
        target_label.configure(bg=bg, fg=fg_dim)
        lang_entry.configure(bg=bg2, fg=fg, insertbackground=fg,
                             highlightbackground=bg2, highlightcolor=accent)
        clip_check.configure(bg=bg, fg=fg_dim, selectcolor=bg2,
                             activebackground=bg, activeforeground=fg)
        theme_menu.configure(bg=bg2, fg=fg, activebackground=bg2, activeforeground=fg)
        theme_menu["menu"].configure(bg=bg2, fg=fg, activebackground=accent,
                                     activeforeground=fg)
        for w in (input_text, output_text):
            w.configure(bg=bg2, fg=fg, insertbackground=fg,
                        selectbackground=select, selectforeground=fg)
        for f in (input_frame, output_frame):
            f.configure(bg=bg2)
        for s in (input_scroll, output_scroll):
            s.configure(bg=bg2, troughcolor=bg2)
        paned.configure(bg=fg_dim)
        status_label.configure(bg=bg, fg=fg_dim)

    theme_var.trace_add("write", apply_theme)

    input_text.bind("<Return>", do_translate)
    input_text.bind("<Control-Return>", do_translate)
    input_text.bind("<Shift-Return>", lambda e: None)  # allow newline
    root.bind("<Control-Button-4>", zoom)   # Linux scroll up
    root.bind("<Control-Button-5>", zoom)   # Linux scroll down
    root.bind("<Control-MouseWheel>", zoom) # macOS/Windows
    root.bind("<Control-plus>", zoom_in)
    root.bind("<Control-equal>", zoom_in)
    root.bind("<Control-minus>", zoom_out)
    root.bind("<Control-0>", zoom_reset)

    # Keep sash at 50% on resize
    def set_sash(_=None):
        h = paned.winfo_height()
        if h > 1:
            paned.sash_place(0, 0, h // 2)
    root.after(50, set_sash)
    paned.bind("<Configure>", set_sash)

    input_text.focus_set()
    root.mainloop()


def main():
    config = load_config()

    parser = argparse.ArgumentParser(
        description="tt - Terminal Translator",
        usage="tt [text] | tt --clip | tt --repl | tt -t <lang> [text]",
    )
    parser.add_argument("text", nargs="*", help="text to translate")
    parser.add_argument("-t", "--target", default=None, help="target language (default: auto-toggle ko/en)")
    parser.add_argument("--clip", action="store_true", help="clipboard monitoring mode")
    parser.add_argument("--repl", action="store_true", help="interactive REPL mode")
    parser.add_argument("--theme", default=None,
                        choices=list(THEMES.keys()),
                        help=f"color theme (default: {DEFAULT_THEME})")
    args = parser.parse_args()

    target = args.target or config.get("target")

    if args.clip and not args.text:
        gui(target, clip_mode=True, theme_name=args.theme, config=config)
    elif args.text:
        try:
            print(translate_auto(" ".join(args.text), target))
        except Exception as e:
            print(f"[error] {e}", file=sys.stderr)
            sys.exit(1)
    elif not sys.stdin.isatty():
        text = sys.stdin.read().strip()
        if text:
            try:
                print(translate_auto(text, target))
            except Exception as e:
                print(f"[error] {e}", file=sys.stderr)
                sys.exit(1)
        else:
            gui(target, theme_name=args.theme, config=config)
    elif args.repl:
        repl(target)
    else:
        gui(target, theme_name=args.theme, config=config)


if __name__ == "__main__":
    main()
