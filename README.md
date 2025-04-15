# WebRTC 设备方向控制示例

一个使用 WebRTC DataChannel 将手机陀螺仪（设备方向）数据发送到 PC，并通过 Python 程序模拟键盘按键的 Demo。左右摇头控制 A/D，前后点头控制 W/S。

---

## 功能

- **实时传输**：通过 WebRTC DataChannel 传输 `alpha`（左右）和 `beta`（前后）角度差值  
- **按键模拟**：Python 端接收数据后调用 [pynput](https://github.com/moses-palmer/pynput) 模拟键盘事件  

---

## 前提条件

- **Python 3.7+**  
- **虚拟环境**（`venv` 或 `virtualenv`，强烈推荐）  
- **关闭电脑防火墙**：请关闭电脑防火墙，以免手机和电脑连接失败

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
pip install aiohttp aiortc pynput
```

---

## 运行电脑端

```bash
python local_control.py
```

---

## 手机端使用

1. **网络**：确保 PC 与手机在同一 Wi‑Fi 或手机热点下，并关闭电脑的防火墙。
2. **手机打开页面**：
   ```
   https://9uecr1n4yd.execute-api.us-east-1.amazonaws.com/default/index.html
   ```  
3. **校准**：  
   - 将手机水平放置于头顶  
   - 双击屏幕任意位置，状态由 “尚未校准 ⏳” 变为 “已校准 ✅”  
   - 校准成功后会记录基线角度
4. **等待手机端和受控端连接成功**
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

- **手机端提示连接失败？**  
  需要关闭电脑的防火墙，并重新连接。

---

## 项目结构

```
.
│── lambda  # 在 aws lambda 上运行的信令服务相关程序
│ ├── client.js  # 前端js
│ ├── index.html  # 前端主页
│ └── lambda_function.py  # 信令服务主程序
├── local_control.py  # 电脑端主程序
└── requirements.txt
```

---

## 许可证

MIT License
