# Oracle Cloud VPS Port Opener (Auto-Config OCI + iptables)

[English](#english) | [中文](#chinese)

---

<a name="english"></a>
## 🇬🇧 English Description

**OCI Port Opener** is a Python automation script designed for Oracle Cloud Infrastructure (OCI) VPS users. It solves the common headache of having to manually configure both the **Cloud Security Lists** (Web Console) and the **Local Firewall** (iptables) every time you need to open a port.

With a single command, this tool safely opens ports on both layers, ensuring your services are accessible without risking SSH lockouts.

### Key Features
*   **Dual-Layer Configuration**:
    *   **Cloud (OCI)**: Automatically detects your instance's VCN and Security List, adding Ingress Rules via OCI CLI.
    *   **Local (OS)**: Detects `iptables` rules and inserts the `ACCEPT` rule *before* the `REJECT` rule (crucial for Ubuntu/Oracle Linux).
*   **Safety First**:
    *   Backs up your Cloud Security List to `~/.oci_backups/` before every modification.
    *   Never deletes existing rules; only appends new ones.
*   **Zero-Config (Auto-Discovery)**:
    *   Automatically fetches your Instance OCID from local `cloud-init` metadata. No manual copy-pasting required.
*   **Persistence**:
    *   Ensures `iptables` rules survive reboots using `netfilter-persistent`.

### Prerequisites
1.  **Python 3** (Pre-installed on most modern Linux distros).
2.  **OCI CLI & API Key**:
    *   The script requires `oci` CLI installed and configured (`~/.oci/config`).
    *   *If you haven't configured OCI CLI, the script will guide you or fail gracefully.*

### Usage

**1. Open a TCP Port (Default)**
```bash
python3 open_port.py 8080
```

**2. Open a UDP Port**
```bash
python3 open_port.py 5000 --proto udp
```

**3. Configure Local Firewall Only (Skip Cloud)**
```bash
python3 open_port.py 8080 --local-only
```

### Installation
Simply clone this repository or download the `open_port.py` script to your VPS.
```bash
chmod +x open_port.py
# Optional: Move to path for global usage
sudo cp open_port.py /usr/local/bin/open-port
```

---

<a name="chinese"></a>
## 🇨🇳 中文说明

**OCI Port Opener** 是一个专为 Oracle Cloud (甲骨文云) VPS 用户设计的 Python 自动化工具。它解决了每次开端口都需要同时操作“网页控制台安全列表”和“本地防火墙”的繁琐问题。

只需一条命令，即可同时打通云端和本地的两层防火墙，且保证不会因为配置错误导致 SSH 失联。

### 核心功能
*   **双重配置**：
    *   **云端 (OCI)**：自动识别实例所在的 VCN 和安全列表 (Security List)，并通过 OCI CLI 添加允许规则。
    *   **本地 (OS)**：自动检测 `iptables` 规则，并将 `ACCEPT` 规则智能插入到 `REJECT` 规则**之前**（这对 Ubuntu/Oracle Linux 至关重要）。
*   **安全保障**：
    *   每次修改前，自动备份当前的云端安全列表到 `~/.oci_backups/` 目录。
    *   只增不减：脚本仅追加新规则，绝不删除或覆盖您现有的其他规则。
*   **零配置 (自动发现)**：
    *   自动从本地 `cloud-init` 元数据中读取 Instance OCID，无需人工手动查找和输入 ID。
*   **持久化**：
    *   自动调用 `netfilter-persistent` 保存本地规则，确保 VPS 重启后端口依然开放。

### 前置要求
1.  **Python 3** (现代 Linux 发行版通常已预装)。
2.  **OCI CLI & API Key**:
    *   脚本运行需要依赖 `oci` 命令行工具及正确的配置 (`~/.oci/config`)。
    *   *如果您尚未配置 OCI CLI，请先参考 Oracle 官方文档配置 API Key。*

### 使用方法

**1. 开启 TCP 端口 (默认)**
```bash
python3 open_port.py 8080
```

**2. 开启 UDP 端口**
```bash
python3 open_port.py 5000 --proto udp
```

**3. 仅配置本地防火墙 (跳过云端)**
```bash
python3 open_port.py 8080 --local-only
```

### 安装
直接克隆本仓库或下载 `open_port.py` 脚本到您的 VPS 即可。
```bash
chmod +x open_port.py
# 可选：移动到系统路径方便全局调用
sudo cp open_port.py /usr/local/bin/open-port
```