#!/usr/bin/env python3
"""
rtc_gui.py: GUI for RTC gyro control using webui2, with status updates via a dedicated thread and queue.
"""

import asyncio
import json
import logging
import os
import queue
import threading
import time

import aiohttp
from aiortc import (
    RTCConfiguration,
    RTCIceServer,
    RTCPeerConnection,
    RTCSessionDescription,
)
from pynput.keyboard import Controller
from webui import webui

# ----- Configuration -----
CONFIG_FILE = "config.json"
API_URL = "https://9uecr1n4yd.execute-api.us-east-1.amazonaws.com/default/signal"
TIMEOUT_INTERVAL = 300  # 5 minutes

# Default thresholds and client ID
ALPHA_THRESHOLD = 12
BETA_THRESHOLD = 12
CLIENT_ID = ""

# ----- Queues for inter-thread communication -----
key_queue = queue.Queue()
status_queue = queue.Queue()


# ----- Key worker thread -----
def key_worker():
    keyboard = Controller()
    while True:
        action, key = key_queue.get()
        try:
            if action == "down":
                keyboard.press(key)
            elif action == "up":
                keyboard.release(key)
        except Exception as e:
            print("Key handling error:", e)
        finally:
            key_queue.task_done()


threading.Thread(target=key_worker, daemon=True).start()
pressed_keys = {"alpha": None, "beta": None}


# ----- Status updater thread -----
def status_updater(window):
    """
    Dedicated thread: reads status messages from status_queue and updates the UI.
    """
    status_to_display = {
        "new": "正在初始化连接",
        "searching": "正在搜索手机端...",
        "timeout": "搜索手机端超时",
        "connecting": "正在连接...",
        "connected": "连接成功",
        "disconnected": "连接断开",
        "failed": "连接失败",
        "closed": "连接关闭",
    }
    while True:
        msg = status_to_display[status_queue.get()]
        # Update the status element in the UI
        window.script(f"document.getElementById('status').innerText = '{msg}';")
        status_queue.task_done()


# ----- Axis processing -----
def process_axis(axis, value, pos_key, neg_key, threshold):
    if value is None:
        return
    current = pressed_keys.get(axis)
    if value > threshold:
        key = pos_key
    elif value < -threshold:
        key = neg_key
    else:
        key = None
    if key != current:
        if current:
            key_queue.put(("up", current))
        if key:
            key_queue.put(("down", key))
        pressed_keys[axis] = key


# ----- Connection manager thread -----
reconnect_event = threading.Event()


def connection_manager(window):
    """
    Background thread: waits for reconnect_event, then runs connect().
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    while True:
        reconnect_event.wait()
        reconnect_event.clear()
        try:
            loop.run_until_complete(connect())
            continue
        except Exception as e:
            print("Connection error:", e)


# ----- RTC connection logic -----
async def connect():
    """
    Establishes RTC connection, handles datachannel messages.
    Returns 'timeout' if no peer found within 5 minutes.
    """
    # Create peer connection
    config = RTCConfiguration([RTCIceServer(urls=["stun:stun.l.google.com:19302"])])
    pc = RTCPeerConnection(configuration=config)

    async with aiohttp.ClientSession() as session:

        async def send_signal(msg):
            await session.post(API_URL, json=msg)

        async def fetch_signals():
            async with session.get(API_URL, params={"clientId": CLIENT_ID}) as resp:
                return await resp.json()

        # Handle incoming data channel
        @pc.on("datachannel")
        def on_datachannel(channel):
            @channel.on("message")
            def on_message(message):
                data = json.loads(message)
                process_axis("alpha", data.get("alpha"), "a", "d", ALPHA_THRESHOLD)
                process_axis("beta", data.get("beta"), "w", "s", BETA_THRESHOLD)

        # Track connection state changes
        done = asyncio.Event()

        @pc.on("connectionstatechange")
        def on_conn_state():
            state = pc.connectionState
            status_queue.put(state)
            if state in ("closed", "failed", "disconnected"):
                done.set()

        # Poll for offer with 5-minute timeout
        start_time = time.time()
        offer_msg = None
        # Notify UI that we're searching for peer
        status_queue.put("searching")
        while not offer_msg:
            msgs = await fetch_signals()
            offer_msg = next((m for m in msgs if m.get("type") == "offer"), None)
            if offer_msg:
                break

            if time.time() - start_time >= TIMEOUT_INTERVAL:
                await pc.close()
                status_queue.put("timeout")

                return

            await asyncio.sleep(3)

        # Establish connection
        offer = RTCSessionDescription(sdp=offer_msg["sdp"], type="offer")
        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        # Send answer back
        await send_signal(
            {
                "from": CLIENT_ID,
                "to": offer_msg.get("from"),
                "type": "answer",
                "sdp": pc.localDescription.sdp,
            }
        )

        # Wait until connection ends
        await done.wait()
        await pc.close()


# ----- Configuration handling -----
def load_config():
    global ALPHA_THRESHOLD, BETA_THRESHOLD, CLIENT_ID

    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)

        ALPHA_THRESHOLD = cfg.get("alpha_threshold", ALPHA_THRESHOLD)
        BETA_THRESHOLD = cfg.get("beta_threshold", BETA_THRESHOLD)
        CLIENT_ID = normalize_client_id(cfg.get("pairing_code", ""))


def save_settings(e: webui.Event):
    global ALPHA_THRESHOLD, BETA_THRESHOLD, CLIENT_ID

    res_a = e.window.script("return document.getElementById('alpha_threshold').value;")
    res_b = e.window.script("return document.getElementById('beta_threshold').value;")
    res_c = e.window.script("return document.getElementById('pairing_code').value;")

    if res_a.error or res_b.error or res_c.error:
        return
    try:
        a = int(res_a.data)
    except ValueError:
        a = ALPHA_THRESHOLD

    try:
        b = int(res_b.data)
    except ValueError:
        b = BETA_THRESHOLD
    client_id = normalize_client_id(res_c.data)

    ALPHA_THRESHOLD = a
    BETA_THRESHOLD = b
    CLIENT_ID = client_id

    with open(CONFIG_FILE, "w") as f:
        json.dump(
            {"alpha_threshold": a, "beta_threshold": b, "pairing_code": res_c.data}, f
        )
    e.window.script("alert('Settings saved');")
    # Trigger reconnect
    reconnect_event.set()


def reconnect(e: webui.Event):
    reconnect_event.set()


# ----- Utility -----
def normalize_client_id(raw_id: str) -> str:
    return f"pc-{raw_id}"


# ----- Main entry point -----
def main():
    logging.basicConfig(level=logging.INFO)

    # Load saved configuration
    load_config()

    # Prepare HTML UI
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset=\"utf-8\" />
        <script src=\"webui.js\"></script>
        <title>头控精灵</title>
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; background: #f0f0f0; }}
            input {{ padding: 5px; margin: 5px; }}
            button {{ padding: 10px 20px; margin: 10px; }}
            #status {{ font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>头控精灵</h1>
        <div>
            <label>摇头阈值（角度）: <input type=\"number\" id=\"alpha_threshold\" value=\"{ALPHA_THRESHOLD}\"></label>
        </div>
        <div>
            <label>点头阈值（角度）: <input type=\"number\" id=\"beta_threshold\" value=\"{BETA_THRESHOLD}\"></label>
        </div>
        <div>
            <label>配对码: <input type=\"text\" id=\"pairing_code\" value=\"{CLIENT_ID[3:]}\"></label>
        </div>
        <button id=\"SaveSettings\">保存设置</button>
        <button id=\"Reconnect\">重新连接</button>
        <h2>状态: <span id=\"status\">{"等待设置配对码" if not CLIENT_ID else ""}</span></h2>
    </body>
    </html>
    """

    # Create window and bind events
    win = webui.Window()
    win.bind("SaveSettings", save_settings)
    win.bind("Reconnect", reconnect)
    win.show(html)

    # Start the status updater thread
    threading.Thread(target=status_updater, args=(win,), daemon=True).start()

    # Start the connection manager thread
    threading.Thread(target=connection_manager, args=(win,), daemon=True).start()

    # If we have a client ID, trigger initial connection
    if CLIENT_ID:
        reconnect_event.set()

    webui.wait()


if __name__ == "__main__":
    main()
