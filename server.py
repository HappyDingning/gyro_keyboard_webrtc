import argparse
import asyncio
import json
import logging
import os
import queue
import ssl
import threading

import pyautogui
from aiohttp import web
from aiortc import (
    RTCConfiguration,
    RTCIceServer,
    RTCPeerConnection,
    RTCSessionDescription,
)

ROOT = os.path.dirname(__file__)

# ----- 按键队列与后台线程 -----
key_queue = queue.Queue()


def key_worker():
    while True:
        action, key = key_queue.get()
        try:
            if action == "down":
                pyautogui.keyDown(key)
            elif action == "up":
                pyautogui.keyUp(key)
        except Exception as e:
            print("按键处理出错:", e)
        finally:
            key_queue.task_done()


threading.Thread(target=key_worker, daemon=True).start()

# 阈值设置
ALPHA_THRESHOLD = 12  # 左右摇头
BETA_THRESHOLD = 12  # 前后点头

# 保存所有活跃的 PeerConnection，以便优雅关闭
pcs = set()


def process_axis(axis, value, pos_key, neg_key, threshold, pressed_keys):
    """
    根据 value 和阈值决定是按下、保持还是松开某个按键，
    pressed_keys 用于记住当前该轴已按下的键。
    """
    if value is None:
        return

    current = pressed_keys.get(axis)
    if value > threshold:
        # 正向
        if current != pos_key:
            if current:
                key_queue.put(("up", current))
            key_queue.put(("down", pos_key))
            pressed_keys[axis] = pos_key
    elif value < -threshold:
        # 负向
        if current != neg_key:
            if current:
                key_queue.put(("up", current))
            key_queue.put(("down", neg_key))
            pressed_keys[axis] = neg_key
    else:
        # 中间区，松开
        if current:
            key_queue.put(("up", current))
            pressed_keys[axis] = None


# ----- HTTP 静态文件服务 -----
async def index(request):
    return web.FileResponse(os.path.join(ROOT, "index.html"))


async def javascript(request):
    return web.FileResponse(os.path.join(ROOT, "client.js"))


# ----- WebRTC 信令：处理 Offer -----
async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    # 配置 STUN（也可以在前端通过参数控制）
    config = RTCConfiguration(
        iceServers=[RTCIceServer(urls=["stun:stun.l.google.com:19302"])]
    )
    pc = RTCPeerConnection(configuration=config)
    pcs.add(pc)

    # 每个连接维护自己的一份 pressed_keys 状态
    pressed_keys = {"alpha": None, "beta": None}

    @pc.on("datachannel")
    def on_datachannel(channel):
        # 浏览器端 createDataChannel("control") 时会触发这里
        @channel.on("message")
        def on_message(message):
            # message 是 JSON 字符串，包含 alpha、beta
            try:
                data = json.loads(message)
                process_axis(
                    "alpha", data.get("alpha"), "a", "d", ALPHA_THRESHOLD, pressed_keys
                )
                process_axis(
                    "beta", data.get("beta"), "w", "s", BETA_THRESHOLD, pressed_keys
                )
            except Exception as e:
                print("处理数据出错:", e)

    # 完成 SDP 交换
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.json_response(
        {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
    )


# 优雅关闭所有 PeerConnection
async def on_shutdown(app):
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()


# ----- 程序入口 -----
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebRTC 控制示例")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8080, help="监听端口")
    parser.add_argument("--cert-file", help="SSL 证书（HTTPS）")
    parser.add_argument("--key-file", help="SSL 私钥（HTTPS）")
    parser.add_argument("-v", "--verbose", action="store_true", help="调试日志")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    if args.cert_file:
        ssl_ctx = ssl.SSLContext()
        ssl_ctx.load_cert_chain(args.cert_file, args.key_file)
    else:
        ssl_ctx = None

    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/client.js", javascript)
    app.router.add_post("/offer", offer)
    app.on_shutdown.append(on_shutdown)

    web.run_app(app, host=args.host, port=args.port, ssl_context=ssl_ctx)
