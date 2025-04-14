// —— 全局状态 ——
let pc, dc;
let baseline = { alpha: 0, beta: 0, gamma: 0 };
let calibrated = false;
const statusEl = document.getElementById("calibrate-status");

// 更新校准状态文字
function updateStatus() {
    statusEl.textContent = calibrated ? "已校准 ✅" : "尚未校准 ⏳";
}

// 双击触发校准
let lastTap = 0;
window.addEventListener("touchstart", (e) => {
    const now = Date.now();
    if (now - lastTap < 300) {
        e.preventDefault();
        calibrated = false;
        updateStatus();
        calibrate();
    }
    lastTap = now;
}, { passive: false });

// 校准函数：第一次拿到 deviceorientation 就记录基线
function calibrate() {
    const cb = (event) => {
        baseline.alpha = event.alpha;
        baseline.beta  = event.beta;
        baseline.gamma  = event.gamma;
        calibrated = true;
        updateStatus();
        window.removeEventListener("deviceorientation", cb);
        console.log("校准成功:", baseline);
    };
    window.addEventListener("deviceorientation", cb);
}

// 将设备方向数据通过 DataChannel 发送
function handleOrientation(event) {
    if (!calibrated || !dc || dc.readyState !== "open") return;
    const diffAlpha = event.alpha - baseline.alpha;
    const diffBeta  = event.beta  - baseline.beta;
    const diffGamma  = event.gamma  - baseline.gamma;
    dc.send(JSON.stringify({ alpha: diffAlpha, beta: diffBeta, gamma: diffGamma }));
}

// 请求 iOS 设备方向权限并启动 WebRTC
function requestPermissionIfNeeded() {
    if (typeof DeviceOrientationEvent.requestPermission === "function") {
        DeviceOrientationEvent.requestPermission()
            .then(res => {
                if (res === "granted") {
                    updateStatus();
                    startWebRTC();
                } else {
                    alert("未获取传感器权限");
                }
            })
            .catch(console.error);
    } else {
        updateStatus();
        startWebRTC();
    }
}

// 建立 RTCPeerConnection + DataChannel，并完成 Offer/Answer 信令
async function startWebRTC() {
    // 1. 新建 PeerConnection（带 STUN）
    pc = new RTCPeerConnection({
        iceServers: [{ urls: "stun:stun.l.google.com:19302" }]
    });

    // 2. 建立 DataChannel
    dc = pc.createDataChannel("control");
    dc.onopen    = () => console.log("DataChannel open");
    dc.onclose   = () => console.log("DataChannel closed");
    dc.onerror   = e => console.error("DC error:", e);
    dc.onmessage = e => console.log("DC msg:", e.data);

    // 3. 创建 Offer
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    // 4. 等待 ICE Gathering 完成
    await new Promise(resolve => {
        if (pc.iceGatheringState === "complete") {
            resolve();
        } else {
            function check() {
                if (pc.iceGatheringState === "complete") {
                    pc.removeEventListener("icegatheringstatechange", check);
                    resolve();
                }
            }
            pc.addEventListener("icegatheringstatechange", check);
        }
    });

    // 5. 发送 Offer，获取 Answer
    const resp = await fetch("/offer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            sdp:  pc.localDescription.sdp,
            type: pc.localDescription.type
        })
    });
    const answer = await resp.json();
    await pc.setRemoteDescription(answer);

    // 6. 绑定设备方向事件
    window.addEventListener("deviceorientation", handleOrientation);
}

// 页面加载后先申请权限
window.onload = requestPermissionIfNeeded;
