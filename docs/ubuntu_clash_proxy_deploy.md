# Ubuntu 全新环境部署 Clash（Mihomo）代理指南

> 适用场景：全新 Ubuntu 22.04/24.04 服务器或桌面环境，需要通过 Clash 内核进行 HTTP/SOCKS 代理。
>
> 说明：当前社区主流内核是 **Mihomo（Clash Meta）**，本文以 Mihomo 为准。

## 1. 准备系统环境

```bash
sudo apt update
sudo apt install -y curl wget gzip tar ca-certificates
```

确认架构（后面下载对应二进制）：

```bash
uname -m
# x86_64 -> amd64
# aarch64 -> arm64
```

## 2. 下载并安装 Mihomo

创建目录：

```bash
sudo mkdir -p /etc/mihomo
sudo mkdir -p /var/log/mihomo
```

自动下载最新稳定版（按架构匹配）：

```bash
ARCH="$(dpkg --print-architecture)"
case "$ARCH" in
  amd64) PATTERN='mihomo-linux-amd64-.*\.gz' ;;
  arm64) PATTERN='mihomo-linux-arm64-.*\.gz' ;;
  *) echo "不支持的架构: $ARCH"; exit 1 ;;
esac

URL="$(curl -fsSL https://api.github.com/repos/MetaCubeX/mihomo/releases/latest \
  | grep browser_download_url \
  | cut -d '"' -f 4 \
  | grep -E "$PATTERN" \
  | head -n1)"

echo "下载地址: $URL"
curl -fL "$URL" -o /tmp/mihomo.gz
gzip -dc /tmp/mihomo.gz | sudo tee /usr/local/bin/mihomo >/dev/null
sudo chmod +x /usr/local/bin/mihomo
```

验证：

```bash
/usr/local/bin/mihomo -v
```

## 3. 放置配置文件

你需要一份可用的 `config.yaml`（通常来自订阅转换或自建配置），放到：

```bash
sudo nano /etc/mihomo/config.yaml
```

一个最小骨架（只示例关键项，实际需补全 `proxies/proxy-groups/rules`）：

```yaml
mixed-port: 7890
allow-lan: false
mode: rule
log-level: info
external-controller: 127.0.0.1:9090
secret: "change-this-controller-secret"

dns:
  enable: true
  ipv6: false
  enhanced-mode: fake-ip
```

> 如果你只让服务器本机走代理，保持 `allow-lan: false` 即可，不要对公网暴露代理端口。

## 4. 配置 systemd 自启动

创建服务文件：

```bash
sudo nano /etc/systemd/system/mihomo.service
```

写入：

```ini
[Unit]
Description=Mihomo (Clash) Proxy Daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/etc/mihomo
ExecStart=/usr/local/bin/mihomo -d /etc/mihomo
Restart=on-failure
RestartSec=5
LimitNOFILE=1048576
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_BIND_SERVICE CAP_NET_RAW
CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_BIND_SERVICE CAP_NET_RAW
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

启动并设为开机自启：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mihomo
sudo systemctl status mihomo --no-pager
```

查看实时日志：

```bash
journalctl -u mihomo -f
```

## 5. 防火墙（UFW）建议

如果你只在服务器本机使用代理：

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw enable
sudo ufw status verbose
```

> 此场景下不需要开放 `7890/9090` 到公网。

如果你要给局域网设备使用（不建议直接对公网开放）：

1. `config.yaml` 里改为 `allow-lan: true`
2. UFW 仅放行内网网段，例如：

```bash
sudo ufw allow from 192.168.1.0/24 to any port 7890 proto tcp
sudo ufw allow from 192.168.1.0/24 to any port 9090 proto tcp
```

## 6. 让系统命令走代理

临时生效（当前 shell）：

```bash
export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890
export all_proxy=socks5://127.0.0.1:7890
export no_proxy=127.0.0.1,localhost,.local
```

永久生效（当前用户）：

```bash
cat <<'EOF' >> ~/.bashrc
export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890
export all_proxy=socks5://127.0.0.1:7890
export no_proxy=127.0.0.1,localhost,.local
EOF

source ~/.bashrc
```

## 7. 连通性验证

```bash
curl -I https://github.com
curl --proxy http://127.0.0.1:7890 https://api.ipify.org
```

若第二条返回的 IP 与服务器公网 IP 不同，说明代理生效。

## 8. 常见问题排查

1. `systemctl status mihomo` 启动失败
   - 先看日志：`journalctl -u mihomo -n 200 --no-pager`
   - 常见原因：`config.yaml` 语法错误、订阅内容不完整。

2. 端口未监听
   - 检查：`ss -lntp | grep -E '7890|9090'`
   - 没监听通常是内核没启动成功或配置未加载。

3. DNS 异常
   - 先确认 `dns.enable: true`
   - 再看日志里是否出现 DNS upstream 失败。

4. 只能密码登录、代理配置后 SSH 断连
   - 先确保防火墙已放行 SSH：`sudo ufw allow OpenSSH`
   - 对网络策略做变更前，建议开两个 SSH 会话避免锁死。

## 9. 升级与卸载

升级（重复第 2 步下载覆盖）：

```bash
sudo systemctl restart mihomo
```

卸载：

```bash
sudo systemctl disable --now mihomo
sudo rm -f /etc/systemd/system/mihomo.service
sudo rm -f /usr/local/bin/mihomo
sudo rm -rf /etc/mihomo
sudo systemctl daemon-reload
```

---

## 参考链接

- Mihomo 仓库（发布与二进制）：https://github.com/MetaCubeX/mihomo
- Mihomo 文档站（配置与功能）：https://wiki.metacubex.one
- Ubuntu 官方社区与文档入口：https://ubuntu.com
