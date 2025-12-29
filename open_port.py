#!/usr/bin/env python3
import argparse
import subprocess
import json
import sys
import os
import time

# 配置文件路径，用于缓存 Instance OCID 等信息，避免重复输入
CONFIG_FILE = os.path.expanduser("~/.oci_port_opener_config.json")
BACKUP_DIR = os.path.expanduser("~/.oci_backups")

def log(msg, level="INFO"):
    print(f"[{level}] {msg}")

def run_command(cmd, check=True, capture_output=True):
    """运行 Shell 命令。
    如果 check=True (默认): 失败时退出脚本，返回 stdout。
    如果 check=False: 返回 (returncode, stdout) 元组，让调用者处理。
    """
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            check=check, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        if check:
            return result.stdout.strip()
        else:
            return result.returncode, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if check:
            log(f"Command failed: {cmd}\nError: {e.stderr}", "ERROR")
            sys.exit(1)
        return e.returncode, e.stdout.strip() if e.stdout else ""

def get_instance_id():
    """获取实例 ID，优先读取缓存，其次尝试本地 cloud-init 文件，最后尝试 Metadata"""
    # 1. Check Config File
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                if config.get("instance_id"):
                    return config["instance_id"]
        except:
            pass

    # 2. Try Local Cloud-Init Files (Most reliable/fastest)
    log("Checking local cloud-init data for Instance OCID...", "DEBUG")
    try:
        # Check instance-data.json
        if os.path.exists("/run/cloud-init/instance-data.json"):
            with open("/run/cloud-init/instance-data.json", 'r') as f:
                data = json.load(f)
                # Structure can vary, check ds/meta_data/instance_id or simply instance_id
                if "instance_id" in data:
                    return save_config("instance_id", data["instance_id"])
                if "ds" in data and "meta_data" in data["ds"] and "instance_id" in data["ds"]["meta_data"]:
                    return save_config("instance_id", data["ds"]["meta_data"]["instance_id"])
                    
        # Check plain text file
        if os.path.exists("/var/lib/cloud/data/instance-id"):
            with open("/var/lib/cloud/data/instance-id", 'r') as f:
                val = f.read().strip()
                if val:
                    return save_config("instance_id", val)
    except Exception as e:
        log(f"Failed to read local instance data: {e}", "DEBUG")

    # 3. Try Metadata Service (Fallback)
    log("Attempting to fetch Instance OCID from metadata service...", "DEBUG")
    meta_cmd = 'curl -s --connect-timeout 2 -H "Authorization: Bearer Oracle" http://169.254.169.254/opc/v2/instance/'
    try:
        rc, output = run_command(meta_cmd, check=False)
        if rc == 0 and output:
            data = json.loads(output)
            if "id" in data:
                return save_config("instance_id", data["id"])
    except:
        pass

    # 4. Prompt User
    log("Could not auto-detect Instance OCID.", "WARNING")
    log("Please enter your Oracle Cloud Instance OCID (ocid1.instance.oc1...):")
    val = input("> ").strip()
    if val:
        return save_config("instance_id", val)
    
    log("Instance OCID is required for OCI operations.", "ERROR")
    sys.exit(1)

def save_config(key, value):
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
        except:
            pass
    config[key] = value
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)
    return value

def configure_local_firewall(port, protocol):
    """配置本地 iptables"""
    log(f"Configuring local firewall for Port {port}/{protocol}...")
    
    # 1. Check if rule exists
    check_cmd = f"sudo iptables -C INPUT -p {protocol} --dport {port} -j ACCEPT 2>/dev/null"
    rc, _ = run_command(check_cmd, check=False)
    if rc == 0:
        log(f"Local rule for {port}/{protocol} already exists. Skipping.")
        return

    # 2. Find position of REJECT rule
    # 我们希望插入到 REJECT 规则之前，或者如果没有 REJECT，就插到最后（但在 POLICY DROP 之前）
    # 为简单起见，且确保有效，通常插入到 INPUT 链的头部（位置 1）或已知允许规则之后。
    # 更稳妥的做法是：插入到第一条 REJECT 规则之前。
    
    lines = run_command("sudo iptables -L INPUT -n --line-numbers").splitlines()
    insert_pos = 1
    found_reject = False
    
    for line in lines:
        parts = line.split()
        if len(parts) >= 2 and (parts[1] == "REJECT" or parts[1] == "DROP"):
            insert_pos = int(parts[0])
            found_reject = True
            break
            
    if not found_reject:
        # 如果没有明确的 REJECT 规则，通常追加即可，但为了保险插入到最后
        insert_pos = len(lines) # Approximate, append
        cmd = f"sudo iptables -A INPUT -p {protocol} --dport {port} -j ACCEPT"
    else:
        # 插入到 REJECT 之前
        cmd = f"sudo iptables -I INPUT {insert_pos} -p {protocol} --dport {port} -j ACCEPT"

    log(f"Executing: {cmd}")
    run_command(cmd)
    
    # 3. Persistence
    # 尝试多种持久化方式
    rc_np, _ = run_command("which netfilter-persistent", check=False)
    if rc_np == 0:
        run_command("sudo netfilter-persistent save", check=False)
    else:
        rc_svc, _ = run_command("which service", check=False)
        if rc_svc == 0:
            run_command("sudo service iptables save", check=False)
    
    log("Local firewall configured successfully.")

def get_security_list_id(instance_id):
    """查找实例关联的主安全列表"""
    log("Fetching network details from OCI...")
    
    # 0. Get Instance Details to get Compartment ID
    inst_json = run_command(f"oci compute instance get --instance-id {instance_id} --output json")
    inst_data = json.loads(inst_json)
    comp_id = inst_data['data']['compartment-id']
    
    # 1. Get VNIC Attachments (Requires Compartment ID)
    vnic_atts_resp = json.loads(run_command(f"oci compute vnic-attachment list --instance-id {instance_id} --compartment-id {comp_id} --all --output json"))
    vnic_atts = vnic_atts_resp.get('data', vnic_atts_resp)
    
    if not vnic_atts:
        log("No VNIC attachments found.", "ERROR")
        sys.exit(1)
    vnic_id = vnic_atts[0]['vnic-id']
    
    # 2. Get VNIC details to find Subnet
    vnic_resp = json.loads(run_command(f"oci network vnic get --vnic-id {vnic_id} --output json"))
    vnic = vnic_resp.get('data', vnic_resp)
    subnet_id = vnic['subnet-id']
    
    # 3. Get Subnet details to find Security Lists
    subnet_resp = json.loads(run_command(f"oci network subnet get --subnet-id {subnet_id} --output json"))
    subnet = subnet_resp.get('data', subnet_resp)
    
    sec_lists = subnet['security-list-ids']
    if not sec_lists:
        log("No Security Lists associated with the subnet.", "ERROR")
        sys.exit(1)
        
    return sec_lists[0] # Default to the first one

def configure_oci_security_list(sl_id, port, protocol):
    """安全的更新 OCI Security List"""
    log(f"Checking OCI Security List: {sl_id}...")
    
    # 1. Fetch current rules
    sl_json = run_command(f"oci network security-list get --security-list-id {sl_id} --output json")
    sl_data = json.loads(sl_json)
    current_ingress = sl_data['data']['ingress-security-rules']
    
    # 2. Check for existence
    # OCI uses protocol numbers: TCP=6, UDP=17
    proto_num = "6" if protocol == "tcp" else "17"
    
    for rule in current_ingress:
        if rule['protocol'] == proto_num:
            # Check port range
            if protocol == "tcp" and 'tcp-options' in rule and rule['tcp-options']:
                 if check_port_match(rule['tcp-options'], port):
                     log(f"OCI rule for {port}/{protocol} already exists. Skipping.")
                     return
            if protocol == "udp" and 'udp-options' in rule and rule['udp-options']:
                 if check_port_match(rule['udp-options'], port):
                     log(f"OCI rule for {port}/{protocol} already exists. Skipping.")
                     return
    
    # 3. Create new rule object
    new_rule = {
        "source": "0.0.0.0/0",
        "protocol": proto_num,
        "is-stateless": False,
        "description": f"Auto-opened port {port} via script"
    }
    
    port_opts = {
        "source-port-range": None,
        "destination-port-range": {
            "min": int(port),
            "max": int(port)
        }
    }
    
    if protocol == "tcp":
        new_rule["tcp-options"] = port_opts
    else:
        new_rule["udp-options"] = port_opts
        
    current_ingress.append(new_rule)
    
    # 4. Backup
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    timestamp = int(time.time())
    backup_path = os.path.join(BACKUP_DIR, f"sl_{sl_id}_{timestamp}.json")
    with open(backup_path, 'w') as f:
        json.dump(sl_data, f, indent=2)
    log(f"Backup of Security List saved to: {backup_path}")
    
    # 5. Update
    log("Updating OCI Security List... (This effectively overwrites the list with the new set)")
    
    # Update command requires a file or string. Passing as string argument is tricky with shell quoting.
    # Safest way is to write to a temp file.
    update_payload_file = os.path.join(BACKUP_DIR, f"update_payload_{timestamp}.json")
    with open(update_payload_file, 'w') as f:
        json.dump(current_ingress, f)
        
    update_cmd = f"oci network security-list update --security-list-id {sl_id} --ingress-security-rules file://{update_payload_file} --force"
    run_command(update_cmd)
    
    log("OCI Security List updated successfully.")
    os.remove(update_payload_file)

def check_port_match(options, target_port):
    """Helper to check if a port is covered by existing options"""
    if not options or 'destination-port-range' not in options:
        return False # Matches all ports if not specified? Usually OCI requires it.
    
    r = options['destination-port-range']
    if not r: return False
    return r['min'] <= int(target_port) <= r['max']

def main():
    parser = argparse.ArgumentParser(description="Open port on Oracle Cloud VPS (Local + OCI)")
    parser.add_argument("port", help="Port number to open")
    parser.add_argument("--proto", choices=["tcp", "udp"], default="tcp", help="Protocol (tcp/udp)")
    parser.add_argument("--local-only", action="store_true", help="Only configure local firewall")
    args = parser.parse_args()

    # 1. Configure Local Firewall
    configure_local_firewall(args.port, args.proto)
    
    if args.local_only:
        log("Skipping OCI configuration as requested.")
        return

    # 2. Configure OCI
    try:
        instance_id = get_instance_id()
        sl_id = get_security_list_id(instance_id)
        configure_oci_security_list(sl_id, args.port, args.proto)
    except Exception as e:
        log(f"OCI Configuration failed: {e}", "ERROR")
        log("Local firewall was updated, but cloud firewall might still block traffic.", "WARNING")

if __name__ == "__main__":
    main()
