#!/usr/bin/env python3
"""
Макрос клавиш и мыши для Wayland (KDE Plasma) через evdev/uinput.

Горячие клавиши (работают глобально, даже в игре):
  F6        - запустить / остановить макрос
  F8        - выйти из программы
  Ctrl + C  - глобальный выход из программы
  Shift + C - скопировать текущие координаты курсора в буфер обмена
"""

import difflib
import os
import re
import select
import shutil
import subprocess
import sys
import threading
import time

from evdev import AbsInfo, InputDevice, UInput, ecodes, list_devices

# ============================================================
#                      НАСТРОЙКИ
# ============================================================

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080

START_STOP_KEY = ecodes.KEY_F6   # старт / стоп
EXIT_KEY = ecodes.KEY_F8         # выход из программы

START_DELAY = 1     # секунд до начала после F6
REPEAT = 0          # сколько раз повторить последовательность; 0 = бесконечно
DEVICE_SWITCH_DELAY = 0.4   # пауза при смене устройства (курсор <-> клик)

# Типы действий:
#   ("hold",   клавиша, секунды)                 - зажать клавишу на N секунд
#   ("tap",    клавиша, раз, пауза_между)        - быстро нажать N раз
#   ("spam",   клавиша, секунды, нажатий_в_сек)  - быстро кликать N секунд
#   ("wait",   секунды)                          - пауза
#   ("cursor", x, y, пауза_после)                - переместить курсор в (X, Y) и подождать N секунд
#   ("parallel", действие, аргументы...)         - параллельное выполнение соседних строк

SEQUENCE = [
    ("tap", "mouse_left", "1"),
]

# ============================================================
#                         КОД
# ============================================================

KB_NAME = "key-macro-keyboard"
MOUSE_NAME = "key-macro-mouse"
ABS_NAME = "key-macro-abs-pointer"

MOUSE_BUTTONS = {
    "mouse_left": ecodes.BTN_LEFT,
    "mouse_right": ecodes.BTN_RIGHT,
    "mouse_middle": ecodes.BTN_MIDDLE,
}

ALIASES = {
    "ctrl": "KEY_LEFTCTRL",
    "shift": "KEY_LEFTSHIFT",
    "alt": "KEY_LEFTALT",
    "win": "KEY_LEFTMETA",
    "enter": "KEY_ENTER",
    "esc": "KEY_ESC",
    "space": "KEY_SPACE",
    "tab": "KEY_TAB",
    "backspace": "KEY_BACKSPACE",
    "up": "KEY_UP",
    "down": "KEY_DOWN",
    "left": "KEY_LEFT",
    "right": "KEY_RIGHT",
}

CTRL_CODES = {ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL}
SHIFT_CODES = {ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT}

try:
    kb_ui = UInput({ecodes.EV_KEY: list(range(1, 249))}, name=KB_NAME)
    mouse_ui = UInput(
        {
            ecodes.EV_KEY: list(MOUSE_BUTTONS.values()),
            ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y],
        },
        name=MOUSE_NAME,
    )
    abs_caps = {
        ecodes.EV_KEY: [ecodes.BTN_TOUCH, ecodes.BTN_LEFT],
        ecodes.EV_ABS: [
            (ecodes.ABS_X, AbsInfo(value=0, min=0, max=SCREEN_WIDTH - 1, fuzz=0, flat=0, resolution=0)),
            (ecodes.ABS_Y, AbsInfo(value=0, min=0, max=SCREEN_HEIGHT - 1, fuzz=0, flat=0, resolution=0)),
        ],
    }
    try:
        abs_ui = UInput(abs_caps, name=ABS_NAME, input_props=[ecodes.INPUT_PROP_DIRECT])
    except TypeError:
        abs_ui = UInput(abs_caps, name=ABS_NAME)
except PermissionError:
    raise SystemExit(
        "Нет доступа к /dev/uinput. Добавь правило udev и группу input "
        "или запусти через sudo."
    )

stop_event = threading.Event()
worker = None

tracked_x = SCREEN_WIDTH // 2
tracked_y = SCREEN_HEIGHT // 2


def get_user_env():
    env = os.environ.copy()
    sudo_uid = env.get("SUDO_UID")
    sudo_user = env.get("SUDO_USER")

    if sudo_uid and sudo_user:
        runtime_dir = f"/run/user/{sudo_uid}"
        env["XDG_RUNTIME_DIR"] = runtime_dir
        env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={runtime_dir}/bus"
        if "WAYLAND_DISPLAY" not in env and os.path.isdir(runtime_dir):
            for fname in os.listdir(runtime_dir):
                if fname.startswith("wayland-") and not fname.endswith(".lock"):
                    env["WAYLAND_DISPLAY"] = fname
                    break
        return sudo_user, env
    return None, env


def run_as_user(cmd, input_text=None):
    sudo_user, env = get_user_env()
    if sudo_user and os.geteuid() == 0:
        keep = ("XDG_RUNTIME_DIR", "WAYLAND_DISPLAY", "DISPLAY", "DBUS_SESSION_BUS_ADDRESS")
        env_vars = [f"{k}={v}" for k, v in env.items() if k in keep]
        full_cmd = ["sudo", "-u", sudo_user, "env"] + env_vars + cmd
    else:
        full_cmd = cmd

    return subprocess.run(
        full_cmd,
        input=input_text.encode("utf-8") if input_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        timeout=1.5,
        check=False,
    )


def get_cursor_pos():
    for qdbus_bin in ("qdbus6", "qdbus", "qdbus-qt5"):
        if shutil.which(qdbus_bin):
            res = run_as_user([qdbus_bin, "org.kde.KWin", "/KWin", "org.kde.KWin.cursorPos"])
            if res.returncode == 0:
                nums = re.findall(r"-?\d+", res.stdout.decode("utf-8", errors="ignore"))
                if len(nums) >= 2:
                    return int(nums[0]), int(nums[1])

    if shutil.which("gdbus"):
        res = run_as_user([
            "gdbus", "call", "--session",
            "--dest", "org.kde.KWin",
            "--object-path", "/KWin",
            "--method", "org.kde.KWin.cursorPos",
        ])
        if res.returncode == 0:
            nums = re.findall(r"-?\d+", res.stdout.decode("utf-8", errors="ignore"))
            if len(nums) >= 2:
                return int(nums[0]), int(nums[1])

    if shutil.which("hyprctl"):
        res = run_as_user(["hyprctl", "cursorpos"])
        if res.returncode == 0:
            nums = re.findall(r"-?\d+", res.stdout.decode("utf-8", errors="ignore"))
            if len(nums) >= 2:
                return int(nums[0]), int(nums[1])

    return int(tracked_x), int(tracked_y)


def copy_to_clipboard(text):
    if shutil.which("wl-copy"):
        sudo_user, env = get_user_env()
        cmd = ["wl-copy", text]
        if sudo_user and os.geteuid() == 0:
            keep = ("XDG_RUNTIME_DIR", "WAYLAND_DISPLAY", "DISPLAY", "DBUS_SESSION_BUS_ADDRESS")
            env_vars = [f"{k}={v}" for k, v in env.items() if k in keep]
            cmd = ["sudo", "-u", sudo_user, "env"] + env_vars + cmd
        try:
            subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True, "wl-copy"
        except Exception:
            pass

    for qdbus_bin in ("qdbus6", "qdbus", "qdbus-qt5"):
        if shutil.which(qdbus_bin):
            res = run_as_user([qdbus_bin, "org.kde.klipper", "/klipper", "setClipboardContents", text])
            if res.returncode == 0:
                return True, "KDE Klipper"

    if shutil.which("gdbus"):
        res = run_as_user([
            "gdbus", "call", "--session",
            "--dest", "org.kde.klipper",
            "--object-path", "/klipper",
            "--method", "org.kde.klipper.klipper.setClipboardContents",
            text,
        ])
        if res.returncode == 0:
            return True, "KDE Klipper"

    if shutil.which("xclip"):
        res = run_as_user(["xclip", "-selection", "clipboard"], input_text=text)
        if res.returncode == 0:
            return True, "xclip"

    return False, None


def handle_pipette_copy():
    x, y = get_cursor_pos()
    coord_text = f"{x}, {y}"
    ok, method = copy_to_clipboard(coord_text)
    if ok:
        print(f"\n[Пипетка] Координаты ({coord_text}) скопированы ({method})!")
        print(f'          Для SEQUENCE: ("cursor", {x}, {y}, 1)')
    else:
        print(f"\n[Пипетка] Координаты: {coord_text} (установи wl-clipboard для автокопирования)")


def resolve(name):
    name = name.lower()
    if name in MOUSE_BUTTONS:
        return mouse_ui, MOUSE_BUTTONS[name]
    key_name = ALIASES.get(name, "KEY_" + name.upper())
    code = ecodes.ecodes.get(key_name)
    if code is None:
        raise ValueError(f"Неизвестная клавиша: {name!r}")
    return kb_ui, code


def press(dev, code):
    dev.write(ecodes.EV_KEY, code, 1)
    dev.syn()


def release(dev, code):
    dev.write(ecodes.EV_KEY, code, 0)
    dev.syn()


def resolve_combo(name):
    return [resolve(part.strip()) for part in name.split("+")]


def press_all(keys):
    for dev, code in keys:
        press(dev, code)


def release_all(keys):
    for dev, code in reversed(keys):
        release(dev, code)


def sleep(seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if stop_event.is_set():
            return False
        time.sleep(min(0.02, max(0, end - time.monotonic())))
    return not stop_event.is_set()


def do_hold(key_name, seconds):
    keys = resolve_combo(key_name)
    press_all(keys)
    try:
        sleep(seconds)
    finally:
        release_all(keys)


def do_tap(key_name, times=1, interval=0.05):
    keys = resolve_combo(key_name)
    for _ in range(int(times)):
        if stop_event.is_set():
            return
        press_all(keys)
        time.sleep(0.03)
        release_all(keys)
        if not sleep(interval):
            return


def do_spam(key_name, seconds, per_second):
    keys = resolve_combo(key_name)
    delay = 1.0 / per_second
    end = time.monotonic() + seconds
    while time.monotonic() < end and not stop_event.is_set():
        press_all(keys)
        time.sleep(0.01)
        release_all(keys)
        sleep(max(0, delay - 0.01))


def do_cursor(x, y, delay=0.0):
    global tracked_x, tracked_y
    target_x = max(0, min(SCREEN_WIDTH - 1, int(x)))
    target_y = max(0, min(SCREEN_HEIGHT - 1, int(y)))
    tracked_x, tracked_y = target_x, target_y

    abs_ui.write(ecodes.EV_ABS, ecodes.ABS_X, target_x)
    abs_ui.write(ecodes.EV_ABS, ecodes.ABS_Y, target_y)
    abs_ui.syn()

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
    "tap": (1, 3),
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
    print(f"Старт через {START_DELAY} с...")
    if not sleep(START_DELAY):
        print("Остановлено.")
        return

    n = 0
    while not stop_event.is_set():
        n += 1
        print(f"Проход {n}")
        for step in PREPARED:
            if stop_event.is_set():
                break
            print("  ->", step)
            run_step(step)
        if REPEAT and n >= REPEAT:
            break

    stop_event.set()
    print("Макрос завершён. F6 - запустить снова, F8 или Ctrl+C - выход.")


def toggle():
    global worker
    if worker and worker.is_alive():
        stop_event.set()
        print("Останавливаю...")
    else:
        stop_event.clear()
        worker = threading.Thread(target=macro, daemon=True)
        worker.start()


def find_devices():
    keyboards, mice = [], []
    virtual_names = {KB_NAME, MOUSE_NAME, ABS_NAME}
    for path in list_devices():
        try:
            dev = InputDevice(path)
        except (PermissionError, OSError):
            continue
        if dev.name in virtual_names:
            continue
        caps = dev.capabilities()
        key_caps = caps.get(ecodes.EV_KEY, [])
        rel_caps = caps.get(ecodes.EV_REL, [])

        if ecodes.KEY_C in key_caps or ecodes.KEY_F6 in key_caps:
            keyboards.append(dev)
        if ecodes.REL_X in rel_caps and ecodes.REL_Y in rel_caps:
            mice.append(dev)
    return keyboards, mice


def is_modifier_held(keyboards, mod_codes):
    for kb in keyboards:
        try:
            if set(kb.active_keys()) & mod_codes:
                return True
        except OSError:
            continue
    return False


def run_pipette():
    global tracked_x, tracked_y
    keyboards, mice = find_devices()
    if not keyboards and not mice:
        raise SystemExit("Не найдены устройства ввода. Запусти через sudo.")

    print("=== Режим пипетки ===")
    print("  Shift + C - скопировать координаты в буфер обмена")
    print("  Ctrl + C  - выход (или F8)")

    do_cursor(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)

    all_devs = {d.fd: d for d in keyboards + mice}
    last_print = 0.0

    try:
        while True:
            ready, _, _ = select.select(list(all_devs), [], [], 0.1)
            for fd in ready:
                dev = all_devs.get(fd)
                if not dev:
                    continue
                try:
                    events = list(dev.read())
                except OSError:
                    all_devs.pop(fd, None)
                    continue

                for ev in events:
                    if ev.type == ecodes.EV_REL:
                        if ev.code == ecodes.REL_X:
                            tracked_x = max(0, min(SCREEN_WIDTH - 1, tracked_x + ev.value))
                        elif ev.code == ecodes.REL_Y:
                            tracked_y = max(0, min(SCREEN_HEIGHT - 1, tracked_y + ev.value))
                    elif ev.type == ecodes.EV_KEY and ev.value == 1:
                        if ev.code == ecodes.KEY_C:
                            if is_modifier_held(keyboards, CTRL_CODES):
                                print("\nВыход по Ctrl + C.")
                                return
                            elif is_modifier_held(keyboards, SHIFT_CODES):
                                handle_pipette_copy()
                        elif ev.code == EXIT_KEY:
                            print("\nВыход по F8.")
                            return

            now = time.monotonic()
            if now - last_print >= 0.1:
                x, y = get_cursor_pos()
                print(f"\rТекущие координаты: X={x:<4} Y={y:<4}   ", end="", flush=True)
                last_print = now
    except KeyboardInterrupt:
        print("\nВыход из пипетки.")


def main():
    global PREPARED, tracked_x, tracked_y

    if len(sys.argv) > 1 and sys.argv[1] == "--pipette":
        try:
            run_pipette()
        finally:
            kb_ui.close()
            mouse_ui.close()
            abs_ui.close()
        return

    try:
        PREPARED = prepare(SEQUENCE)
    except ValueError as e:
        raise SystemExit(f"Ошибка в SEQUENCE: {e}")

    keyboards, mice = find_devices()
    if not keyboards:
        raise SystemExit(
            "Не удалось открыть клавиатуры в /dev/input. "
            "Добавь пользователя в группу input или запусти через sudo."
        )

    print("Слушаю клавиатуры:", ", ".join(k.name for k in keyboards))
    print("Управление (работает даже в игре):")
    print("  F6        - старт / стоп макроса")
    print("  Shift + C - скопировать координаты курсора (пипетка)")
    print("  Ctrl + C  - выход из программы (или F8)")

    devices = {d.fd: d for d in keyboards + mice}

    try:
        while True:
            ready, _, _ = select.select(list(devices), [], [])
            for fd in ready:
                dev = devices.get(fd)
                if not dev:
                    continue
                try:
                    events = list(dev.read())
                except OSError:
                    devices.pop(fd, None)
                    continue

                for ev in events:
                    if ev.type == ecodes.EV_REL:
                        if ev.code == ecodes.REL_X:
                            tracked_x = max(0, min(SCREEN_WIDTH - 1, tracked_x + ev.value))
                        elif ev.code == ecodes.REL_Y:
                            tracked_y = max(0, min(SCREEN_HEIGHT - 1, tracked_y + ev.value))
                    elif ev.type == ecodes.EV_KEY and ev.value == 1:
                        if ev.code == START_STOP_KEY:
                            toggle()
                        elif ev.code == EXIT_KEY:
                            stop_event.set()
                            print("\nВыход (F8).")
                            return
                        elif ev.code == ecodes.KEY_C:
                            if is_modifier_held(keyboards, CTRL_CODES):
                                stop_event.set()
                                print("\nГлобальный выход (Ctrl + C).")
                                return
                            elif is_modifier_held(keyboards, SHIFT_CODES):
                                handle_pipette_copy()

            if not devices:
                raise SystemExit("Все устройства ввода отключены.")
    except KeyboardInterrupt:
        stop_event.set()
        print("\nВыход (Ctrl + C).")
    finally:
        time.sleep(0.1)
        kb_ui.close()
        mouse_ui.close()
        abs_ui.close()


if __name__ == "__main__":
    main()

