import asyncio
import io
import json
import threading
import tkinter as tk

import requests
import websockets

from PIL import Image, ImageTk


RELAY_HTTP = "https://remote-desktop-relay-5gte.onrender.com"
RELAY_WS = "wss://remote-desktop-relay-5gte.onrender.com"

TOKEN = "YOUR_NEW_RANDOM_TOKEN"


class RemoteViewer:

    def __init__(self, root):

        self.root = root

        self.root.title("My Remote Computers")
        self.root.geometry("1400x850")

        self.ws = None
        self.loop = None

        self.image = None
        self.tk_image = None

        self.image_width = 1
        self.image_height = 1

        self.devices = []

        self.selected_device = None

        self.sidebar = tk.Frame(
            root,
            width=230
        )

        self.sidebar.pack(
            side="left",
            fill="y"
        )

        self.title = tk.Label(
            self.sidebar,
            text="My Remote Computers",
            font=("Arial", 16, "bold")
        )

        self.title.pack(
            pady=15
        )

        self.device_frame = tk.Frame(
            self.sidebar
        )

        self.device_frame.pack(
            fill="both",
            expand=True
        )

        self.refresh_button = tk.Button(
            self.sidebar,
            text="Refresh Devices",
            command=self.load_devices
        )

        self.refresh_button.pack(
            pady=10
        )

        self.status = tk.Label(
            self.sidebar,
            text="Disconnected",
            anchor="w"
        )

        self.status.pack(
            fill="x",
            padx=10,
            pady=10
        )

        self.canvas = tk.Canvas(
            root,
            bg="black"
        )

        self.canvas.pack(
            side="right",
            fill="both",
            expand=True
        )

        self.canvas.bind(
            "<Motion>",
            self.mouse_move
        )

        self.canvas.bind(
            "<Button-1>",
            self.left_click
        )

        self.canvas.bind(
            "<Button-3>",
            self.right_click
        )

        self.canvas.bind(
            "<Double-Button-1>",
            self.double_click
        )

        self.canvas.bind(
            "<MouseWheel>",
            self.scroll
        )

        self.canvas.bind(
            "<KeyPress>",
            self.key_down
        )

        self.canvas.bind(
            "<KeyRelease>",
            self.key_up
        )

        self.canvas.bind(
            "<Button-1>",
            self.focus_canvas,
            add="+"
        )

        threading.Thread(
            target=self.network_thread,
            daemon=True
        ).start()

        self.root.after(
            30,
            self.refresh
        )

        self.root.after(
            1000,
            self.load_devices
        )

    def focus_canvas(self, event):

        self.canvas.focus_set()

    def update_status(self, text):

        self.root.after(
            0,
            lambda: self.status.config(
                text=text
            )
        )

    def network_thread(self):

        self.loop = asyncio.new_event_loop()

        asyncio.set_event_loop(
            self.loop
        )

        self.loop.run_forever()

    def run_async(self, coroutine):

        if self.loop:

            asyncio.run_coroutine_threadsafe(
                coroutine,
                self.loop
            )

    def load_devices(self):

        threading.Thread(
            target=self.fetch_devices,
            daemon=True
        ).start()

    def fetch_devices(self):

        try:

            response = requests.get(
                f"{RELAY_HTTP}/devices",
                timeout=10
            )

            devices = response.json()

            self.devices = devices

            self.root.after(
                0,
                self.update_device_list
            )

        except Exception as e:

            self.update_status(
                "Device list unavailable"
            )

    def update_device_list(self):

        for widget in self.device_frame.winfo_children():

            widget.destroy()

        for device in self.devices:

            name = device["name"]

            online = device["online"]

            if online:

                text = f"●  {name}"

            else:

                text = f"○  {name}"

            button = tk.Button(
                self.device_frame,
                text=text,
                anchor="w",
                width=22,
                command=lambda d=device: self.select_device(d)
            )

            button.pack(
                fill="x",
                padx=8,
                pady=4
            )

    def select_device(self, device):

        if not device["online"]:

            self.update_status(
                f"{device['name']} is offline"
            )

            return

        self.selected_device = device

        self.image = None

        self.update_status(
            f"Connecting to {device['name']}..."
        )

        if self.ws:

            self.run_async(
                self.close_connection()
            )

        self.run_async(
            self.connect_device(
                device["id"]
            )
        )

    async def close_connection(self):

        try:

            if self.ws:

                await self.ws.close()

        except Exception:
            pass

        self.ws = None

    async def connect_device(self, device_id):

        url = (
            f"{RELAY_WS}"
            f"/ws/viewer/{device_id}"
            f"?token={TOKEN}"
        )

        try:

            async with websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=20,
                max_size=None
            ) as ws:

                self.ws = ws

                self.update_status(
                    f"Connected to {self.selected_device['name']}"
                )

                while True:

                    data = await ws.recv()

                    if isinstance(data, bytes):

                        image = Image.open(
                            io.BytesIO(data)
                        ).convert("RGB")

                        self.image = image

                        self.image_width = image.width
                        self.image_height = image.height

        except Exception:

            self.ws = None

            self.update_status(
                "Disconnected"
            )

    def send(self, data):

        if not self.ws or not self.loop:

            return

        asyncio.run_coroutine_threadsafe(
            self.ws.send(
                json.dumps(data)
            ),
            self.loop
        )

    def screen_coordinates(self, event):

        if not self.image:

            return None

        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        image_width = self.image_width
        image_height = self.image_height

        image_ratio = (
            image_width /
            image_height
        )

        canvas_ratio = (
            canvas_width /
            canvas_height
        )

        if image_ratio > canvas_ratio:

            display_width = canvas_width

            display_height = int(
                canvas_width /
                image_ratio
            )

        else:

            display_height = canvas_height

            display_width = int(
                canvas_height *
                image_ratio
            )

        offset_x = (
            canvas_width -
            display_width
        ) / 2

        offset_y = (
            canvas_height -
            display_height
        ) / 2

        x = event.x - offset_x
        y = event.y - offset_y

        if x < 0 or y < 0:

            return None

        if (
            x > display_width or
            y > display_height
        ):

            return None

        remote_x = round(
            x *
            image_width /
            display_width
        )

        remote_y = round(
            y *
            image_height /
            display_height
        )

        remote_x = max(
            0,
            min(
                remote_x,
                image_width - 1
            )
        )

        remote_y = max(
            0,
            min(
                remote_y,
                image_height - 1
            )
        )

        return remote_x, remote_y

    def mouse_move(self, event):

        coords = self.screen_coordinates(
            event
        )

        if coords:

            self.send({
                "type": "mouse_move",
                "x": coords[0],
                "y": coords[1]
            })

    def left_click(self, event):

        coords = self.screen_coordinates(
            event
        )

        if coords:

            self.send({
                "type": "mouse_move",
                "x": coords[0],
                "y": coords[1]
            })

            self.send({
                "type": "click",
                "button": "left"
            })

    def right_click(self, event):

        coords = self.screen_coordinates(
            event
        )

        if coords:

            self.send({
                "type": "mouse_move",
                "x": coords[0],
                "y": coords[1]
            })

            self.send({
                "type": "click",
                "button": "right"
            })

    def double_click(self, event):

        coords = self.screen_coordinates(
            event
        )

        if coords:

            self.send({
                "type": "mouse_move",
                "x": coords[0],
                "y": coords[1]
            })

            self.send({
                "type": "double_click",
                "button": "left"
            })

    def scroll(self, event):

        amount = (
            1
            if event.delta > 0
            else -1
        )

        self.send({
            "type": "scroll",
            "amount": amount
        })

    def key_down(self, event):

        self.send({
            "type": "key_down",
            "key": event.keysym
        })

    def key_up(self, event):

        self.send({
            "type": "key_up",
            "key": event.keysym
        })

    def refresh(self):

        if self.image:

            canvas_width = (
                self.canvas.winfo_width()
            )

            canvas_height = (
                self.canvas.winfo_height()
            )

            if (
                canvas_width > 1 and
                canvas_height > 1
            ):

                image = self.image.copy()

                image.thumbnail(
                    (
                        canvas_width,
                        canvas_height
                    )
                )

                self.tk_image = ImageTk.PhotoImage(
                    image
                )

                self.canvas.delete(
                    "all"
                )

                self.canvas.create_image(
                    canvas_width // 2,
                    canvas_height // 2,
                    image=self.tk_image,
                    anchor="center"
                )

        self.root.after(
            30,
            self.refresh
        )


root = tk.Tk()

app = RemoteViewer(root)

root.mainloop()