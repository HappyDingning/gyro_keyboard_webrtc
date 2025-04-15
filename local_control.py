import asyncio
import json
import logging
import os
import queue
import sys
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

# ----- 配置文件 & 超时 -----
CONFIG_FILE = "pairing_code.txt"
API_URL = os.environ.get(
    "SIGNAL_API",
    "https://9uecr1n4yd.execute-api.us-east-1.amazonaws.com/default/signal",
)
POLL_INTERVAL = 3  # 秒
TIMEOUT = 5 * 60  # 秒


# ----- 获取并保存配对码 -----
def get_pairing_code():
    if os.path.exists(CONFIG_FILE):
        return open(CONFIG_FILE).read().strip()
    code = input("请输入配对码: ").strip()
    if not code:
        print("配对码不能为空，退出")
        sys.exit(1)
    with open(CONFIG_FILE, "w") as f:
        f.write(code)
    return code


pairing_code = get_pairing_code()
CLIENT_ID = f"pc-{pairing_code}"
REMOTE_ID = f"mobile-{pairing_code}"

# ----- 按键队列与后台线程 -----
key_queue = queue.Queue()


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
            print("按键处理出错:", e)
        finally:
            key_queue.task_done()


threading.Thread(target=key_worker, daemon=True).start()

pressed_keys = {"alpha": None, "beta": None}


# ----- 按键处理 -----
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


# ----- 主逻辑 -----
async def run():
    print(f"本端 ID: {CLIENT_ID}，目标 ID: {REMOTE_ID}")
    start_time = time.time()
    async with aiohttp.ClientSession() as session:

        async def send_signal(msg):
            await session.post(API_URL, json=msg)

        async def fetch_signals():
            async with session.get(API_URL, params={"clientId": CLIENT_ID}) as resp:
                return await resp.json()

        # 1. 创建 PeerConnection
        config = RTCConfiguration([RTCIceServer(urls=["stun:stun.l.google.com:19302"])])
        pc = RTCPeerConnection(configuration=config)

        @pc.on("datachannel")
        def on_datachannel(channel):
            @channel.on("message")
            def on_message(message):
                data = json.loads(message)
                process_axis("alpha", data.get("alpha"), "a", "d", 12)
                process_axis("beta", data.get("beta"), "w", "s", 12)

        # 2. 轮询等待 Offer 或 超时
        print("正在轮询等待 Offer…")
        offer_msg = None
        while not offer_msg:
            if time.time() - start_time > TIMEOUT:
                print("配对超时，未检测到手机端，请重启")
                return
            msgs = await fetch_signals()
            offer_msg = next(
                (m for m in msgs if m["type"] == "offer" and m["from"] == REMOTE_ID),
                None,
            )
            if not offer_msg:
                await asyncio.sleep(POLL_INTERVAL)

        print("Offer 已收到，正在处理…")
        offer = RTCSessionDescription(sdp=offer_msg["sdp"], type="offer")
        await pc.setRemoteDescription(offer)

        # 3. 生成并发送 Answer
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        await send_signal(
            {
                "from": CLIENT_ID,
                "to": REMOTE_ID,
                "type": "answer",
                "sdp": pc.localDescription.sdp,
            }
        )
        print("Answer 已发送，等待连接…")

        # 4. 等待连接关闭或失败
        done = asyncio.Event()

        @pc.on("connectionstatechange")
        def on_conn_state():
            print("连接状态:", pc.connectionState)
            if pc.connectionState in ("closed", "failed", "disconnected"):
                done.set()

        await done.wait()
        print("PeerConnection 已关闭，脚本退出")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
