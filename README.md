# Oracle Cloud VPS Port Opener (Auto-Config OCI + iptables)

[English](#english) | [中文](#chinese)

---

<a name="english"></a>
## 🇬🇧 English Description

**OCI Port Opener** is a battle-tested Python automation script designed for Oracle Cloud Infrastructure (OCI) VPS users. It solves the fragmentation problem between the **Cloud Security Lists** (Web Console) and the **Local Firewall** (iptables).

Unlike simple wrapper scripts, this tool is built with **robustness** in mind, handling edge cases like firewall rule ordering, OCI API inconsistencies, and reboot persistence.

### 🌟 Why Use This?
*   **Safety First**: Automatically inserts `ACCEPT` rules *before* existing `REJECT` rules. Appends rules blindly (like `ufw allow`) often fails on Oracle images because the traffic gets rejected before it hits your new rule.
*   **Dual-Layer Sync**: Opens the port on OCI Network Security List AND local `iptables` simultaneously.
*   **Disaster Recovery**: Auto-backups your Cloud Security List to `~/.oci_backups/` before touching it.
*   **Zero Config**: Auto-detects Instance ID and Compartment ID via local metadata files.

### 📦 Dependencies

The script uses Python standard libraries (`json`, `subprocess`, `argparse`), but relies on the following system tools:

1.  **OCI CLI**: Must be installed and configured.
    ```bash
    # Install
    bash -c "$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)"
    # Setup
    oci setup config
    ```
2.  **iptables-persistent** (Recommended): For saving rules across reboots.
    ```bash
    sudo apt install iptables-persistent netfilter-persistent
    ```

### 🛠 Usage & Verification

**1. Open a Port**
```bash
python3 open_port.py 18520
```

**2. Verify (Crucial Step)**
Opening the port is only half the battle. You must have a service *listening* on that port to test it.

*   **On VPS (Server side)**: Start a temporary listener.
    ```bash
    nc -lvnp 18520
    # Output: Listening on 0.0.0.0 18520
    ```
*   **On Your PC (Client side)**: Try to connect.
    ```bash
    nc -vz <YOUR_VPS_IP> 18520
    # Output: Connection to ... succeeded!
    ```

### 🐛 Known Pitfalls & Dev Notes (What we learned)

*   **The `iptables -C` Trap**: When checking if a rule exists using `subprocess` in Python, you cannot rely on stdout. You MUST check the **Exit Code** (RC). RC 0 means exists, RC 1 means does not exist.
*   **OCI CLI JSON Inconsistency**: Some OCI CLI commands return the resource directly, while others wrap it in a `{"data": ...}` field. The script implements a robust extractor to handle both formats.
*   **Firewall Ordering**: On Oracle Ubuntu images, the default `iptables` rules end with a strict `REJECT`. If you just use `iptables -A` (Append), your rule sits *after* the Reject rule and does nothing. This script uses `iptables -I` (Insert) to place rules correctly.
*   **Persistence**: Ubuntu 24.04 on Oracle Cloud does not autosave iptables. We explicitly trigger `netfilter-persistent save` to prevent lockout after reboot.

---

<a name="chinese"></a>
## 🇨🇳 中文说明

**OCI Port Opener** 是一个为 Oracle Cloud (甲骨文云) 定制的硬核端口管理工具。它不仅仅是简单的命令封装，而是为了解决“云防火墙”与“本地防火墙”割裂、规则顺序错误导致无效、以及配置丢失等实际痛点。

### 🌟 核心特性
*   **智能插入规则**：脚本不会简单地追加规则（Append），而是会自动寻找 `REJECT` 规则的位置，并将新的 `ACCEPT` 规则插入到它**之前**。这是大多数通用工具（如 `ufw`）在 Oracle 默认镜像上失效的原因。
*   **双层同步**：一键打通 OCI 云端安全列表 (Security List) 和本地 `iptables`。
*   **防灾备份**：在修改云端策略前，自动将当前配置备份到 `~/.oci_backups/`。
*   **零配置启动**：通过读取 `cloud-init` 数据自动获取实例 ID，无需人工查找。

### 📦 依赖项

本脚本主要使用 Python 标准库，但依赖以下系统工具：

1.  **OCI CLI**: 必须安装并配置好 API Key。
    ```bash
    # 安装
    bash -c "$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)"
    # 配置
    oci setup config
    ```
2.  **iptables-persistent** (强烈建议): 用于持久化保存防火墙规则。
    ```bash
    sudo apt install iptables-persistent netfilter-persistent
    ```

### 🛠 使用与验证指南

**1. 开启端口**
```bash
python3 open_port.py 18520
```

**2. 验证测试 (必读)**
很多用户以为跑完脚本就通了，其实不然。如果端口上没有运行程序，外部扫描永远是“拒绝连接”。

*   **在 VPS 上 (服务端)**：启动一个临时监听器。
    ```bash
    nc -lvnp 18520
    # 看到: Listening on 0.0.0.0 18520
    ```
*   **在您电脑上 (客户端)**：尝试发起连接。
    ```bash
    nc -vz <你的VPS公网IP> 18520
    # 看到: Connection to ... succeeded! 才算真正成功
    ```

### 🐛 踩坑记录 (Dev Notes)

我们在开发过程中解决的几个关键问题，供开发者参考：

1.  **`iptables -C` 的陷阱**：在 Python 中调用 `iptables -C` (Check) 时，不能只看输出内容。必须通过 **Exit Code (返回码)** 来判断：0 代表规则存在，1 代表不存在。早期的脚本版本因为忽略了这点，导致误判“规则已存在”。
2.  **OCI CLI 输出格式不统一**：Oracle 的 CLI 命令返回格式很诡异，有时直接返回 JSON 对象，有时又包裹在 `{"data": ...}` 字段里。本脚本内置了一个鲁棒的解析器来同时兼容这两种格式。
3.  **防火墙顺序至关重要**：Oracle 官方镜像的 iptables 策略非常严格，最后一行通常是 `REJECT all`。如果使用默认的追加方式 (`-A`)，规则会排在拒绝规则之后，导致无效。必须使用 `-I` 指定行号插入。
4.  **持久化问题**：Ubuntu 24.04 默认不会自动保存 iptables 变动。我们增加了对 `netfilter-persistent` 的调用，确保重启后不翻车。

### 📜 License
MIT License
