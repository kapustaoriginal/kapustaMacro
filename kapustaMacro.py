# Create By: kapusta_original and Gemini Pro 3.1, Gemini 4 Argon, Claude Sonnet 5.5.

import ctypes
from ctypes import wintypes
import difflib
import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox


try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CFG_DIR = os.path.join(BASE_DIR, "cfg")
SETTINGS_FILE = os.path.join(CFG_DIR, "settings.json")
DEFAULT_SEQ_FILE = os.path.join(CFG_DIR, "default.json")

# ============================================================
#                      НАСТРОЙКИ ПО УМОЛЧАНИЮ
# ============================================================

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080

START_STOP_KEY = "f6"
EXIT_KEY = "f8"
PIPETTE_KEY = "shift+c"
START_DELAY = 2
DEVICE_SWITCH_DELAY = 0 # Пауза при смене устройств
DEFAULT_TAP_INTERVAL = 0
DEFAULT_TAP_HOLD = 0
CURSOR_ROBLOX_FIX = True    # True = делать мгновенный сдвиг на 1px при наведении
REPEAT = 0
ACTIVE_CONFIG = "default.json"

DEFAULT_SEQUENCE = [
    
]

# ============================================================

SEQUENCE = list(DEFAULT_SEQUENCE)

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_ABSOLUTE = 0x8000

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12
VK_C = 0x43

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _anonymous_ = ("_ union",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("_ union", _INPUT_UNION),
    ]


KB_DEV = "key-macro-keyboard"
MOUSE_DEV = "key-macro-mouse"
ABS_DEV = "key-macro-abs-pointer"

MOUSE_BUTTONS = {
    "mouse_left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    "mouse_right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    "mouse_middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}

ALIASES = {
    "ctrl": "LEFTCTRL",
    "shift": "LEFTSHIFT",
    "alt": "LEFTALT",
    "win": "LEFTMETA",
    "enter": "ENTER",
    "esc": "ESC",
    "space": "SPACE",
    "tab": "TAB",
    "backspace": "BACKSPACE",
    "up": "UP",
    "down": "DOWN",
    "left": "LEFT",
    "right": "RIGHT",
}

VK_MAP = {
    "ESC": 0x1B, "ESCAPE": 0x1B,
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75,
    "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    "GRAVE": 0xC0, "MINUS": 0xBD, "EQUAL": 0xBB, "BACKSPACE": 0x08,
    "TAB": 0x09, "LEFTBRACE": 0xDB, "RIGHTBRACE": 0xDD, "BACKSLASH": 0xDC,
    "CAPSLOCK": 0x14, "SEMICOLON": 0xBA, "APOSTROPHE": 0xDE, "ENTER": 0x0D,
    "LEFTSHIFT": 0xA0, "RIGHTSHIFT": 0xA1, "COMMA": 0xBC, "DOT": 0xBE, "SLASH": 0xBF,
    "LEFTCTRL": 0xA2, "RIGHTCTRL": 0xA3, "LEFTMETA": 0x5B, "RIGHTMETA": 0x5C,
    "LEFTALT": 0xA4, "RIGHTALT": 0xA5, "SPACE": 0x20,
    "INSERT": 0x2D, "DELETE": 0x2E, "HOME": 0x24, "END": 0x23, "PAGEUP": 0x21, "PAGEDOWN": 0x22,
    "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27,
}
for _c in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    VK_MAP[_c] = ord(_c)

EXTENDED_VKS = {
    0xA3, 0xA5, 0x5B, 0x5C, 0x2D, 0x2E, 0x24, 0x23, 0x21, 0x22, 0x26, 0x28, 0x25, 0x27
}

stop_event = threading.Event()
worker = None
status_callback = None


def notify_status(text):
    print(text)
    if status_callback:
        try:
            status_callback(text)
        except Exception:
            pass


def get_cursor_pos():
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def copy_to_clipboard(text):
    try:
        p = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=True)
        p.communicate(input=text.encode("utf-16-le"))
        return p.returncode == 0, "clip"
    except Exception:
        return False, None


def handle_pipette_copy():
    x, y = get_cursor_pos()
    coord_text = f"{x}, {y}"
    ok, method = copy_to_clipboard(coord_text)
    if ok:
        notify_status(f"[Пипетка] Скопировано: ({coord_text}) -> [\"cursor\", {x}, {y}, 1]")
    else:
        notify_status(f"[Пипетка] Координаты: {coord_text} (ошибка буфера)")


def resolve(name):
    name = name.lower()
    if name in MOUSE_BUTTONS:
        return MOUSE_DEV, MOUSE_BUTTONS[name]
    key_name = ALIASES.get(name, name.upper())
    if key_name.startswith("KEY_"):
        key_name = key_name[4:]
    vk = VK_MAP.get(key_name)
    if vk is None:
        raise ValueError(f"Неизвестная клавиша: {name!r}")
    return KB_DEV, vk


_last_dev = None
_dev_lock = threading.Lock()


def switch_to(dev):
    """Если устройство сменилось и DEVICE_SWITCH_DELAY > 0, подождать перед действием."""
    global _last_dev
    with _dev_lock:
        prev = _last_dev
        _last_dev = dev
    if prev is not None and prev != dev and DEVICE_SWITCH_DELAY > 0:
        return sleep(DEVICE_SWITCH_DELAY)
    return not stop_event.is_set()


def send_key_event(vk, is_up=False):
    scan = user32.MapVirtualKeyW(vk, 0)
    flags = KEYEVENTF_SCANCODE
    if is_up:
        flags |= KEYEVENTF_KEYUP
    if vk in EXTENDED_VKS:
        flags |= KEYEVENTF_EXTENDEDKEY
    inp = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def send_mouse_move_rel(dx, dy):
    """Относительный сдвиг реальной мыши."""
    inp = INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(dx=dx, dy=dy, dwFlags=MOUSEEVENTF_MOVE))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def send_mouse_button(flags):
    inp = INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(dx=0, dy=0, dwFlags=flags))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def press(dev, code):
    switch_to(dev)
    if dev == MOUSE_DEV:
        send_mouse_button(code[0])
    else:
        send_key_event(code, is_up=False)


def release(dev, code):
    switch_to(dev)
    if dev == MOUSE_DEV:
        send_mouse_button(code[1])
    else:
        send_key_event(code, is_up=True)


def resolve_combo(name):
    return [resolve(part.strip()) for part in name.split("+")]


def press_all(keys):
    for dev, code in keys:
        press(dev, code)


def release_all(keys):
    for dev, code in reversed(keys):
        release(dev, code)


def sleep(seconds):
    if seconds <= 0:
        return not stop_event.is_set()
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if stop_event.is_set():
            return False
        time.sleep(min(0.01, max(0, end - time.monotonic())))
    return not stop_event.is_set()


def do_hold(key_name, seconds):
    keys = resolve_combo(key_name)
    press_all(keys)
    try:
        sleep(seconds)
    finally:
        release_all(keys)


def do_tap(key_name, times=1, interval=None, hold_time=None):
    if interval is None:
        interval = DEFAULT_TAP_INTERVAL
    if hold_time is None:
        hold_time = DEFAULT_TAP_HOLD
    keys = resolve_combo(key_name)
    for _ in range(int(times)):
        if stop_event.is_set():
            return
        press_all(keys)
        if hold_time > 0:
            time.sleep(hold_time)
        release_all(keys)
        if interval > 0 and not sleep(interval):
            return


def do_spam(key_name, seconds, per_second):
    keys = resolve_combo(key_name)
    delay = 1.0 / per_second if per_second > 0 else 0
    end = time.monotonic() + seconds
    while time.monotonic() < end and not stop_event.is_set():
        press_all(keys)
        release_all(keys)
        if delay > 0:
            sleep(delay)


def do_cursor(x, y, delay=0.0):
    target_x = max(0, min(SCREEN_WIDTH - 1, int(x)))
    target_y = max(0, min(SCREEN_HEIGHT - 1, int(y)))

    switch_to(ABS_DEV)

    user32.SetCursorPos(target_x, target_y)
    if CURSOR_ROBLOX_FIX:
        send_mouse_move_rel(1, 1)
        send_mouse_move_rel(-1, -1)
        user32.SetCursorPos(target_x, target_y)

    if delay > 0:
        sleep(delay)


def do_parallel(steps):
    threads = [threading.Thread(target=run_step, args=(s,)) for s in steps]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def run_step(step):
    action = step[0]
    if action == "hold":
        do_hold(*step[1:])
    elif action == "tap":
        do_tap(*step[1:])
    elif action == "spam":
        do_spam(*step[1:])
    elif action == "wait":
        sleep(step[1])
    elif action == "cursor":
        do_cursor(*step[1:])
    elif action == "parallel":
        do_parallel(step[1])
    else:
        raise ValueError(f"Неизвестное действие: {action!r}")


ARITY = {
    "hold": (2, 2),
    "tap": (1, 4),
    "spam": (3, 3),
    "wait": (1, 1),
    "cursor": (2, 3),
}
PREPARED = []


def validate(step):
    if not step:
        raise ValueError("Пустой шаг в SEQUENCE")
    action = step[0]
    if action == "parallel":
        for sub in step[1]:
            validate(sub)
        return
    if action not in ARITY:
        hint = difflib.get_close_matches(str(action), list(ARITY) + ["parallel"], n=1)
        extra = f" Может, {hint[0]!r}?" if hint else ""
        raise ValueError(f"Неизвестное действие {action!r} в шаге {step}.{extra}")
    lo, hi = ARITY[action]
    n = len(step) - 1
    if not lo <= n <= hi:
        raise ValueError(
            f"Неверное число аргументов в шаге {step}: нужно {lo}-{hi}, получено {n}"
        )
    nums = step[1:] if action in ("wait", "cursor") else step[2:]
    for v in nums:
        if not isinstance(v, (int, float)):
            raise ValueError(f"Ожидалось число, а в шаге {step} стоит {v!r}")
    if action not in ("wait", "cursor"):
        resolve_combo(step[1])


def to_num(v):
    if isinstance(v, str):
        try:
            f = float(v.replace(",", "."))
        except ValueError:
            return v
        return int(f) if f.is_integer() else f
    return v


def normalize(step):
    step = tuple(step)
    if not step:
        return step
    if isinstance(step[0], str):
        step = (step[0].strip().lower(),) + step[1:]
    if step[0] == "parallel":
        if len(step) >= 2 and isinstance(step[1], (list, tuple)):
            return ("parallel", [normalize(s) for s in step[1]])
        return ("parallel",) + normalize(step[1:])
    if step[0] in ("wait", "cursor"):
        return (step[0],) + tuple(to_num(v) for v in step[1:])
    return step[:2] + tuple(to_num(v) for v in step[2:])


def prepare(sequence):
    result, group = [], []

    def flush():
        if group:
            result.append(("parallel", list(group)))
            group.clear()

    for step in map(normalize, sequence):
        if step and step[0] == "parallel":
            if len(step) >= 2 and isinstance(step[1], (list, tuple)):
                flush()
                result.append(("parallel", [tuple(s) for s in step[1]]))
            else:
                group.append(tuple(step[1:]))
        else:
            flush()
            result.append(step)
    flush()

    for step in result:
        validate(step)
    return result


def macro():
    notify_status(f"Старт через {START_DELAY} с...")
    if not sleep(START_DELAY):
        notify_status("Остановлено.")
        return

    n = 0
    while not stop_event.is_set():
        n += 1
        notify_status(f"Выполняется: проход {n} ({ACTIVE_CONFIG})")
        for step in PREPARED:
            if stop_event.is_set():
                break
            print("  ->", step)
            run_step(step)
        if REPEAT and n >= REPEAT:
            break

    stop_event.set()
    notify_status(f"Готов. ({START_STOP_KEY.upper()} - старт/стоп)")


def toggle():
    global worker
    if worker and worker.is_alive():
        stop_event.set()
        notify_status("Останавливаю...")
    else:
        if not PREPARED:
            notify_status("Ошибка: SEQUENCE пуст или содержит ошибку!")
            return
        stop_event.clear()
        worker = threading.Thread(target=macro, daemon=True)
        worker.start()


def is_key_down(vk):
    return (user32.GetAsyncKeyState(vk) & 0x8000) != 0


def parse_hotkey(hotkey_str):
    """Преобразует строку вида 'shift+c' или 'f6' в список кодов VK."""
    if not hotkey_str or not str(hotkey_str).strip():
        return []
    vks = []
    for part in str(hotkey_str).split("+"):
        p = part.strip().lower()
        if not p:
            continue
        if p in ("ctrl", "control"):
            vks.append(VK_CONTROL)
        elif p == "shift":
            vks.append(VK_SHIFT)
        elif p == "alt":
            vks.append(VK_MENU)
        else:
            dev, vk = resolve(p)
            if dev != KB_DEV:
                raise ValueError(f"В горячей клавише нельзя использовать мышь: {p}")
            vks.append(vk)
    return vks


def is_hotkey_pressed(vks):
    """Проверяет, зажаты ли все клавиши комбинации прямо сейчас."""
    if not vks:
        return False
    for vk in vks[:-1]:
        if not is_key_down(vk):
            return False
    return is_key_down(vks[-1])


def ensure_cfg_files():
    """Создаёт папку cfg, settings.json и default.json, если их ещё нет."""
    os.makedirs(CFG_DIR, exist_ok=True)

    if not os.path.exists(DEFAULT_SEQ_FILE):
        with open(DEFAULT_SEQ_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_SEQUENCE, f, indent=4, ensure_ascii=False)

    if not os.path.exists(SETTINGS_FILE):
        save_settings()


def save_settings():
    os.makedirs(CFG_DIR, exist_ok=True)
    data = {
        "screen_width": SCREEN_WIDTH,
        "screen_height": SCREEN_HEIGHT,
        "start_stop_key": START_STOP_KEY,
        "exit_key": EXIT_KEY,
        "pipette_key": PIPETTE_KEY,
        "start_delay": START_DELAY,
        "device_switch_delay": DEVICE_SWITCH_DELAY,
        "default_tap_interval": DEFAULT_TAP_INTERVAL,
        "default_tap_hold": DEFAULT_TAP_HOLD,
        "cursor_roblox_fix": CURSOR_ROBLOX_FIX,
        "repeat": REPEAT,
        "active_config": ACTIVE_CONFIG,
    }
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_settings():
    global SCREEN_WIDTH, SCREEN_HEIGHT, START_STOP_KEY, EXIT_KEY, PIPETTE_KEY
    global START_DELAY, DEVICE_SWITCH_DELAY, DEFAULT_TAP_INTERVAL, DEFAULT_TAP_HOLD
    global CURSOR_ROBLOX_FIX, REPEAT, ACTIVE_CONFIG

    ensure_cfg_files()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        SCREEN_WIDTH = int(data.get("screen_width", SCREEN_WIDTH))
        SCREEN_HEIGHT = int(data.get("screen_height", SCREEN_HEIGHT))
        START_STOP_KEY = str(data.get("start_stop_key", START_STOP_KEY))
        EXIT_KEY = str(data.get("exit_key", EXIT_KEY))
        PIPETTE_KEY = str(data.get("pipette_key", PIPETTE_KEY))
        START_DELAY = float(data.get("start_delay", START_DELAY))
        DEVICE_SWITCH_DELAY = float(data.get("device_switch_delay", DEVICE_SWITCH_DELAY))
        DEFAULT_TAP_INTERVAL = float(data.get("default_tap_interval", DEFAULT_TAP_INTERVAL))
        DEFAULT_TAP_HOLD = float(data.get("default_tap_hold", DEFAULT_TAP_HOLD))
        CURSOR_ROBLOX_FIX = bool(data.get("cursor_roblox_fix", CURSOR_ROBLOX_FIX))
        REPEAT = int(data.get("repeat", REPEAT))
        ACTIVE_CONFIG = str(data.get("active_config", ACTIVE_CONFIG))
    except Exception as e:
        print(f"Ошибка чтения settings.json: {e}")


def list_sequence_configs():
    """Сканирует папку cfg и возвращает список всех json-конфигов (кроме settings.json)."""
    os.makedirs(CFG_DIR, exist_ok=True)
    files = []
    for fname in os.listdir(CFG_DIR):
        if fname.lower().endswith(".json") and fname.lower() != "settings.json":
            files.append(fname)
    files.sort()
    return files


def load_sequence_file(filename):
    """Загружает SEQUENCE из выбранного файла в папке cfg."""
    global SEQUENCE, PREPARED, ACTIVE_CONFIG
    path = os.path.join(CFG_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Файл не найден: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if isinstance(raw, dict) and "sequence" in raw:
        seq_data = raw["sequence"]
    elif isinstance(raw, list):
        seq_data = raw
    else:
        raise ValueError("JSON должен содержать список шагов [...]")

    PREPARED = prepare(seq_data)
    SEQUENCE = seq_data
    ACTIVE_CONFIG = filename
    return len(PREPARED)


class MacroGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Kapusta Macro")
        self.root.resizable(False, False)

        global status_callback
        status_callback = self.set_status_safe

        self.start_vks = []
        self.exit_vks = []
        self.pipette_vks = []
        self.rebinding_Callback = None

        self._build_ui()
        self._load_into_ui()
        self._apply_hotkeys()

        self.listener_running = True
        self.listener_thread = threading.Thread(target=self._hotkey_loop, daemon=True)
        self.listener_thread.start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}

        # --- Блок выбора конфига SEQUENCE ---
        cfg_frame = ttk.LabelFrame(self.root, text="Конфиг SEQUENCE (папка cfg)")
        cfg_frame.pack(fill="x", **pad)

        ttk.Label(cfg_frame, text="Файл:").grid(row=0, column=0, padx=6, pady=8, sticky="w")

        self.config_var = tk.StringVar()
        self.config_combo = ttk.Combobox(
            cfg_frame,
            textvariable=self.config_var,
            state="readonly",
            width=28,
            postcommand=self.refresh_config_list,
        )
        self.config_combo.grid(row=0, column=1, padx=6, pady=8)
        self.config_combo.bind("<<ComboboxSelected>>", self.on_config_selected)

        ttk.Button(cfg_frame, text="Открыть папку cfg", command=self.open_cfg_folder).grid(
            row=0, column=2, padx=6, pady=8
        )

        hk_frame = ttk.LabelFrame(self.root, text="Горячие клавиши (например: f6, f8, shift+c)")
        hk_frame.pack(fill="x", **pad)

        ttk.Label(hk_frame, text="Старт / Стоп:").grid(row=0, column=0, padx=6, pady=4, sticky="w")
        self.start_key_var = tk.StringVar()
        ttk.Entry(hk_frame, textvariable=self.start_key_var, width=16).grid(row=0, column=1, padx=6, pady=4)

        ttk.Label(hk_frame, text="Выход из программы:").grid(row=1, column=0, padx=6, pady=4, sticky="w")
        self.exit_key_var = tk.StringVar()
        ttk.Entry(hk_frame, textvariable=self.exit_key_var, width=16).grid(row=1, column=1, padx=6, pady=4)

        ttk.Label(hk_frame, text="Копировать координаты:").grid(row=2, column=0, padx=6, pady=4, sticky="w")
        self.pipette_key_var = tk.StringVar()
        ttk.Entry(hk_frame, textvariable=self.pipette_key_var, width=16).grid(row=2, column=1, padx=6, pady=4)

        set_frame = ttk.LabelFrame(self.root, text="Параметры (settings.json)")
        set_frame.pack(fill="x", **pad)

        ttk.Label(set_frame, text="Разрешение (Ш x В):").grid(row=0, column=0, padx=6, pady=4, sticky="w")
        res_box = ttk.Frame(set_frame)
        res_box.grid(row=0, column=1, padx=6, pady=4, sticky="w")
        self.width_var = tk.StringVar()
        self.height_var = tk.StringVar()
        ttk.Entry(res_box, textvariable=self.width_var, width=7).pack(side="left")
        ttk.Label(res_box, text=" x ").pack(side="left")
        ttk.Entry(res_box, textvariable=self.height_var, width=7).pack(side="left")

        ttk.Label(set_frame, text="Задержка перед стартом (с):").grid(row=1, column=0, padx=6, pady=4, sticky="w")
        self.start_delay_var = tk.StringVar()
        ttk.Entry(set_frame, textvariable=self.start_delay_var, width=16).grid(row=1, column=1, padx=6, pady=4, sticky="w")

        ttk.Label(set_frame, text="DEVICE_SWITCH_DELAY (с):").grid(row=2, column=0, padx=6, pady=4, sticky="w")
        self.switch_delay_var = tk.StringVar()
        ttk.Entry(set_frame, textvariable=self.switch_delay_var, width=16).grid(row=2, column=1, padx=6, pady=4, sticky="w")

        ttk.Label(set_frame, text="Пауза tap по умолч. (с):").grid(row=3, column=0, padx=6, pady=4, sticky="w")
        self.tap_interval_var = tk.StringVar()
        ttk.Entry(set_frame, textvariable=self.tap_interval_var, width=16).grid(row=3, column=1, padx=6, pady=4, sticky="w")

        ttk.Label(set_frame, text="Удержание tap по умолч. (с):").grid(row=4, column=0, padx=6, pady=4, sticky="w")
        self.tap_hold_var = tk.StringVar()
        ttk.Entry(set_frame, textvariable=self.tap_hold_var, width=16).grid(row=4, column=1, padx=6, pady=4, sticky="w")

        ttk.Label(set_frame, text="Повторов (0 = бесконечно):").grid(row=5, column=0, padx=6, pady=4, sticky="w")
        self.repeat_var = tk.StringVar()
        ttk.Entry(set_frame, textvariable=self.repeat_var, width=16).grid(row=5, column=1, padx=6, pady=4, sticky="w")

        self.roblox_fix_var = tk.BooleanVar()
        ttk.Checkbutton(
            set_frame,
            text="Фикс наведения курсора для Roblox (1px)",
            variable=self.roblox_fix_var,
        ).grid(row=6, column=0, columnspan=2, padx=6, pady=4, sticky="w")

        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", **pad)

        ttk.Button(btn_frame, text="Сохранить настройки", command=self.save_from_ui).pack(
            side="left", expand=True, fill="x", padx=4
        )
        ttk.Button(btn_frame, text="Старт / Стоп макроса", command=toggle).pack(
            side="left", expand=True, fill="x", padx=4
        )

        self.status_var = tk.StringVar(value="Готов к работе.")
        status_lbl = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w")
        status_lbl.pack(fill="x", padx=10, pady=(2, 10), ipady=3)

    def refresh_config_list(self):
        """Обновляет список файлов в выпадающем меню при каждом открытии."""
        files = list_sequence_configs()
        self.config_combo["values"] = files
        return files

    def _load_into_ui(self):
        files = self.refresh_config_list()
        if ACTIVE_CONFIG in files:
            self.config_var.set(ACTIVE_CONFIG)
        elif files:
            self.config_var.set(files[0])

        self.start_key_var.set(START_STOP_KEY)
        self.exit_key_var.set(EXIT_KEY)
        self.pipette_key_var.set(PIPETTE_KEY)

        self.width_var.set(str(SCREEN_WIDTH))
        self.height_var.set(str(SCREEN_HEIGHT))
        self.start_delay_var.set(str(START_DELAY))
        self.switch_delay_var.set(str(DEVICE_SWITCH_DELAY))
        self.tap_interval_var.set(str(DEFAULT_TAP_INTERVAL))
        self.tap_hold_var.set(str(DEFAULT_TAP_HOLD))
        self.repeat_var.set(str(REPEAT))
        self.roblox_fix_var.set(CURSOR_ROBLOX_FIX)

        if self.config_var.get():
            self.on_config_selected()

    def on_config_selected(self, event=None):
        chosen = self.config_var.get()
        if not chosen:
            return
        try:
            count = load_sequence_file(chosen)
            save_settings()
            self.set_status_safe(f"Загружен {chosen} (шагов: {count})")
        except Exception as e:
            messagebox.showerror("Ошибка в конфиге SEQUENCE", f"Не удалось загрузить {chosen}:\n{e}")

    def _apply_hotkeys(self):
        self.start_vks = parse_hotkey(START_STOP_KEY)
        self.exit_vks = parse_hotkey(EXIT_KEY)
        self.pipette_vks = parse_hotkey(PIPETTE_KEY)

    def save_from_ui(self):
        global SCREEN_WIDTH, SCREEN_HEIGHT, START_STOP_KEY, EXIT_KEY, PIPETTE_KEY
        global START_DELAY, DEVICE_SWITCH_DELAY, DEFAULT_TAP_INTERVAL, DEFAULT_TAP_HOLD
        global CURSOR_ROBLOX_FIX, REPEAT

        try:
            new_start_key = self.start_key_var.get().strip().lower()
            new_exit_key = self.exit_key_var.get().strip().lower()
            new_pipette_key = self.pipette_key_var.get().strip().lower()

            parse_hotkey(new_start_key)
            parse_hotkey(new_exit_key)
            parse_hotkey(new_pipette_key)

            SCREEN_WIDTH = int(self.width_var.get())
            SCREEN_HEIGHT = int(self.height_var.get())
            START_DELAY = float(self.start_delay_var.get().replace(",", "."))
            DEVICE_SWITCH_DELAY = float(self.switch_delay_var.get().replace(",", "."))
            DEFAULT_TAP_INTERVAL = float(self.tap_interval_var.get().replace(",", "."))
            DEFAULT_TAP_HOLD = float(self.tap_hold_var.get().replace(",", "."))
            REPEAT = int(self.repeat_var.get())
            CURSOR_ROBLOX_FIX = bool(self.roblox_fix_var.get())

            START_STOP_KEY = new_start_key
            EXIT_KEY = new_exit_key
            PIPETTE_KEY = new_pipette_key

            self._apply_hotkeys()
            if self.config_var.get():
                load_sequence_file(self.config_var.get())
            save_settings()
            self.set_status_safe("Настройки сохранены в cfg/settings.json!")
        except Exception as e:
            messagebox.showerror("Ошибка настроек", str(e))

    def open_cfg_folder(self):
        os.makedirs(CFG_DIR, exist_ok=True)
        os.startfile(CFG_DIR)

    def set_status_safe(self, text):
        self.root.after(0, lambda: self.status_var.set(text))

    def _hotkey_loop(self):
        prev_start = False
        prev_exit = False
        prev_pipette = False
        prev_ctrl_c = False

        while self.listener_running:
            start_down = is_hotkey_pressed(self.start_vks)
            exit_down = is_hotkey_pressed(self.exit_vks)
            pipette_down = is_hotkey_pressed(self.pipette_vks)
            ctrl_c_down = is_key_down(VK_CONTROL) and is_key_down(VK_C)

            if start_down and not prev_start:
                toggle()

            if (exit_down and not prev_exit) or (ctrl_c_down and not prev_ctrl_c):
                stop_event.set()
                self.root.after(0, self.on_close)
                return

            if pipette_down and not prev_pipette:
                handle_pipette_copy()

            prev_start = start_down
            prev_exit = exit_down
            prev_pipette = pipette_down
            prev_ctrl_c = ctrl_c_down

            time.sleep(0.015)

    def on_close(self):
        self.listener_running = False
        stop_event.set()
        self.root.destroy()


def run_pipette():
    print("=== Режим пипетки (Windows) ===")
    print(f"  {PIPETTE_KEY.upper()} - скопировать координаты в буфер обмена")
    print(f"  Ctrl + C  - выход (или {EXIT_KEY.upper()})")

    do_cursor(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)

    pipette_vks = parse_hotkey(PIPETTE_KEY)
    exit_vks = parse_hotkey(EXIT_KEY)

    last_print = 0.0
    prev_pip = False
    prev_exit = False

    try:
        while True:
            pip_down = is_hotkey_pressed(pipette_vks)
            exit_down = is_hotkey_pressed(exit_vks)

            if is_key_down(VK_CONTROL) and is_key_down(VK_C):
                print("\nВыход по Ctrl + C.")
                return

            if pip_down and not prev_pip:
                handle_pipette_copy()

            if exit_down and not prev_exit:
                print(f"\nВыход по {EXIT_KEY.upper()}.")
                return

            prev_pip = pip_down
            prev_exit = exit_down

            now = time.monotonic()
            if now - last_print >= 0.1:
                x, y = get_cursor_pos()
                print(f"\rТекущие координаты: X={x:<4} Y={y:<4}   ", end="", flush=True)
                last_print = now

            time.sleep(0.015)
    except KeyboardInterrupt:
        print("\nВыход из пипетки.")


def main():
    load_settings()

    if len(sys.argv) > 1 and sys.argv[1] == "--pipette":
        run_pipette()
        return

    root = tk.Tk()
    app = MacroGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()