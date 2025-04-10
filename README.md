# WebRTC 设备方向控制示例

一个使用 WebRTC DataChannel 将手机陀螺仪（设备方向）数据发送到 PC，并通过 Python 程序模拟键盘按键的 Demo。左右摇头控制 A/D，前后点头控制 W/S。

---

## 功能

- **实时传输**：通过 WebRTC DataChannel 传输 `alpha`（左右）和 `beta`（前后）角度差值  
- **按键模拟**：Python 端接收数据后调用 [PyAutoGUI](https://pyautogui.readthedocs.io/) 模拟键盘事件  

---

## 前提条件

- **Python 3.7+**  
- **pip**  
- **虚拟环境**（`venv` 或 `virtualenv`，强烈推荐）  
- **手机端浏览器**：请使用 **Firefox**（Android/iOS），因为 Firefox 允许在 HTTP 页面中访问陀螺仪数据；其他浏览器可能需要 HTTPS  

---

## 快速开始

### 1. 克隆或下载项目

```bash
git clone git@github.com:HappyDingning/gyro_keyboard_webrtc.git
cd gyro_keyboard_webrtc
```

### 2. 创建并激活虚拟环境

```bash
python3 -m venv venv
# macOS/Linux
source venv/bin/activate
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1
```

### 3. 安装依赖

项目根目录运行：

```bash
pip install -r requirements.txt
```

或者直接：

```bash
pip install aiohttp aiortc pyautogui
```

---

## 运行服务器

```bash
python server.py --host 0.0.0.0 --port 8080
```

- `--host`：监听地址，默认为 `0.0.0.0`  
- `--port`：监听端口，默认为 `8080`  
- `--cert-file`、`--key-file`：启用 HTTPS（可选）  
- `-v` / `--verbose`：打开调试日志  

> **防火墙提示**  
> - **Windows**：在“Windows 防火墙”中允许端口 `8080`  
> - **Linux (ufw)**：`sudo ufw allow 8080`  

---

## 客户端使用

1. **网络**：确保 PC 与手机在同一 Wi‑Fi 或手机热点下。  
2. **查看本机 IP**：  
   - Windows：`ipconfig`  
   - macOS/Linux：`ifconfig` 或 `ip addr show`  
3. **打开页面**：在手机 Firefox 中访问  
   ```
   http://<PC_IP>:8080
   ```  
4. **校准**：  
   - 将手机水平放置于头顶  
   - 双击屏幕任意位置，状态由 “尚未校准 ⏳” 变为 “已校准 ✅”  
   - 校准成功后会记录基线角度  
5. **使用**：  
   - **左右摇头**：按下并保持 “A”/“D”  
   - **前后点头**：按下并保持 “W”/“S”  
   - **保持屏幕常亮**，否则设备方向事件会中断  
   - 可随时双击重新校准  

---

## 配置与自定义

- **阈值**（`server.py` 中）：  
  ```python
  ALPHA_THRESHOLD = 12  # 左右摇头阈值
  BETA_THRESHOLD  = 12  # 前后点头阈值
  ```
- **按键映射**：在 `process_axis` 函数中修改 `pos_key` / `neg_key`  

---

## 常见问题

- **无法获取方向数据？**  
  在 Firefox 中允许“传感器”权限，或者刷新页面重试。  
- **按键无响应？**  
  确保 PyAutoGUI 安装正确，并且操作系统允许模拟按键（macOS 需在“系统偏好设置 → 安全性与隐私”中授权）。  
- **使用 Chrome/Safari？**  
  这些浏览器在 HTTP 页面上通常禁止陀螺仪访问，建议使用 Firefox 或启用 HTTPS。  

---

## 项目结构

```
.
├── server.py       # 后端主程序
├── index.html      # 前端页面
├── client.js       # 前端脚本
└── requirements.txt
```

---

## 许可证

MIT License
