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
MW_API_URL = "https://www.dictionaryapi.com/api/v3/references/collegiate/json"
MW_CONFIG_PATH = os.path.expanduser("~/.config/english-vocab/config.json")
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
TIMEOUT = 5
MAX_RETRIES = 2


def _load_mw_key():
    """Load Merriam-Webster API key from config, or return None."""
    try:
        with open(MW_CONFIG_PATH) as f:
            return json.load(f)["merriam_webster"]["dictionary_key"]
    except Exception:
        return None


MW_KEY = _load_mw_key()


def is_single_word(text):
    """Check if text is a single English word."""
    return bool(text) and len(text.split()) == 1 and text.isascii() and text.isalpha()


def mw_lookup(word):
    """Look up a word in Merriam-Webster. Returns formatted string or None."""
    if not MW_KEY:
        return None
    url = f"{MW_API_URL}/{urllib.parse.quote(word)}?key={MW_KEY}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None

    if not data or not isinstance(data[0], dict):
        if data and isinstance(data[0], str):
            return f"Word not found. Suggestions: {', '.join(data[:5])}"
        return None

    lines = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        word_id = entry.get("meta", {}).get("id", word).split(":")[0]
        pos = entry.get("fl", "")
        pron = ""
        try:
            pron = entry["hwi"]["prs"][0]["mw"]
        except (KeyError, IndexError, TypeError):
            pass

        header = word_id
        if pron:
            header += f"  /{pron}/"
        if pos:
            header += f"  ({pos})"
        lines.append(header)

        for i, d in enumerate(entry.get("shortdef", []), 1):
            lines.append(f"  {i}. {d}")

        for def_block in entry.get("def", []):
            for sseq in def_block.get("sseq", []):
                for sense_group in sseq:
                    if not isinstance(sense_group, list) or len(sense_group) < 2:
                        continue
                    sense = sense_group[1]
                    if isinstance(sense, dict):
                        for dt_item in sense.get("dt", []):
                            if isinstance(dt_item, list) and len(dt_item) >= 2:
                                if dt_item[0] == "vis":
                                    for vis in dt_item[1]:
                                        ex = vis.get("t", "")
                                        ex = ex.replace("{it}", "_").replace("{/it}", "_")
                                        ex = ex.replace("{wi}", "").replace("{/wi}", "")
                                        ex = ex.replace("{phrase}", "").replace("{/phrase}", "")
                                        lines.append(f"     e.g. {ex}")
        lines.append("")
    return "\n".join(lines).strip() if lines else None

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


def save_config(cfg):
    """Save config to ~/.config/tt/config.json."""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


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


def translate_auto(text, fixed_target=None, dict_mode="both"):
    """Translate with auto-toggle unless fixed_target is set.

    dict_mode: "both" (translate+dict), "dict" (dict only), "off" (translate only)
    """
    word = text.strip()
    use_dict = MW_KEY and dict_mode != "off" and is_single_word(word)

    if use_dict and dict_mode == "dict":
        defn = mw_lookup(word.lower())
        return defn if defn else f"No dictionary entry for '{word}'"

    target = fixed_target if fixed_target else auto_target(text)
    translated, detected = translate(text, target=target)
    result = translated

    if use_dict:
        defn = mw_lookup(word.lower())
        if defn:
            result += "\n\n── dictionary ──\n" + defn
    return result


def repl(fixed_target=None, dict_mode="both"):
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
            print(translate_auto(text, fixed_target, dict_mode=dict_mode))
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

    def __init__(self, fixed_target=None, clip_mode=False, theme_name=None,
                 config=None, dict_mode="both"):
        import tkinter as tk
        import tkinter.font as tkfont

        self.tk = tk
        self.config = config or {}
        effective_theme = theme_name or self.config.get("theme", DEFAULT_THEME)
        self.theme = THEMES.get(effective_theme, THEMES[DEFAULT_THEME])
        self.font_size = self.config.get("font_size", DEFAULT_FONT_SIZE)
        self.dict_mode = dict_mode

        clip_mode = clip_mode or self.config.get("clipboard", False)
        self._split = self.config.get("split", "vertical")
        self._sash_frac = self.config.get("sash_frac", 0.5)

        self.root = tk.Tk()
        self.root.title("tt")
        self.root.geometry(self.config.get("geometry", "750x550"))
        self.root.minsize(400, 300)

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

    def small_font(self):
        return (self.font_family, max(self.font_size - 5, 8))

    def _save_config(self):
        cfg = load_config()
        cfg["theme"] = self.theme_var.get()
        cfg["dict_mode"] = self.dict_var.get()
        cfg["font_size"] = self.font_size
        cfg["geometry"] = self.root.geometry()
        cfg["clipboard"] = self.clip_var.get()
        cfg["split"] = self.split_var.get()
        try:
            coord = self.paned.sash_coord(0)
            if self.split_var.get() == "horizontal":
                cfg["sash_frac"] = coord[0] / self.paned.winfo_width()
            else:
                cfg["sash_frac"] = coord[1] / self.paned.winfo_height()
        except Exception:
            pass
        save_config(cfg)

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
        self.dict_var = tk.StringVar(value=self.dict_mode if MW_KEY else "off")
        self.split_var = tk.StringVar(value=self._split)
        self.theme_var = tk.StringVar(value=effective_theme)

        self.settings_btn = tk.Label(self.top_frame, text="settings",
                                     cursor="hand2")
        self.settings_btn.pack(side="right")

        self.clear_btn = tk.Label(self.top_frame, text="clear",
                                   cursor="hand2")
        self.clear_btn.pack(side="right", padx=(0, 10))

        self.clip_label = tk.Label(self.top_frame, text="clip",
                                   cursor="hand2")
        self.clip_label.pack(side="right", padx=(0, 10))
        self._update_clip_label()
        self._settings_win = None

        # Status bar (pack before paned so it gets space first)
        self.status_var = tk.StringVar(value="Enter: translate | Ctrl+L: clear | Ctrl+D: clipboard")
        self.status_label = tk.Label(self.root, textvariable=self.status_var,
                                     anchor="w", pady=4)
        self.status_label.pack(fill="x", padx=12, side="bottom")

        self._text_opts = dict(bd=0, relief="flat", highlightthickness=0,
                               wrap="word", padx=10, pady=8)
        self.paned = None
        self.input_frame = None
        self.input_text = None
        self.output_frame = None
        self.output_text = None
        self._build_paned(self._split)

    def _build_paned(self, orient, frac=None):
        """Create (or recreate) the paned window with given orientation."""
        tk = self.tk
        if frac is None:
            frac = self._sash_frac

        # Save existing text content before destroying
        input_content = ""
        output_content = ""
        if self.input_text:
            input_content = self.input_text.get("1.0", "end-1c")
        if self.output_text:
            output_content = self.output_text.get("1.0", "end-1c")

        # Destroy old widgets if they exist
        if self.paned:
            self.paned.destroy()

        # Create fresh paned + frames + text widgets
        self.paned = tk.PanedWindow(self.root, orient=orient,
                                    sashwidth=8, sashrelief="flat", bd=0,
                                    sashpad=0, opaqueresize=True,
                                    showhandle=False)
        self.paned.pack(fill="both", expand=True, padx=12, pady=(4, 0))

        self.input_frame = tk.Frame(self.paned)
        self.input_text = tk.Text(self.input_frame, **self._text_opts)
        self.input_scroll = tk.Scrollbar(self.input_frame, command=self.input_text.yview,
                                         highlightthickness=0, bd=0, width=8)
        self.input_text.config(yscrollcommand=self.input_scroll.set)
        self.input_scroll.pack(side="right", fill="y")
        self.input_text.pack(fill="both", expand=True)
        self.paned.add(self.input_frame, minsize=60)

        self.output_frame = tk.Frame(self.paned)
        self.output_text = tk.Text(self.output_frame, state="disabled", **self._text_opts)
        self.output_scroll = tk.Scrollbar(self.output_frame, command=self.output_text.yview,
                                          highlightthickness=0, bd=0, width=8)
        self.output_text.config(yscrollcommand=self.output_scroll.set)
        self.output_scroll.pack(side="right", fill="y")
        self.output_text.pack(fill="both", expand=True)
        self.paned.add(self.output_frame, minsize=60)

        # Restore text content
        if input_content:
            self.input_text.insert("1.0", input_content)
        if output_content:
            self.output_text.config(state="normal")
            self.output_text.insert("1.0", output_content)
            self.output_text.config(state="disabled")

        # Re-bind input events (old text widget was destroyed)
        self.input_text.bind("<Return>", self._do_translate)
        self.input_text.bind("<Control-Return>", self._do_translate)
        self.input_text.bind("<Shift-Return>", lambda e: None)
        self.input_text.bind("<Control-a>", self._select_all)
        self.input_text.bind("<Control-l>", self._clear)
        self.input_text.focus_set()

        # Apply theme and restore sash
        self.apply_theme()
        def _set_sash():
            self.root.update_idletasks()
            if orient == "horizontal":
                size = self.paned.winfo_width()
                if size > 1:
                    self.paned.sash_place(0, int(size * frac), 0)
            else:
                size = self.paned.winfo_height()
                if size > 1:
                    self.paned.sash_place(0, 0, int(size * frac))
        self.root.after(100, _set_sash)

    def _bind_events(self):
        self.root.bind("<Control-Button-4>", self._zoom)
        self.root.bind("<Control-Button-5>", self._zoom)
        self.root.bind("<Control-MouseWheel>", self._zoom)
        self.root.bind("<Control-plus>", self._zoom_in)
        self.root.bind("<Control-equal>", self._zoom_in)
        self.root.bind("<Control-minus>", self._zoom_out)
        self.root.bind("<Control-0>", self._zoom_reset)
        self.root.bind("<Control-comma>", self._open_settings)
        self.settings_btn.bind("<Button-1>", self._open_settings)
        self.clear_btn.bind("<Button-1>", self._clear)
        self.clip_label.bind("<Button-1>", lambda e: self._toggle_clip())
        self.root.bind("<Control-d>", lambda e: self._toggle_clip())
        self.root.bind("<Control-l>", self._clear)
        self.theme_var.trace_add("write", self.apply_theme)
        self.split_var.trace_add("write", lambda *_: self._build_paned(
            self.split_var.get(), 0.5))
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _update_clip_label(self):
        on = self.clip_var.get()
        t = self.theme
        if on:
            self.clip_label.configure(text="clip: on", fg=t["accent"])
        else:
            self.clip_label.configure(text="clip: off", fg=t["fg_dim"])

    def _toggle_clip(self):
        self.clip_var.set(not self.clip_var.get())
        self._update_clip_label()

    def _select_all(self, _event=None):
        self.input_text.tag_add("sel", "1.0", "end")
        return "break"

    def _on_close(self):
        self._save_config()
        self.root.destroy()

    def _open_settings(self, _event=None):
        tk = self.tk
        if self._settings_win and self._settings_win.winfo_exists():
            self._settings_win.lift()
            self._settings_win.focus_force()
            return "break"

        t = self.theme
        win = tk.Toplevel(self.root)
        self._settings_win = win
        win.title("tt — settings")
        win.geometry("420x420")
        win.minsize(350, 300)
        win.configure(bg=t["bg"])
        win.transient(self.root)
        win.lift()
        win.focus_force()

        sf = self.small_font()
        uf = self.ui_font()
        pad = dict(padx=20, pady=(12, 0))

        def make_row():
            f = tk.Frame(win, bg=t["bg"])
            f.pack(fill="x", **pad)
            return f

        def make_label(parent, text):
            return tk.Label(parent, text=text, bg=t["bg"], fg=t["fg_dim"],
                            font=sf, anchor="w")

        # Theme
        row = make_row()
        make_label(row, "THEME").pack(side="left")
        tm = tk.OptionMenu(row, self.theme_var, *THEMES.keys())
        tm.config(bg=t["bg2"], fg=t["fg"], font=uf, bd=0, relief="flat",
                  highlightthickness=0, activebackground=t["bg2"],
                  activeforeground=t["fg"])
        tm["menu"].config(bg=t["bg2"], fg=t["fg"], font=uf,
                          activebackground=t["accent"], activeforeground=t["fg"], bd=0)
        tm.pack(side="right")

        # Font size
        row = make_row()
        make_label(row, "FONT SIZE").pack(side="left")
        fs_var = tk.IntVar(value=self.font_size)

        def on_fs_change(*_):
            try:
                val = fs_var.get()
            except Exception:
                return
            if 8 <= val <= 48:
                self.font_size = val
                self._apply_zoom(show_status=False)

        fs_spin = tk.Spinbox(row, from_=8, to=48, textvariable=fs_var, width=4,
                             command=lambda: on_fs_change(),
                             bg=t["bg2"], fg=t["fg"], font=uf, bd=0,
                             relief="flat", highlightthickness=1,
                             highlightbackground=t["bg2"],
                             highlightcolor=t["accent"],
                             buttonbackground=t["bg2"])
        fs_spin.pack(side="right")
        fs_var.trace_add("write", on_fs_change)

        # Target language
        row = make_row()
        make_label(row, "TARGET LANGUAGE").pack(side="left")
        te = tk.Entry(row, textvariable=self.lang_var, width=6,
                      bg=t["bg2"], fg=t["fg"], insertbackground=t["fg"],
                      font=uf, bd=0, relief="flat",
                      highlightthickness=1, highlightbackground=t["bg2"],
                      highlightcolor=t["accent"])
        te.pack(side="right")

        # Dictionary mode
        if MW_KEY:
            row = make_row()
            make_label(row, "DICTIONARY").pack(side="left")
            dm = tk.OptionMenu(row, self.dict_var, "both", "dict", "off")
            dm.config(bg=t["bg2"], fg=t["fg"], font=uf, bd=0, relief="flat",
                      highlightthickness=0, activebackground=t["bg2"],
                      activeforeground=t["fg"])
            dm["menu"].config(bg=t["bg2"], fg=t["fg"], font=uf,
                              activebackground=t["accent"],
                              activeforeground=t["fg"], bd=0)
            dm.pack(side="right")

        # Clipboard
        row = make_row()
        make_label(row, "CLIPBOARD (Ctrl+D)").pack(side="left")
        cc = tk.Checkbutton(row, variable=self.clip_var,
                            bg=t["bg"], selectcolor=t["bg2"],
                            activebackground=t["bg"], highlightthickness=0,
                            command=self._update_clip_label)
        cc.pack(side="right")

        # Split orientation
        row = make_row()
        make_label(row, "SPLIT").pack(side="left")
        sp = tk.OptionMenu(row, self.split_var, "vertical", "horizontal")
        sp.config(bg=t["bg2"], fg=t["fg"], font=uf, bd=0, relief="flat",
                  highlightthickness=0, activebackground=t["bg2"],
                  activeforeground=t["fg"])
        sp["menu"].config(bg=t["bg2"], fg=t["fg"], font=uf,
                          activebackground=t["accent"], activeforeground=t["fg"], bd=0)
        sp.pack(side="right")

        # Separator + config path
        tk.Frame(win, bg=t["fg_dim"], height=1).pack(fill="x", padx=20, pady=(20, 0))
        tk.Label(win, text=f"config: {CONFIG_PATH}", bg=t["bg"],
                 fg=t["fg_dim"], font=sf, anchor="w").pack(
                     fill="x", padx=20, pady=(8, 10))

        def on_close():
            try:
                self.font_size = fs_var.get()
            except Exception:
                pass
            self._apply_zoom(show_status=False)
            win.destroy()
            self._settings_win = None

        win.protocol("WM_DELETE_WINDOW", on_close)
        win.bind("<Escape>", lambda e: on_close())
        return "break"

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
        dm = self.dict_var.get()
        self.status_var.set(f"{prefix}translating..." if prefix else "translating...")

        def run():
            try:
                result = translate_auto(text, target, dict_mode=dm)
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
            self._set_output("")
            return "break"
        self._run_translate(text)
        return "break"

    def _clear(self, _event=None):
        self.input_text.delete("1.0", "end")
        self._set_output("")
        self.status_var.set("")
        self.input_text.focus_set()
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
            # Skip if user is typing (input has focus)
            if text and self.root.focus_get() != self.input_text:
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

    def _apply_zoom(self, show_status=True):
        self.apply_theme()
        if show_status:
            self.status_var.set(f"font size: {self.font_size}")

    def apply_theme(self, *_args):
        t = THEMES.get(self.theme_var.get(), THEMES[DEFAULT_THEME])
        self.theme = t
        bg, bg2, fg = t["bg"], t["bg2"], t["fg"]
        fg_dim, accent, select = t["fg_dim"], t["accent"], t["select"]
        f, uf, sf = self.text_font(), self.ui_font(), self.small_font()
        self.root.configure(bg=bg)
        self.top_frame.configure(bg=bg)
        self.target_label.configure(bg=bg, fg=fg_dim, font=uf)
        self.lang_entry.configure(bg=bg2, fg=fg, insertbackground=fg,
                                  highlightbackground=bg2, highlightcolor=accent, font=uf)
        self.settings_btn.configure(bg=bg, fg=accent, font=sf)
        self.clear_btn.configure(bg=bg, fg=accent, font=sf)
        self.clip_label.configure(bg=bg, font=sf)
        self._update_clip_label()
        for w in (self.input_text, self.output_text):
            w.configure(bg=bg2, fg=fg, insertbackground=fg,
                        selectbackground=select, selectforeground=fg, font=f)
        for fr in (self.input_frame, self.output_frame):
            fr.configure(bg=bg2)
        for s in (self.input_scroll, self.output_scroll):
            s.configure(bg=bg2, troughcolor=bg2)
        self.paned.configure(bg=bg)
        self.status_label.configure(bg=bg, fg=fg_dim, font=sf)

    def run(self):
        self.root.mainloop()


def gui(fixed_target=None, clip_mode=False, theme_name=None, config=None,
        dict_mode="both"):
    """Tkinter GUI mode."""
    app = TranslatorGUI(fixed_target, clip_mode, theme_name, config, dict_mode)
    app.run()


def main():
    config = load_config()

    parser = argparse.ArgumentParser(
        description="tt - Terminal Translator",
        usage="tt [text] | tt --clip | tt --repl | tt -t <lang> [text]",
    )
    parser.add_argument("text", nargs="*", help="text to translate")
    parser.add_argument("-t", "--target", default=None, help="target language (default: auto-toggle ko/en)")
    parser.add_argument("-d", "--dict", default=config.get("dict_mode", "both"),
                        choices=["both", "dict", "off"],
                        help="dictionary mode for single words (default: saved or both)")
    parser.add_argument("--clip", action="store_true", help="clipboard monitoring mode")
    parser.add_argument("--repl", action="store_true", help="interactive REPL mode")
    parser.add_argument("--theme", default=None,
                        choices=list(THEMES.keys()),
                        help=f"color theme (default: {DEFAULT_THEME})")
    args = parser.parse_args()

    target = args.target or config.get("target")

    if args.clip and not args.text:
        gui(target, clip_mode=True, theme_name=args.theme, config=config,
            dict_mode=args.dict)
    elif args.text:
        try:
            print(translate_auto(" ".join(args.text), target, dict_mode=args.dict))
        except Exception as e:
            print(f"[error] {e}", file=sys.stderr)
            sys.exit(1)
    elif not sys.stdin.isatty():
        text = sys.stdin.read().strip()
        if text:
            try:
                print(translate_auto(text, target, dict_mode=args.dict))
            except Exception as e:
                print(f"[error] {e}", file=sys.stderr)
                sys.exit(1)
        else:
            gui(target, theme_name=args.theme, config=config, dict_mode=args.dict)
    elif args.repl:
        repl(target, dict_mode=args.dict)
    else:
        gui(target, theme_name=args.theme, config=config, dict_mode=args.dict)


if __name__ == "__main__":
    main()
