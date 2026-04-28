# PingPong

PingPong 是一个 Windows 桌面小工具，用来并发测试 YouTube、ChatGPT 和 Claude 的 HTTPS 连通状态与延迟。

## 使用方式

双击 `Start PingPong.bat` 启动。

## 说明

这里测试的是 HTTPS 连通延迟，不是传统 ICMP ping。YouTube、ChatGPT 和 Claude 这类网站可能不响应普通 ping，但只要能收到 HTTP 响应，就说明当前网络或 VPN 已经能连到对应服务。
