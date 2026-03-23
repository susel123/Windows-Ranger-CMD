
import os
import sys
import shutil
import string
import time
try:
    import msvcrt
except ImportError:
    msvcrt = None
import unicodedata
import subprocess
import re
from pathlib import Path

PILImage = None
pygame = None

# ANSI kolory
C_RESET  = '\033[0m'
C_FOLDER = '\033[38;5;180m'
C_IMG    = '\033[38;5;103m'
C_VIDEO  = '\033[38;5;132m'
C_AUDIO  = '\033[38;5;138m'
C_DOC    = '\033[38;5;109m'
C_ARCH   = '\033[38;5;131m'
C_EXE    = '\033[38;5;108m'
C_DIM    = '\033[38;5;240m'
C_BG     = '\033[48;5;236;38;5;255m'
C_LINE   = '\033[38;5;237m'
C_INFO   = '\033[38;5;244m'
C_WARN   = '\033[38;5;214m'
C_ERR    = '\033[38;5;203m'
C_OK     = '\033[38;5;120m'

os.system("")

TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".json", ".ini", ".log", ".csv", ".xml", ".html",
    ".css", ".js", ".ts", ".yaml", ".yml", ".cfg", ".conf", ".bat", ".cmd"
}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".webm"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".ogg"}
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar", ".gz", ".xz"}
EXE_EXTENSIONS = {".exe", ".msi"}

SORT_MODES = ["name", "size", "date", "type"]
SCROLL_INTERVAL = 0.12
PREVIEW_LINES = 30
BOOKMARK_LIMIT = 9

AUDIO_PLAYER_READY = False
AUDIO_TRACK_PLAYING = None
AUDIO_PROCESS = None
AUDIO_BACKEND = None

def get_pillow_image():
    global PILImage
    if PILImage is not None:
        return PILImage
    try:
        from PIL import Image as _Image
        PILImage = _Image
        return PILImage
    except Exception:
        return None


def get_pygame():
    global pygame
    if pygame is not None:
        return pygame
    try:
        import pygame as _pygame
        pygame = _pygame
        return pygame
    except Exception:
        return None


def enable_audio_player():
    global AUDIO_PLAYER_READY
    if AUDIO_PLAYER_READY:
        return True
    pg = get_pygame()
    if pg is None:
        return False
    try:
        pg.mixer.init()
        AUDIO_PLAYER_READY = True
        return True
    except Exception:
        return False


def play_audio(path):
    global AUDIO_TRACK_PLAYING, AUDIO_BACKEND, AUDIO_PROCESS

    stop_audio()

    pg = get_pygame()
    if pg is not None:
        try:
            if enable_audio_player():
                pg.mixer.music.stop()
                pg.mixer.music.load(path)
                pg.mixer.music.play()
                AUDIO_TRACK_PLAYING = path
                AUDIO_BACKEND = 'pygame'
                return True
        except Exception:
            pass

    if sys.platform.startswith('win'):
        try:
            escaped = str(Path(path).resolve()).replace("'", "''").replace('\\', '/')
            ps = f"""
Add-Type -AssemblyName PresentationCore
$player = New-Object System.Windows.Media.MediaPlayer
$player.Open([Uri]::new("file:///{escaped}"))
$player.Play()
while ($true) {{
    Start-Sleep -Milliseconds 500
}}
"""
            AUDIO_PROCESS = subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            AUDIO_TRACK_PLAYING = path
            AUDIO_BACKEND = 'powershell'
            return True
        except Exception:
            pass

    return False


def stop_audio():
    global AUDIO_TRACK_PLAYING, AUDIO_PROCESS, AUDIO_BACKEND, AUDIO_PLAYER_READY
    pg = get_pygame()
    if AUDIO_PLAYER_READY and pg is not None:
        try:
            pg.mixer.music.stop()
        except Exception:
            pass
    if AUDIO_PROCESS is not None:
        try:
            AUDIO_PROCESS.terminate()
        except Exception:
            pass
        AUDIO_PROCESS = None
    AUDIO_TRACK_PLAYING = None
    AUDIO_BACKEND = None


def get_drives():
    drives = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            drives.append(drive)
    return drives


def is_drive_root(path):
    if not path:
        return False
    path = os.path.normpath(path)
    drive, tail = os.path.splitdrive(path)
    return bool(drive) and tail in ("\\", "/")


def get_parent_path(path):
    if path is None:
        return None
    if is_drive_root(path):
        return None
    parent = os.path.dirname(path.rstrip("\\/"))
    return parent if parent else None


def list_items(path):
    if path is None:
        return get_drives()
    if not os.path.exists(path):
        return []
    try:
        items = os.listdir(path)
        return items
    except Exception:
        return []


def fuzzy_score(text, query):
    text = clean_text(text).casefold()
    query = clean_text(query).casefold().strip()
    if not query:
        return 0
    if query in text:
        return -1000 + text.index(query)

    ti = 0
    qi = 0
    gaps = 0
    start = None
    while ti < len(text) and qi < len(query):
        if text[ti] == query[qi]:
            if start is None:
                start = ti
            qi += 1
        else:
            if start is not None:
                gaps += 1
        ti += 1
    if qi != len(query):
        return None
    score = (start or 0) * 2 + gaps + (len(text) - len(query))
    if text.startswith(query):
        score -= 50
    return score


def filter_and_sort_items(items, search_query, ext_filter, current_dir, sort_mode, reverse_sort):
    filtered = []
    ext_filter = (ext_filter or '').strip().lower()
    search_query = (search_query or '').strip()

    for item in items:
        full = item if current_dir is None else os.path.join(current_dir, item)
        if ext_filter:
            ext = os.path.splitext(item)[1].lower().lstrip('.')
            if ext != ext_filter.lstrip('.'):
                continue
        if search_query and fuzzy_score(item, search_query) is None:
            continue
        filtered.append(item)

    def sort_key(name):
        full = name if current_dir is None else os.path.join(current_dir, name)
        is_dir = os.path.isdir(full)
        try:
            st = os.stat(full)
        except Exception:
            st = None
        if sort_mode == 'size':
            size = st.st_size if st is not None else -1
            return (0 if is_dir else 1, size, name.casefold())
        if sort_mode == 'date':
            mtime = st.st_mtime if st is not None else 0
            return (0 if is_dir else 1, mtime, name.casefold())
        if sort_mode == 'type':
            ext = os.path.splitext(name)[1].lower()
            return (0 if is_dir else 1, ext, name.casefold())
        return (0 if is_dir else 1, name.casefold())

    filtered.sort(key=sort_key, reverse=reverse_sort)
    return filtered


def clean_text(text):
    text = str(text)
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    return "".join(ch if ch.isprintable() else "?" for ch in text)


def char_width(ch):
    if unicodedata.combining(ch):
        return 0
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    return 1


ANSI_RE = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')

def strip_ansi(text):
    return ANSI_RE.sub('', str(text))


def display_width(text):
    return sum(char_width(ch) for ch in text)


def human_size(num):
    try:
        num = float(num)
    except Exception:
        return "?"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    for unit in units:
        if num < 1024:
            return f"{num:.1f} {unit}" if unit != "B" else f"{int(num)} B"
        num /= 1024
    return f"{num:.1f} EB"


def format_time(ts):
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
    except Exception:
        return "?"


def read_key():
    if msvcrt is None:
        return None

    if not msvcrt.kbhit():
        return None

    ch = msvcrt.getwch()

    if ch in ("\x00", "\xe0"):
        ch2 = msvcrt.getwch()
        return {
            "H": "UP",
            "P": "DOWN",
            "K": "LEFT",
            "M": "RIGHT",
        }.get(ch2)

    if ch == "\r":
        return "ENTER"
    if ch == "\x1b":
        return "ESC"
    if ch == "\x08":
        return "BACKSPACE"
    if ch == "\t":
        return "TAB"

    return ch

def trim_to_width(text, width):
    text = clean_text(text)
    if width <= 0:
        return ""
    if display_width(text) <= width:
        return text

    ellipsis = "..."
    ell_w = display_width(ellipsis)

    if width <= ell_w:
        out = []
        used = 0
        for ch in text:
            cw = char_width(ch)
            if used + cw > width:
                break
            out.append(ch)
            used += cw
        return "".join(out)

    target = width - ell_w
    out = []
    used = 0
    for ch in text:
        cw = char_width(ch)
        if used + cw > target:
            break
        out.append(ch)
        used += cw
    return "".join(out) + ellipsis


def fit_text(text, width):
    text = trim_to_width(text, width)
    pad = width - display_width(text)
    if pad > 0:
        text += " " * pad
    return text


def wrap_text_lines(text, width):
    text = clean_text(text)
    if width <= 0:
        return [""]

    words = text.split()
    if not words:
        return [""]

    lines = []
    current = ""

    def push_current():
        nonlocal current
        if current:
            lines.append(fit_text(current, width))
            current = ""

    for word in words:
        if display_width(word) > width:
            push_current()
            chunk = ""
            for ch in word:
                if display_width(chunk + ch) > width:
                    if chunk:
                        lines.append(fit_text(chunk, width))
                        chunk = ""
                    if char_width(ch) > width:
                        lines.append(fit_text(trim_to_width(ch, width), width))
                    else:
                        chunk = ch
                else:
                    chunk += ch
            if chunk:
                lines.append(fit_text(chunk, width))
            continue

        candidate = word if not current else current + " " + word
        if display_width(candidate) <= width:
            current = candidate
        else:
            push_current()
            current = word

    push_current()
    return lines if lines else [""]


def marquee_text(text, width, offset):
    text = clean_text(text)
    if width <= 0:
        return ""
    if display_width(text) <= width:
        return fit_text(text, width)

    padded = text + "   "
    total = len(padded)
    offset %= total

    out = []
    used = 0
    i = offset
    while used < width:
        ch = padded[i % total]
        cw = char_width(ch)
        if used + cw > width:
            break
        out.append(ch)
        used += cw
        i += 1

    return fit_text("".join(out), width)


def file_color(name, is_dir, dim=False):
    if dim:
        return C_DIM
    if is_dir:
        return C_FOLDER

    ext = os.path.splitext(name)[1].lower()
    if ext in IMAGE_EXTENSIONS:
        return C_IMG
    if ext in VIDEO_EXTENSIONS:
        return C_VIDEO
    if ext in AUDIO_EXTENSIONS:
        return C_AUDIO
    if ext in ARCHIVE_EXTENSIONS:
        return C_ARCH
    if ext in EXE_EXTENSIONS:
        return C_EXE
    if ext in TEXT_EXTENSIONS:
        return C_DOC
    return ""


def format_line(name, is_dir, width, selected=False, dim=False, marked=False):
    shown = name + "\\" if is_dir and not name.endswith("\\") else name
    if marked:
        shown = "[x] " + shown
    shown = fit_text(shown, max(0, width - 2))
    color = file_color(name, is_dir, dim=dim)
    cell = fit_text(f" {shown} ", width)
    if selected:
        return f"{C_BG}{cell}{C_RESET}"
    return f"{color}{cell}{C_RESET}"



def is_text_file(path):
    try:
        with open(path, "rb") as f:
            chunk = f.read(4096)
            if b"\x00" in chunk:
                return False
            if not chunk:
                return True
            printable = 0
            for b in chunk:
                if b in (9, 10, 13) or 32 <= b <= 126 or b >= 160:
                    printable += 1
            return (printable / len(chunk)) > 0.75
    except Exception:
        return False


def _resize_for_terminal(img, max_rows, max_cols):
    pil = get_pillow_image()
    if pil is None:
        resample = 1
    else:
        try:
            resample = pil.Resampling.LANCZOS
        except Exception:
            resample = getattr(pil, "LANCZOS", 1)

    # Braille uses 2x4 dots per character cell.
    # We keep the preview inside the available panel and prefer a slightly
    # wider canvas so the shape looks less blocky.
    target_cols = max(8, min(max_cols * 2, 120))
    target_rows = max(8, min(max_rows * 4, 120))
    return img.resize((target_cols, target_rows), resample)


def _image_pixels_to_braille_lines(pixels, width, height):
    # Convert a grayscale matrix into Unicode braille characters.
    # Each braille cell maps to a 2x4 pixel block.
    lines = []
    for y in range(0, height - (height % 4), 4):
        row = []
        for x in range(0, width - (width % 2), 2):
            bits = 0
            # Dot numbering:
            # 1 4
            # 2 5
            # 3 6
            # 7 8
            if pixels[y + 0][x + 0] < 160: bits |= 0x01
            if pixels[y + 1][x + 0] < 160: bits |= 0x02
            if pixels[y + 2][x + 0] < 160: bits |= 0x04
            if pixels[y + 0][x + 1] < 160: bits |= 0x08
            if pixels[y + 1][x + 1] < 160: bits |= 0x10
            if pixels[y + 2][x + 1] < 160: bits |= 0x20
            if pixels[y + 3][x + 0] < 160: bits |= 0x40
            if pixels[y + 3][x + 1] < 160: bits |= 0x80
            row.append(chr(0x2800 + bits))
        lines.append("".join(row).rstrip())
    return lines


def _image_to_braille_lines_from_pillow(img):
    gray = img.convert("L")
    width, height = gray.size
    pixels = gray.load()
    matrix = [[pixels[x, y] for x in range(width)] for y in range(height)]
    return _image_pixels_to_braille_lines(matrix, width, height)


def _render_image_preview_powershell(path, max_rows, max_cols):
    if not sys.platform.startswith("win"):
        return []

    try:
        escaped = str(Path(path).resolve()).replace("'", "''")
        cols = max(8, min(max_cols * 2, 120))
        rows = max(8, min(max_rows * 4, 120))
        ps = f"""
Add-Type -AssemblyName System.Drawing
$img = [System.Drawing.Image]::FromFile('{escaped}')
$bmp = New-Object System.Drawing.Bitmap {cols}, {rows}
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$g.DrawImage($img, 0, 0, {cols}, {rows})
$g.Dispose()
for ($y = 0; $y -lt {rows}; $y++) {{
    $row = New-Object System.Collections.Generic.List[System.String]
    for ($x = 0; $x -lt {cols}; $x++) {{
        $p = $bmp.GetPixel($x, $y)
        $gval = [int](($p.R * 0.299) + ($p.G * 0.587) + ($p.B * 0.114))
        $row.Add($gval.ToString())
    }}
    Write-Output ($row -join ',')
}}
$g.Dispose()
$bmp.Dispose()
$img.Dispose()
"""
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode == 0 and result.stdout.strip():
            matrix = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    matrix.append([int(x) for x in line.split(',') if x != ''])
                except Exception:
                    return []
            if matrix:
                return _image_pixels_to_braille_lines(matrix, len(matrix[0]), len(matrix))
    except Exception:
        pass
    return []


def render_image_preview(path, max_rows, max_cols):
    Image = get_pillow_image()
    if Image is not None:
        try:
            img = Image.open(path).convert("RGB")
            img = _resize_for_terminal(img, max_rows, max_cols)
            return _image_to_braille_lines_from_pillow(img)
        except Exception:
            pass

    return _render_image_preview_powershell(path, max_rows, max_cols)


def preview_file(path, max_rows, max_cols=24):

    ext = os.path.splitext(path)[1].lower()

    if ext in IMAGE_EXTENSIONS:
        lines = render_image_preview(path, max_rows, max_cols)
        if lines:
            return [("img", line) for line in lines]
        return [("text", "<podgląd obrazu niedostępny>")]

    if not is_text_file(path):
        return [("text", "<plik binarny>")]

    lines = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for _ in range(max_rows):
                line = f.readline()
                if not line:
                    break
                lines.append(("text", clean_text(line.rstrip("\r\n"))))
    except Exception:
        return [("text", "<brak podglądu>")]

    return lines if lines else [("text", "<pusty plik>")]


def preview_directory(path, max_rows):
    try:
        return list_items(path)[:max_rows]
    except Exception:
        return [("text", "<brak podglądu>")]


def open_selected(path):
    try:
        os.startfile(path)
        return True
    except Exception:
        try:
            subprocess.Popen(
                ["cmd", "/c", "start", "", str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            return False


def open_in_editor(path):
    try:
        if is_text_file(path):
            if sys.platform.startswith("win"):
                subprocess.Popen(["notepad.exe", path], shell=False)
            else:
                os.startfile(path)
        else:
            open_selected(path)
    except Exception:
        open_selected(path)


def handle_enter_action(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in AUDIO_EXTENSIONS:
        played = play_audio(path)
        if played:
            return "Odtwarzanie audio..."
        if open_selected(path):
            return "Audio otwarte w domyślnej aplikacji"
        return "Nie udało się odtworzyć ani otworzyć"
    if ext in IMAGE_EXTENSIONS:
        return "Podgląd obrazu pokazany w panelu"
    if is_text_file(path):
        return open_in_editor(path) or "Otworzono w edytorze"
    return open_selected(path) or "Otworzono zewnętrznie"


def build_info_lines(path, max_rows, preview_width=40):
    lines = []
    if not path:
        lines.append(("text", "MÓJ KOMPUTER"))
        lines.append(("text", ""))
        lines.append(("text", "Wybierz dysk."))
        return lines[:max_rows]

    name = os.path.basename(path.rstrip("\\/")) or path

    try:
        st = os.stat(path)
    except Exception:
        st = None

    if os.path.isdir(path):
        lines.append(("text", "[FOLDER]"))
        lines.append(("text", f"Nazwa: {name}"))
        lines.append(("text", f"Ścieżka: {path}"))
        try:
            count = len(list_items(path))
            lines.append(("text", f"Elementów: {count}"))
        except Exception:
            lines.append(("text", "Elementów: ?"))
        if st is not None:
            lines.append(("text", f"Zmodyfikowany: {format_time(st.st_mtime)}"))
    else:
        ext = os.path.splitext(path)[1].lower() or "<brak>"
        lines.append(("text", "[PLIK]"))
        lines.append(("text", f"Nazwa: {name}"))
        lines.append(("text", f"Ścieżka: {path}"))
        lines.append(("text", f"Rozszerzenie: {ext}"))
        if st is not None:
            lines.append(("text", f"Rozmiar: {human_size(st.st_size)}"))
            lines.append(("text", f"Zmodyfikowany: {format_time(st.st_mtime)}"))
            lines.append(("text", f"Utworzony: {format_time(st.st_ctime)}"))

        if ext in IMAGE_EXTENSIONS:
            lines.append(("text", "Podgląd obrazu:"))
            img_lines = render_image_preview(path, max_rows - len(lines) - 1, preview_width)
            if img_lines:
                lines.extend(("img", ln) for ln in img_lines)
            else:
                lines.append(("text", "<podgląd obrazu niedostępny>"))
        elif is_text_file(path):
            lines.append(("text", "Podgląd:"))
            lines.extend(preview_file(path, max_rows - len(lines) - 1, preview_width))
        elif ext in AUDIO_EXTENSIONS:
            lines.append(("text", "<audio: Enter odtwarza, t stop>"))
        else:
            lines.append(("text", "<plik binarny>"))

    return lines[:max_rows]


def build_controls_lines(search_mode, search_query, filter_mode, ext_filter, sort_mode, marked_count, clipboard, bookmarks, width):
    clip_txt = "brak" if not clipboard else f"{clipboard['mode']}:{len(clipboard['paths'])}"
    bm_txt = f"{len(bookmarks)}"

    if search_mode:
        segments = [
            f"Szukaj: /{search_query}",
            "Enter = koniec",
            "Esc = anuluj",
            "Backspace = usuń",
            f"Zaznaczone: {marked_count}",
            f"Schowek: {clip_txt}",
            f"Zakładki: {bm_txt}",
        ]
    elif filter_mode:
        segments = [
            f"Filtr: {ext_filter}",
            "Enter = koniec",
            "Esc = anuluj",
            "Backspace = usuń",
            f"Zaznaczone: {marked_count}",
            f"Schowek: {clip_txt}",
            f"Zakładki: {bm_txt}",
        ]
    else:
        segments = [
            "↑↓ wybór",
            "Space zaznacz",
            "c kopiuj",
            "m przenieś",
            "p wklej",
            "d usuń",
            "h/l historia",
            "b zakładka",
            "Tab zakładki",
            f"s sort {sort_mode}",
            "r odwróć",
            "f filtr",
            "/ szukaj",
            "e otwórz/edytuj",
            "t stop audio",
            "q/ESC wyjście",
            f"Zaznaczone: {marked_count}",
            f"Schowek: {clip_txt}",
            f"Zakładki: {bm_txt}",
        ]

    lines = []
    current = ""
    for seg in segments:
        if not current:
            current = seg
            continue
        candidate = current + " | " + seg
        if display_width(candidate) <= width:
            current = candidate
        else:
            lines.extend(wrap_text_lines(current, width))
            current = seg
    if current:
        lines.extend(wrap_text_lines(current, width))
    return lines if lines else [""]


def unique_destination_path(dest_path):
    if not os.path.exists(dest_path):
        return dest_path

    base_dir = os.path.dirname(dest_path)
    base_name = os.path.basename(dest_path)

    if os.path.isdir(dest_path):
        stem = base_name
        ext = ""
    else:
        stem, ext = os.path.splitext(base_name)

    n = 1
    while True:
        if ext:
            candidate = os.path.join(base_dir, f"{stem} (copy {n}){ext}")
        else:
            candidate = os.path.join(base_dir, f"{stem} (copy {n})")
        if not os.path.exists(candidate):
            return candidate
        n += 1


def copy_path(src, dst_dir, conflict_mode="ask"):
    base = os.path.basename(src.rstrip("\\/"))
    dst = os.path.join(dst_dir, base)

    if os.path.exists(dst):
        if conflict_mode == "skip":
            return "skip", dst
        if conflict_mode == "rename":
            dst = unique_destination_path(dst)
        elif conflict_mode == "overwrite":
            delete_path(dst)
        else:
            return "conflict", dst

    if os.path.isdir(src) and not os.path.islink(src):
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
    return "ok", dst


def move_path(src, dst_dir, conflict_mode="ask"):
    base = os.path.basename(src.rstrip("\\/"))
    dst = os.path.join(dst_dir, base)

    if os.path.exists(dst):
        if conflict_mode == "skip":
            return "skip", dst
        if conflict_mode == "rename":
            dst = unique_destination_path(dst)
        elif conflict_mode == "overwrite":
            delete_path(dst)
        else:
            return "conflict", dst

    shutil.move(src, dst)
    return "ok", dst


def delete_path(path):
    if os.path.islink(path) or os.path.isfile(path):
        os.unlink(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)


def collect_targets(current_dir, sel_item, marked_paths):
    if marked_paths:
        return [p for p in marked_paths if os.path.exists(p)]
    if sel_item is None:
        return []
    sel_full = sel_item if current_dir is None else os.path.join(current_dir, sel_item)
    return [sel_full] if os.path.exists(sel_full) else []


def format_progress_bar(done, total, width=24):
    if total <= 0:
        return "[" + ("=" * width) + "]"
    fill = int((done / total) * width)
    fill = max(0, min(width, fill))
    return "[" + ("=" * fill) + (" " * (width - fill)) + "]"


def make_operation(kind, sources, dst_dir=None):
    total = len(sources)
    return {
        "kind": kind,
        "sources": sources[:],
        "dst_dir": dst_dir,
        "index": 0,
        "ok": 0,
        "fail": 0,
        "skip": 0,
        "current": "",
        "conflict": None,
        "policy": "ask",
        "done": 0,
        "total": total,
        "finished": False,
        "message": "",
    }


def process_operation(op_state, marked_paths):
    if op_state is None or op_state.get("finished"):
        return op_state

    if op_state.get("conflict") is not None:
        return op_state

    if op_state["index"] >= len(op_state["sources"]):
        if op_state["kind"] == "move":
            op_state["message"] = f"Przeniesiono: {op_state['ok']}, błędy: {op_state['fail']}, pominięte: {op_state['skip']}"
        elif op_state["kind"] == "copy":
            op_state["message"] = f"Skopiowano: {op_state['ok']}, błędy: {op_state['fail']}, pominięte: {op_state['skip']}"
        elif op_state["kind"] == "delete":
            op_state["message"] = f"Usunięto: {op_state['ok']}, błędy: {op_state['fail']}, pominięte: {op_state['skip']}"
        op_state["finished"] = True
        return op_state

    src = op_state["sources"][op_state["index"]]
    op_state["current"] = src

    if not os.path.exists(src):
        op_state["fail"] += 1
        op_state["index"] += 1
        op_state["done"] += 1
        return op_state

    try:
        if op_state["kind"] == "delete":
            delete_path(src)
            marked_paths.discard(src)
            op_state["ok"] += 1
            op_state["index"] += 1
            op_state["done"] += 1
            return op_state

        dst_dir = op_state["dst_dir"]
        if dst_dir is None or not os.path.isdir(dst_dir):
            op_state["fail"] += 1
            op_state["index"] += 1
            op_state["done"] += 1
            return op_state

        if op_state["kind"] == "copy":
            res, dst = copy_path(src, dst_dir, conflict_mode=op_state["policy"])
        elif op_state["kind"] == "move":
            res, dst = move_path(src, dst_dir, conflict_mode=op_state["policy"])
        else:
            res, dst = "fail", ""

        if res == "conflict":
            op_state["conflict"] = {"src": src, "dst": dst, "kind": op_state["kind"]}
            return op_state
        elif res == "skip":
            op_state["skip"] += 1
        elif res == "ok":
            op_state["ok"] += 1
        else:
            op_state["fail"] += 1

        op_state["index"] += 1
        op_state["done"] += 1
        return op_state

    except Exception:
        op_state["fail"] += 1
        op_state["index"] += 1
        op_state["done"] += 1
        return op_state


def get_current_selection(current_dir, items_mid, selected_index):
    if not items_mid:
        return None, None
    sel_item = items_mid[selected_index]
    sel_full = sel_item if current_dir is None else os.path.join(current_dir, sel_item)
    return sel_item, sel_full


def show_message(text, seconds=2.0):
    return {"text": text, "until": time.monotonic() + seconds}


def main():
    current_dir = os.path.abspath(os.getcwd())
    selected_index = 0
    offset = 0

    search_mode = False
    search_query = ""
    filter_mode = False
    ext_filter = ""
    sort_mode_index = 0
    reverse_sort = False

    marked_paths = set()
    clipboard = None
    bookmarks = []

    history_back = []
    history_forward = []

    directory_state = {None: (0, 0)}

    confirm_delete = False
    delete_targets = []

    op_state = None
    action_message = ""
    action_message_until = 0.0

    last_sig = None
    info_lines_cache = []
    status_scroll = 0
    status_last_tick = time.monotonic()

    dirty = True

    def save_view_state(path=None):
        directory_state[path] = (selected_index, offset)

    def restore_view_state(path):
        nonlocal selected_index, offset
        selected_index, offset = directory_state.get(path, (0, 0))

    def enter_directory(new_dir):
        nonlocal current_dir, last_sig, history_back, history_forward, dirty, search_mode, filter_mode, search_query, ext_filter
        save_view_state(current_dir)
        if current_dir != new_dir:
            history_back.append(current_dir)
            history_forward.clear()
        current_dir = os.path.abspath(new_dir)
        restore_view_state(current_dir)
        search_mode = False
        filter_mode = False
        search_query = ""
        ext_filter = ""
        last_sig = None
        dirty = True

    def go_back_history():
        nonlocal current_dir, last_sig, dirty, search_mode, filter_mode, search_query, ext_filter
        if not history_back:
            return
        save_view_state(current_dir)
        history_forward.append(current_dir)
        current_dir = history_back.pop()
        restore_view_state(current_dir)
        search_mode = False
        filter_mode = False
        search_query = ""
        ext_filter = ""
        last_sig = None
        dirty = True

    def go_forward_history():
        nonlocal current_dir, last_sig, dirty, search_mode, filter_mode, search_query, ext_filter
        if not history_forward:
            return
        save_view_state(current_dir)
        history_back.append(current_dir)
        current_dir = history_forward.pop()
        restore_view_state(current_dir)
        search_mode = False
        filter_mode = False
        search_query = ""
        ext_filter = ""
        last_sig = None
        dirty = True

    def refresh_operation_message():
        nonlocal action_message, action_message_until, dirty
        action_message = ""
        action_message_until = 0.0
        dirty = True

    while True:

        w, h = shutil.get_terminal_size(fallback=(120, 40))
        controls_lines = build_controls_lines(search_mode, search_query, filter_mode, ext_filter, SORT_MODES[sort_mode_index], len(marked_paths), clipboard, bookmarks, w)
        footer_lines = 5 + len(controls_lines)
        max_rows = max(1, h - footer_lines)

        all_items_mid = list_items(current_dir)
        items_mid = filter_and_sort_items(
            all_items_mid, search_query, ext_filter, current_dir, SORT_MODES[sort_mode_index], reverse_sort
        )

        if not items_mid:
            selected_index = 0
            offset = 0
        else:
            if selected_index < 0:
                selected_index = 0
            if selected_index >= len(items_mid):
                selected_index = len(items_mid) - 1

        if selected_index < offset:
            offset = selected_index
        elif selected_index >= offset + max_rows:
            offset = selected_index - max_rows + 1

        sel_item, sel_full = get_current_selection(current_dir, items_mid, selected_index)
        sig = (
            current_dir,
            sel_full,
            search_query,
            ext_filter,
            search_mode,
            filter_mode,
            sort_mode_index,
            reverse_sort,
            confirm_delete,
            tuple(sorted(marked_paths)),
            None if clipboard is None else (clipboard["mode"], tuple(clipboard["paths"])),
            None if op_state is None else (
                op_state["kind"],
                op_state["index"],
                op_state["total"],
                op_state.get("finished", False),
                op_state.get("conflict") is not None
            ),
            tuple(bookmarks),
        )

        w1 = max(14, w // 6)
        w2 = max(24, (w - w1) // 2)
        w3 = max(18, w - w1 - w2)

        if sig != last_sig:
            info_lines_cache = build_info_lines(sel_full, max_rows, w3) if sel_full else build_info_lines(None, max_rows, w3)
            last_sig = sig
            status_scroll = 0
            status_last_tick = time.monotonic()
            dirty = True

        parent_path = get_parent_path(current_dir)
        items_left = list_items(parent_path) if parent_path is not None else []

        # process active batch operations
        if op_state is not None and not op_state.get("finished"):
            op_state = process_operation(op_state, marked_paths)
            dirty = True

            if op_state.get("finished"):
                action_message = op_state.get("message", "")
                action_message_until = time.monotonic() + 2.0
                if op_state["kind"] == "move":
                    marked_paths.difference_update(op_state["sources"])
                    clipboard = None
                if op_state["kind"] == "delete":
                    marked_paths.difference_update(op_state["sources"])
                if op_state["kind"] in ("copy", "move"):
                    if clipboard and clipboard["mode"] == "move":
                        clipboard = None
                op_state = None

        now = time.monotonic()
        if action_message and now >= action_message_until:
            refresh_operation_message()

        key = read_key()
        if key is not None:
            # conflict prompt for batch operations
            if op_state is not None and op_state.get("conflict") is not None:
                conflict = op_state["conflict"]
                src = conflict["src"]
                if key in ("y", "Y"):
                    op_state["policy"] = "overwrite"
                    op_state["conflict"] = None
                    dirty = True
                elif key in ("a", "A"):
                    op_state["policy"] = "overwrite"
                    op_state["conflict"] = None
                    dirty = True
                elif key in ("n", "N"):
                    op_state["policy"] = "skip"
                    op_state["conflict"] = None
                    op_state["index"] += 1
                    op_state["skip"] += 1
                    op_state["done"] += 1
                    dirty = True
                elif key in ("s", "S"):
                    op_state["policy"] = "skip"
                    op_state["conflict"] = None
                    op_state["index"] += 1
                    op_state["skip"] += 1
                    op_state["done"] += 1
                    dirty = True
                elif key in ("r", "R"):
                    op_state["policy"] = "rename"
                    op_state["conflict"] = None
                    dirty = True
                elif key in ("c", "C", "ESC"):
                    op_state["conflict"] = None
                    op_state["finished"] = True
                    op_state["message"] = "Anulowano operację"
                    action_message = op_state["message"]
                    action_message_until = time.monotonic() + 1.5
                    dirty = True
                continue

            if confirm_delete:
                if key in ("y", "Y"):
                    op_state = make_operation("delete", delete_targets)
                    confirm_delete = False
                    delete_targets = []
                    dirty = True
                elif key in ("n", "N", "ESC"):
                    confirm_delete = False
                    delete_targets = []
                    action_message = "Anulowano usuwanie"
                    action_message_until = time.monotonic() + 1.5
                    dirty = True
                continue

            if search_mode:
                if key == "ESC":
                    search_mode = False
                    search_query = ""
                    selected_index = 0
                    offset = 0
                    last_sig = None
                    dirty = True
                elif key == "ENTER":
                    search_mode = False
                    dirty = True
                elif key == "BACKSPACE":
                    if search_query:
                        search_query = search_query[:-1]
                        selected_index = 0
                        offset = 0
                        last_sig = None
                        dirty = True
                elif key == " ":
                    search_query += " "
                    selected_index = 0
                    offset = 0
                    last_sig = None
                    dirty = True
                elif key == "UP":
                    if items_mid and selected_index > 0:
                        selected_index -= 1
                        dirty = True
                elif key == "DOWN":
                    if items_mid and selected_index < len(items_mid) - 1:
                        selected_index += 1
                        dirty = True
                elif key == "LEFT":
                    if current_dir is not None:
                        save_view_state(current_dir)
                        if is_drive_root(current_dir):
                            current_dir = None
                        else:
                            current_dir = get_parent_path(current_dir)
                        restore_view_state(current_dir)
                        search_query = ""
                        search_mode = False
                        last_sig = None
                        dirty = True
                elif key == "RIGHT":
                    if items_mid:
                        new_path = items_mid[selected_index] if current_dir is None else os.path.join(current_dir, items_mid[selected_index])
                        if os.path.isdir(new_path):
                            enter_directory(new_path)
                            search_query = ""
                            search_mode = False
                        else:
                            action_message = handle_enter_action(new_path)
                            action_message_until = time.monotonic() + 1.5
                else:
                    if len(key) == 1 and key.isprintable():
                        search_query += key
                        selected_index = 0
                        offset = 0
                        last_sig = None
                        dirty = True
                continue

            if filter_mode:
                if key == "ESC":
                    filter_mode = False
                    ext_filter = ""
                    selected_index = 0
                    offset = 0
                    last_sig = None
                    dirty = True
                elif key == "ENTER":
                    filter_mode = False
                    dirty = True
                elif key == "BACKSPACE":
                    if ext_filter:
                        ext_filter = ext_filter[:-1]
                        selected_index = 0
                        offset = 0
                        last_sig = None
                        dirty = True
                elif key == " ":
                    ext_filter += " "
                    selected_index = 0
                    offset = 0
                    last_sig = None
                    dirty = True
                else:
                    if len(key) == 1 and key.isprintable():
                        ext_filter += key
                        selected_index = 0
                        offset = 0
                        last_sig = None
                        dirty = True
                continue

            if key in ("q", "ESC"):
                break

            elif key == "UP":
                if items_mid and selected_index > 0:
                    selected_index -= 1
                    dirty = True

            elif key == "DOWN":
                if items_mid and selected_index < len(items_mid) - 1:
                    selected_index += 1
                    dirty = True

            elif key == "LEFT":
                if current_dir is None:
                    pass
                elif is_drive_root(current_dir):
                    current_dir = None
                    selected_index = 0
                    offset = 0
                    last_sig = None
                    dirty = True
                else:
                    current_dir = get_parent_path(current_dir)
                    selected_index = 0
                    offset = 0
                    last_sig = None
                    dirty = True

            elif key == "RIGHT":
                if items_mid:
                    new_path = items_mid[selected_index] if current_dir is None else os.path.join(current_dir, items_mid[selected_index])
                    if os.path.isdir(new_path):
                        enter_directory(new_path)
                    else:
                        open_selected(new_path)

            elif key == "ENTER":
                if items_mid:
                    new_path = items_mid[selected_index] if current_dir is None else os.path.join(current_dir, items_mid[selected_index])
                    if os.path.isdir(new_path):
                        enter_directory(new_path)
                    else:
                        action_message = handle_enter_action(new_path)
                        action_message_until = time.monotonic() + 1.5
                        dirty = True

            elif key == "/":
                search_mode = True
                filter_mode = False
                search_query = ""
                selected_index = 0
                offset = 0
                last_sig = None
                dirty = True

            elif key == "f":
                filter_mode = True
                search_mode = False
                ext_filter = ""
                selected_index = 0
                offset = 0
                last_sig = None
                dirty = True

            elif key == "h":
                go_back_history()

            elif key == "l":
                go_forward_history()

            elif key == "b":
                if current_dir is not None:
                    if current_dir in bookmarks:
                        bookmarks.remove(current_dir)
                        action_message = "Usunięto zakładkę"
                    else:
                        if len(bookmarks) >= BOOKMARK_LIMIT:
                            bookmarks.pop(0)
                        bookmarks.append(current_dir)
                        action_message = "Dodano zakładkę"
                    action_message_until = time.monotonic() + 1.2
                    dirty = True

            elif key == "TAB":
                if bookmarks:
                    save_view_state(current_dir)
                    current_dir = bookmarks[0]
                    bookmarks = bookmarks[1:] + [current_dir]
                    restore_view_state(current_dir)
                    last_sig = None
                    dirty = True

            elif key == "s":
                sort_mode_index = (sort_mode_index + 1) % len(SORT_MODES)
                dirty = True

            elif key == "r":
                reverse_sort = not reverse_sort
                dirty = True

            elif key == " ":
                if sel_full:
                    if sel_full in marked_paths:
                        marked_paths.remove(sel_full)
                    else:
                        marked_paths.add(sel_full)
                    dirty = True

            elif key == "c":
                targets = collect_targets(current_dir, sel_item, marked_paths)
                if targets:
                    clipboard = {"mode": "copy", "paths": targets[:]}
                    action_message = f"Skopiowano do schowka: {len(targets)}"
                    action_message_until = time.monotonic() + 1.5
                    dirty = True

            elif key == "m":
                targets = collect_targets(current_dir, sel_item, marked_paths)
                if targets:
                    clipboard = {"mode": "move", "paths": targets[:]}
                    action_message = f"Przeniesiono do schowka: {len(targets)}"
                    action_message_until = time.monotonic() + 1.5
                    dirty = True

            elif key == "p":
                if clipboard and current_dir is not None:
                    op_state = make_operation(clipboard["mode"], clipboard["paths"], current_dir)
                    action_message = "Uruchomiono wklejanie"
                    action_message_until = time.monotonic() + 1.2
                    dirty = True
                else:
                    action_message = "Brak schowka albo brak folderu docelowego"
                    action_message_until = time.monotonic() + 1.5
                    dirty = True

            elif key == "d":
                targets = collect_targets(current_dir, sel_item, marked_paths)
                if targets:
                    confirm_delete = True
                    delete_targets = targets[:]
                    dirty = True

            elif key == "e":
                if sel_full and os.path.exists(sel_full):
                    if os.path.isdir(sel_full):
                        open_selected(sel_full)
                    else:
                        open_in_editor(sel_full)

            elif key == "t":
                stop_audio()
                action_message = "Zatrzymano audio"
                action_message_until = time.monotonic() + 1.0
                dirty = True

        status_text = action_message if action_message else f"Wybrane: {sel_full if sel_full else '<nic nie zaznaczono>'}"
        if display_width(status_text) > w and (time.monotonic() - status_last_tick) >= SCROLL_INTERVAL:
            status_scroll += 1
            status_last_tick = time.monotonic()
            dirty = True

        if dirty:
            out = []
            out.append("\033[2J\033[H")

            header = current_dir if current_dir is not None else "MÓJ KOMPUTER"
            if current_dir is None and bookmarks:
                header += f"   [zakładka: {len(bookmarks)}]"
            out.append(f"{C_DOC}{fit_text(header, w)}{C_RESET}\n")
            out.append(f"{C_LINE}{'━' * max(1, w)}{C_RESET}\n")

            for i in range(max_rows):
                line = ""

                if i < len(items_left):
                    it = items_left[i]
                    if parent_path is None:
                        is_d = True
                    else:
                        is_d = os.path.isdir(os.path.join(parent_path, it))
                    line += format_line(it, is_d, w1, dim=True)
                else:
                    line += " " * w1

                idx_mid = i + offset
                if idx_mid < len(items_mid):
                    it = items_mid[idx_mid]
                    full = it if current_dir is None else os.path.join(current_dir, it)
                    is_d = os.path.isdir(full)
                    marked = full in marked_paths
                    line += format_line(it, is_d, w2, selected=(idx_mid == selected_index), marked=marked)
                else:
                    line += " " * w2

                if i < len(info_lines_cache):
                    kind, content = info_lines_cache[i]
                    if kind == "img":
                        visible = display_width(strip_ansi(content))
                        line += content
                        if visible < w3:
                            line += " " * (w3 - visible)
                    else:
                        clean = fit_text(content, w3)
                        line += f"{C_INFO}{clean}{C_RESET}"
                else:
                    line += " " * w3

                out.append(line + "\n")

            out.append(f"{C_LINE}{'━' * max(1, w)}{C_RESET}\n")

            if confirm_delete:
                prompt = f"Usunąć {len(delete_targets)} element(ów)? (y/n)"
                out.append(f"{C_WARN}{fit_text(prompt, w)}{C_RESET}\n")
            elif op_state is not None and not op_state.get("finished"):
                bar = format_progress_bar(op_state["done"], op_state["total"], width=max(8, min(32, w // 3)))
                pct = int((op_state["done"] / max(1, op_state["total"])) * 100)
                current = clean_text(op_state.get("current", ""))
                if current:
                    current = os.path.basename(current.rstrip("\\/"))
                msg = f"{op_state['kind'].upper()} {bar} {pct}%  {current}"
                if op_state.get("conflict") is not None:
                    msg = f"Konflikt nazwy: y=nadpisz | n=pomiń | r=zmień nazwę | esc=anuluj  |  {msg}"
                out.append(f"{C_WARN}{fit_text(msg, w)}{C_RESET}\n")
            else:
                if display_width(status_text) > w:
                    status_view = marquee_text(status_text, w, status_scroll)
                else:
                    status_view = fit_text(status_text, w)
                out.append(f"{C_INFO}{status_view}{C_RESET}\n")

            out.append(f"{C_LINE}{'━' * max(1, w)}{C_RESET}\n")
            wrapped_controls = []
            for ctrl_line in controls_lines:
                wrapped_controls.extend(wrap_text_lines(ctrl_line, w))
            for idx, ctrl_line in enumerate(wrapped_controls):
                out.append(f"{C_INFO}{fit_text(ctrl_line, w)}{C_RESET}")
                if idx < len(wrapped_controls) - 1:
                    out.append("\n")

            sys.stdout.write("".join(out))
            sys.stdout.flush()
            dirty = False

        time.sleep(0.03)


if __name__ == "__main__":
    sys.stdout.write("\033[?25h")
    try:
        main()
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
