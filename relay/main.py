import os
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse


app = FastAPI()

ROOM_TOKEN = os.environ.get(
    "ROOM_TOKEN",
    "CHANGE_THIS_TOKEN"
)

devices = {}


@app.get("/")
async def root():

    return JSONResponse({
        "status": "online",
        "service": "remote-desktop-relay",
        "devices": len(devices)
    })


@app.get("/devices")
async def get_devices():

    result = []

    for device_id, device in devices.items():

        result.append({
            "id": device_id,
            "name": device["name"],
            "online": device["websocket"] is not None
        })

    result.sort(
        key=lambda x: int(
            x["name"].replace("home", "")
        )
    )

    return result


@app.websocket("/ws/home")
async def home_websocket(websocket: WebSocket):

    token = websocket.query_params.get("token")

    if token != ROOM_TOKEN:

        await websocket.close(code=1008)
        return

    await websocket.accept()

    device_id = None

    try:

        registration = await websocket.receive_text()

        data = json.loads(registration)

        if data.get("type") != "register":

            await websocket.close(code=1008)
            return

        device_id = data.get("device_id")

        if not device_id:

            await websocket.close(code=1008)
            return

        if device_id not in devices:

            used_numbers = []

            for device in devices.values():

                try:

                    number = int(
                        device["name"].replace(
                            "home",
                            ""
                        )
                    )

                    used_numbers.append(number)

                except Exception:
                    pass

            number = 1

            while number in used_numbers:
                number += 1

            devices[device_id] = {
                "name": f"home{number}",
                "websocket": websocket,
                "viewer": None
            }

        else:

            old_viewer = devices[device_id].get(
                "viewer"
            )

            devices[device_id]["websocket"] = websocket

            if old_viewer:

                try:

                    await old_viewer.send_text(
                        json.dumps({
                            "type": "reconnected"
                        })
                    )

                except Exception:
                    pass

        await websocket.send_text(
            json.dumps({
                "type": "registered",
                "device_id": device_id,
                "name": devices[device_id]["name"]
            })
        )

        while True:

            message = await websocket.receive()

            viewer = devices[device_id].get(
                "viewer"
            )

            if "text" in message:

                if viewer:

                    try:

                        await viewer.send_text(
                            message["text"]
                        )

                    except Exception:

                        pass

            elif "bytes" in message:

                if viewer:

                    try:

                        await viewer.send_bytes(
                            message["bytes"]
                        )

                    except Exception:

                        pass

    except WebSocketDisconnect:
        pass

    except Exception:
        pass

    finally:

        if device_id in devices:

            if devices[device_id]["websocket"] is websocket:

                devices[device_id]["websocket"] = None


@app.websocket("/ws/viewer/{device_id}")
async def viewer_websocket(
    websocket: WebSocket,
    device_id: str
):

    token = websocket.query_params.get("token")

    if token != ROOM_TOKEN:

        await websocket.close(code=1008)
        return

    await websocket.accept()

    device = devices.get(device_id)

    if not device:

        await websocket.send_text(
            json.dumps({
                "type": "error",
                "message": "Device not found"
            })
        )

        await websocket.close()

        return

    home_ws = device.get("websocket")

    if not home_ws:

        await websocket.send_text(
            json.dumps({
                "type": "error",
                "message": "Device offline"
            })
        )

        await websocket.close()

        return

    old_viewer = device.get("viewer")

    if old_viewer:

        try:

            await old_viewer.close()

        except Exception:
            pass

    device["viewer"] = websocket

    try:

        await websocket.send_text(
            json.dumps({
                "type": "connected",
                "device_id": device_id,
                "name": device["name"]
            })
        )

        while True:

            message = await websocket.receive()

            if "text" in message:

                try:

                    await home_ws.send_text(
                        message["text"]
                    )

                except Exception:

                    break

            elif "bytes" in message:

                try:

                    await home_ws.send_bytes(
                        message["bytes"]
                    )

                except Exception:

                    break

    except WebSocketDisconnect:
        pass

    except Exception:
        pass

    finally:

        if device_id in devices:

            if devices[device_id].get(
                "viewer"
            ) is websocket:

                devices[device_id]["viewer"] = None