// client.js

// —— 全局状态 ——
let pc, dc;
let baseline = { alpha: 0, beta: 0 };
let calibrated = false;
let pairingCode = null;
let localId = null;
let remoteId = null;
const pollingTimeout = 5 * 60 * 1000; // 5 分钟

// —— DOM 元素 ——
const statusEl = document.getElementById("calibrate-status");
const connectionStatusEl = document.getElementById("connection-status");
const pairingInput = document.getElementById("pairing-code");
const setCodeBtn = document.getElementById("set-code");

// —— UI 更新 ——
function updateCalibrateStatus() {
    statusEl.textContent = calibrated ? "已校准 ✅" : "尚未校准 ⏳";
}
function updateConnectionStatus(state) {
    const map = {
        "new": "未连接，请打开受控端 ⏳",
        "connecting": "正在连接 🔄",
        "connected": "已连接 ✅",
        "disconnected": "已断开 ⚠️",
        "failed": "连接失败 ❌",
        "closed": "连接关闭 🚫",
        "timeout": "配对超时，请重启 ⚠️"
    };
    connectionStatusEl.textContent = `连接状态：${map[state]}`;
}

// —— 本地存储 ——
function savePairingCode(code) {
    localStorage.setItem("pairingCode", code);
}
function loadPairingCode() {
    return localStorage.getItem("pairingCode");
}

// —— 校准逻辑 ——
let lastTap = 0;
window.addEventListener("touchstart", (e) => {
    const now = Date.now();
    if (now - lastTap < 300) {
        e.preventDefault();
        calibrated = false;
        updateCalibrateStatus();
        calibrate();
    }
    lastTap = now;
}, { passive: false });

function calibrate() {
    const cb = (event) => {
        baseline.alpha = event.alpha;
        baseline.beta  = event.beta;
        calibrated = true;
        updateCalibrateStatus();
        window.removeEventListener("deviceorientation", cb);
    };
    window.addEventListener("deviceorientation", cb);
}

function handleOrientation(event) {
    if (!calibrated || !dc || dc.readyState !== "open") return;
    const diffAlpha = event.alpha - baseline.alpha;
    const diffBeta  = event.beta  - baseline.beta;
    dc.send(JSON.stringify({ alpha: diffAlpha, beta: diffBeta }));
}

// —— 信令通信 ——
async function sendSignal(msg) {
    await fetch('/default/signal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(msg)
    });
}
async function fetchSignals() {
    const resp = await fetch(`/default/signal?clientId=${localId}`);
    return resp.json();
}

// —— 应用配对码 & 启动 WebRTC ——
function applyPairingCode(code) {
    pairingCode = code;
    localId = `mobile-${code}`;
    remoteId = `pc-${code}`;
    savePairingCode(code);
    initWebRTC();
}

setCodeBtn.addEventListener("click", () => {
    const code = pairingInput.value.trim();
    if (!code) return alert("请输入有效配对码");
    applyPairingCode(code);
});

// —— WebRTC 连接逻辑 ——
async function initWebRTC() {
    updateCalibrateStatus();
    updateConnectionStatus("new");

    // 请求设备方向权限
    if (typeof DeviceOrientationEvent?.requestPermission === "function") {
        try {
            const res = await DeviceOrientationEvent.requestPermission();
            if (res !== "granted") {
                alert("未获取传感器权限");
                return;
            }
        } catch (e) {
            console.error(e);
        }
    }

    pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.miwifi.com' }] });
    dc = pc.createDataChannel('control');
    dc.onopen = () => console.log('DataChannel open');

    pc.addEventListener("connectionstatechange", () => {
        updateConnectionStatus(pc.connectionState);
    });

    // 发起 Offer
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    await new Promise(r => {
        if (pc.iceGatheringState === 'complete') r();
        else pc.addEventListener('icegatheringstatechange', () => {
            if (pc.iceGatheringState === 'complete') r();
        });
    });
    await sendSignal({ from: localId, to: remoteId, type: 'offer', sdp: pc.localDescription.sdp });
    updateConnectionStatus(pc.connectionState);

    // 等待 Answer 或 超时
    let answerMsg = null;
    const startTime = Date.now();
    while (!answerMsg) {
        if (Date.now() - startTime > pollingTimeout) {
            updateConnectionStatus("timeout");
            alert("配对超时，未检测到受控端，请重启");
            return;
        }
        const msgs = await fetchSignals();
        answerMsg = msgs.find(m => m.type === 'answer' && m.from === remoteId);
        if (!answerMsg) {
            await new Promise(r => setTimeout(r, 3000));
        }
    }
    await pc.setRemoteDescription(new RTCSessionDescription(answerMsg));
    updateConnectionStatus(pc.connectionState);
    window.addEventListener("deviceorientation", handleOrientation);
}

// —— 页面加载时：自动填充 & 应用配对码 ——
window.onload = () => {
    const saved = loadPairingCode();
    if (saved) {
        pairingInput.value = saved;
        applyPairingCode(saved);
    }
};
