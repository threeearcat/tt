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


class TranslatorGUI:
    """Tkinter GUI for tt."""

    def __init__(self, fixed_target=None, clip_mode=False, theme_name=None, config=None):
        import tkinter as tk
        import tkinter.font as tkfont

        self.tk = tk
        self.config = config or {}
        effective_theme = theme_name or self.config.get("theme", DEFAULT_THEME)
        self.theme = THEMES.get(effective_theme, THEMES[DEFAULT_THEME])
        self.font_size = self.config.get("font_size", DEFAULT_FONT_SIZE)

        self.root = tk.Tk()
        self.root.title("tt")
        self.root.geometry("700x500")
        self.root.minsize(300, 100)

        # Font setup
        self.font_family = "monospace"
        candidates = ["JetBrains Mono", "Noto Sans Mono CJK KR", "DejaVu Sans Mono"]
        if "font_family" in self.config:
            candidates.insert(0, self.config["font_family"])
        for candidate in candidates:
            if candidate in tkfont.families():
                self.font_family = candidate
                break

        self._create_widgets(fixed_target, clip_mode, effective_theme)
        self._bind_events()
        self.apply_theme()

        # Start clipboard polling
        self._prev_clip = get_clipboard() if clip_mode else ""
        self.root.after(500, self._poll_clipboard)

    def text_font(self):
        return (self.font_family, self.font_size)

    def ui_font(self, size=0):
        return (self.font_family, size or max(self.font_size - 2, 9))

    def _create_widgets(self, fixed_target, clip_mode, effective_theme):
        tk = self.tk

        # Top bar
        self.top_frame = tk.Frame(self.root, pady=6)
        self.top_frame.pack(fill="x", padx=12)

        self.target_label = tk.Label(self.top_frame, text="target:")
        self.target_label.pack(side="left")
        self.lang_var = tk.StringVar(value=fixed_target or "auto")
        self.lang_entry = tk.Entry(self.top_frame, textvariable=self.lang_var,
                                   width=6, bd=0, relief="flat", highlightthickness=1)
        self.lang_entry.pack(side="left", padx=(4, 0))

        self.clip_var = tk.BooleanVar(value=clip_mode)
        self.clip_check = tk.Checkbutton(self.top_frame, text="clipboard",
                                         variable=self.clip_var, highlightthickness=0)
        self.clip_check.pack(side="right")

        self.theme_var = tk.StringVar(value=effective_theme)
        self.theme_menu = tk.OptionMenu(self.top_frame, self.theme_var, *THEMES.keys())
        self.theme_menu.config(bd=0, relief="flat", highlightthickness=0)
        self.theme_menu["menu"].config(bd=0)
        self.theme_menu.pack(side="right", padx=(0, 8))

        # Status bar (pack before paned so it gets space first)
        self.status_var = tk.StringVar(value="Enter to translate | Shift+Enter for newline")
        self.status_label = tk.Label(self.root, textvariable=self.status_var,
                                     anchor="w", pady=4)
        self.status_label.pack(fill="x", padx=12, side="bottom")

        # Paned window
        self.paned = tk.PanedWindow(self.root, orient="vertical",
                                    sashwidth=4, sashrelief="flat", bd=0,
                                    opaqueresize=True)
        self.paned.pack(fill="both", expand=True, padx=12, pady=(4, 0))

        text_opts = dict(bd=0, relief="flat", highlightthickness=0,
                         wrap="word", padx=10, pady=8)

        # Input pane
        self.input_frame = tk.Frame(self.paned)
        self.input_text = tk.Text(self.input_frame, **text_opts)
        self.input_scroll = tk.Scrollbar(self.input_frame, command=self.input_text.yview,
                                         highlightthickness=0, bd=0, width=8)
        self.input_text.config(yscrollcommand=self.input_scroll.set)
        self.input_scroll.pack(side="right", fill="y")
        self.input_text.pack(fill="both", expand=True)
        self.paned.add(self.input_frame, minsize=60)

        # Output pane
        self.output_frame = tk.Frame(self.paned)
        self.output_text = tk.Text(self.output_frame, state="disabled", **text_opts)
        self.output_scroll = tk.Scrollbar(self.output_frame, command=self.output_text.yview,
                                          highlightthickness=0, bd=0, width=8)
        self.output_text.config(yscrollcommand=self.output_scroll.set)
        self.output_scroll.pack(side="right", fill="y")
        self.output_text.pack(fill="both", expand=True)
        self.paned.add(self.output_frame, minsize=60)

    def _bind_events(self):
        self.input_text.bind("<Return>", self._do_translate)
        self.input_text.bind("<Control-Return>", self._do_translate)
        self.input_text.bind("<Shift-Return>", lambda e: None)
        self.root.bind("<Control-Button-4>", self._zoom)
        self.root.bind("<Control-Button-5>", self._zoom)
        self.root.bind("<Control-MouseWheel>", self._zoom)
        self.root.bind("<Control-plus>", self._zoom_in)
        self.root.bind("<Control-equal>", self._zoom_in)
        self.root.bind("<Control-minus>", self._zoom_out)
        self.root.bind("<Control-0>", self._zoom_reset)
        self.theme_var.trace_add("write", self.apply_theme)

        def set_sash(_=None):
            h = self.paned.winfo_height()
            if h > 1:
                self.paned.sash_place(0, 0, h // 2)
        self.root.after(50, set_sash)
        self.paned.bind("<Configure>", set_sash)

        self.input_text.focus_set()

    def _set_output(self, text):
        self.output_text.config(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", text)
        self.output_text.config(state="disabled")

    def _get_target(self):
        lang = self.lang_var.get().strip()
        return lang if lang and lang != "auto" else None

    def _run_translate(self, text, prefix=""):
        import threading
        target = self._get_target()
        self.status_var.set(f"{prefix}translating..." if prefix else "translating...")

        def run():
            try:
                result = translate_auto(text, target)
                self.root.after(0, lambda: self._set_output(result))
                self.root.after(0, lambda: self.status_var.set(
                    f"{prefix}done" if prefix else "done"))
            except Exception as e:
                self.root.after(0, lambda: self._set_output(f"[error] {e}"))
                self.root.after(0, lambda: self.status_var.set(
                    f"{prefix}error" if prefix else "error"))

        threading.Thread(target=run, daemon=True).start()

    def _do_translate(self, _event=None):
        text = self.input_text.get("1.0", "end").strip()
        if not text:
            return "break"
        self._run_translate(text)
        return "break"

    def _poll_clipboard(self):
        if not self.clip_var.get():
            self._prev_clip = ""
            self.root.after(500, self._poll_clipboard)
            return
        current = get_clipboard()
        if current and current != self._prev_clip:
            self._prev_clip = current
            text = current.strip()
            if text:
                self.input_text.delete("1.0", "end")
                self.input_text.insert("1.0", text)
                self._run_translate(text, prefix="clipboard → ")
        self.root.after(500, self._poll_clipboard)

    def _zoom(self, event):
        if event.delta > 0 or event.num == 4:
            self.font_size = min(self.font_size + 1, 40)
        else:
            self.font_size = max(self.font_size - 1, 8)
        self._apply_zoom()

    def _zoom_in(self, _event=None):
        self.font_size = min(self.font_size + 1, 40)
        self._apply_zoom()
        return "break"

    def _zoom_out(self, _event=None):
        self.font_size = max(self.font_size - 1, 8)
        self._apply_zoom()
        return "break"

    def _zoom_reset(self, _event=None):
        self.font_size = self.config.get("font_size", DEFAULT_FONT_SIZE)
        self._apply_zoom()
        return "break"

    def _apply_zoom(self):
        self.apply_theme()
        self.status_var.set(f"font size: {self.font_size}")

    def apply_theme(self, *_args):
        t = THEMES.get(self.theme_var.get(), THEMES[DEFAULT_THEME])
        self.theme = t
        bg, bg2, fg = t["bg"], t["bg2"], t["fg"]
        fg_dim, accent, select = t["fg_dim"], t["accent"], t["select"]
        f, uf = self.text_font(), self.ui_font()
        self.root.configure(bg=bg)
        self.top_frame.configure(bg=bg)
        self.target_label.configure(bg=bg, fg=fg_dim, font=uf)
        self.lang_entry.configure(bg=bg2, fg=fg, insertbackground=fg,
                                  highlightbackground=bg2, highlightcolor=accent, font=uf)
        self.clip_check.configure(bg=bg, fg=fg_dim, selectcolor=bg2,
                                  activebackground=bg, activeforeground=fg, font=uf)
        self.theme_menu.configure(bg=bg2, fg=fg, activebackground=bg2,
                                  activeforeground=fg, font=uf)
        self.theme_menu["menu"].configure(bg=bg2, fg=fg, activebackground=accent,
                                          activeforeground=fg, font=uf)
        for w in (self.input_text, self.output_text):
            w.configure(bg=bg2, fg=fg, insertbackground=fg,
                        selectbackground=select, selectforeground=fg, font=f)
        for fr in (self.input_frame, self.output_frame):
            fr.configure(bg=bg2)
        for s in (self.input_scroll, self.output_scroll):
            s.configure(bg=bg2, troughcolor=bg2)
        self.paned.configure(bg=fg_dim)
        self.status_label.configure(bg=bg, fg=fg_dim,
                                    font=self.ui_font(max(self.font_size - 3, 8)))

    def run(self):
        self.root.mainloop()


def gui(fixed_target=None, clip_mode=False, theme_name=None, config=None):
    """Tkinter GUI mode."""
    app = TranslatorGUI(fixed_target, clip_mode, theme_name, config)
    app.run()


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
