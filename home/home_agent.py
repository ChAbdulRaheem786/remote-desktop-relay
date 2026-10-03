import asyncio
import io
import json
import os
import sys
import uuid
from pathlib import Path

import mss
from PIL import Image
import pyautogui
import websockets


RELAY = "wss://remote-desktop-relay-5gte.onrender.com"
TOKEN = "webcrwaler@302"

running = True
device_id = None
device_name = None


def get_device_id():
    app_dir = Path(os.environ["APPDATA"]) / "HomeRemote"
    app_dir.mkdir(parents=True, exist_ok=True)

    id_file = app_dir / "device_id.txt"

    if id_file.exists():
        value = id_file.read_text().strip()

        if value:
            return value

    value = str(uuid.uuid4())

    id_file.write_text(value)

    return value


def setup_startup():
    try:
        startup_dir = (
            Path(os.environ["APPDATA"])
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
            / "Startup"
        )

        startup_dir.mkdir(parents=True, exist_ok=True)

        exe_path = Path(sys.executable)

        shortcut_path = startup_dir / "HomeRemote.lnk"

        if shortcut_path.exists():
            return

        import win32com.client

        shell = win32com.client.Dispatch("WScript.Shell")

        shortcut = shell.CreateShortcut(
            str(shortcut_path)
        )

        shortcut.TargetPath = str(exe_path)
        shortcut.WorkingDirectory = str(exe_path.parent)
        shortcut.Description = "Home Remote Desktop"

        shortcut.Save()

    except Exception:
        pass


def normalize_key(key):

    mapping = {
        "Control_L": "ctrl",
        "Control_R": "ctrl",
        "Shift_L": "shift",
        "Shift_R": "shift",
        "Alt_L": "alt",
        "Alt_R": "alt",
        "Win_L": "win",
        "Win_R": "win",
        "Return": "enter",
        "Escape": "esc",
        "BackSpace": "backspace",
        "Tab": "tab",
        "space": "space",
        "Delete": "delete",
        "Insert": "insert",
        "Home": "home",
        "End": "end",
        "Prior": "pageup",
        "Next": "pagedown",
        "Up": "up",
        "Down": "down",
        "Left": "left",
        "Right": "right"
    }

    if key in mapping:
        return mapping[key]

    if key.startswith("F") and key[1:].isdigit():
        return key.lower()

    if len(key) == 1:
        return key.lower()

    return key.lower()


def handle_command(data):

    try:

        msg = json.loads(data)

        command = msg.get("type")

        if command == "mouse_move":

            pyautogui.moveTo(
                int(msg["x"]),
                int(msg["y"]),
                duration=0
            )

        elif command == "mouse_down":

            pyautogui.mouseDown(
                button=msg.get("button", "left")
            )

        elif command == "mouse_up":

            pyautogui.mouseUp(
                button=msg.get("button", "left")
            )

        elif command == "click":

            pyautogui.click(
                button=msg.get("button", "left")
            )

        elif command == "double_click":

            pyautogui.doubleClick(
                button=msg.get("button", "left")
            )

        elif command == "scroll":

            pyautogui.scroll(
                int(msg["amount"])
            )

        elif command == "key_down":

            pyautogui.keyDown(
                normalize_key(msg["key"])
            )

        elif command == "key_up":

            pyautogui.keyUp(
                normalize_key(msg["key"])
            )

    except Exception:
        pass


async def send_screen(ws):

    with mss.mss() as sct:

        while running:

            try:

                monitor = sct.monitors[1]

                screenshot = sct.grab(monitor)

                image = Image.frombytes(
                    "RGB",
                    screenshot.size,
                    screenshot.rgb
                )

                max_width = 1280

                if image.width > max_width:

                    height = int(
                        image.height *
                        max_width /
                        image.width
                    )

                    image = image.resize(
                        (max_width, height)
                    )

                buffer = io.BytesIO()

                image.save(
                    buffer,
                    format="JPEG",
                    quality=55,
                    optimize=True
                )

                await ws.send(
                    buffer.getvalue()
                )

                await asyncio.sleep(0.08)

            except Exception:

                break


async def receive_commands(ws):

    while running:

        try:

            message = await ws.recv()

            if isinstance(message, str):

                try:

                    data = json.loads(message)

                    if data.get("type") == "registered":

                        global device_name

                        device_name = data.get("name")

                        print(
                            "Registered as:",
                            device_name
                        )

                    else:

                        handle_command(message)

                except Exception:
                    pass

        except Exception:

            break


async def connect_loop():

    global device_id

    device_id = get_device_id()

    url = (
        f"{RELAY}/ws/home"
        f"?token={TOKEN}"
    )

    while running:

        try:

            print("Connecting to:", RELAY)

            async with websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=20,
                max_size=None
            ) as ws:

                print("Connected")

                await ws.send(
                    json.dumps({
                        "type": "register",
                        "device_id": device_id
                    })
                )

                print("Registration sent")

                await asyncio.gather(
                    send_screen(ws),
                    receive_commands(ws)
                )

        except Exception as e:

            print("Connection error:", repr(e))

        if running:

            await asyncio.sleep(5)


if __name__ == "__main__":

    setup_startup()

    asyncio.run(connect_loop())