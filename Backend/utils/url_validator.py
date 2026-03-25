import re
from urllib.parse import urlparse
import ipaddress
import socket


class URLValidator:
    # 禁止的內部 IP 範圍
    BLOCKED_IP_RANGES = [
        ipaddress.ip_network("127.0.0.0/8"),  # Loopback
        ipaddress.ip_network("10.0.0.0/8"),  # Private
        ipaddress.ip_network("172.16.0.0/12"),  # Private
        ipaddress.ip_network("192.168.0.0/16"),  # Private
        ipaddress.ip_network("169.254.0.0/16"),  # Link-local
        ipaddress.ip_network("::1/128"),  # IPv6 loopback
        ipaddress.ip_network("fc00::/7"),  # IPv6 private
        ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
    ]

    # 允許的協議白名單
    ALLOWED_SCHEMES = ["https", "http"]

    # 允許的域名白名單（根據實際需求配置）
    ALLOWED_DOMAINS = [
        "api.openai.com",
        "103.124.72.114",
        "219.86.90.181",
        "219.86.90.170",
        "api-ams.twcc.ai",
        "211.79.49.98",
    ]

    ALLOWED_PORTS = [8000, 8080]

    @classmethod
    def validate_base_url(cls, url: str) -> tuple[bool, str]:
        """
        驗證 base_url 是否安全

        Args:
            url: 要驗證的 URL

        Returns:
            (is_valid, error_message)
        """
        if not url:
            return False, "URL 不能為空"

        try:
            # 解析 URL
            parsed = urlparse(url)

            # 1. 驗證協議
            if parsed.scheme not in cls.ALLOWED_SCHEMES:
                return (
                    False,
                    f"不允許的協議: {parsed.scheme}，僅支援 {cls.ALLOWED_SCHEMES}",
                )

            # 2. 驗證主機名不為空
            if not parsed.netloc:
                return False, "主機名不能為空"

            # 3. 提取主機名（去除端口）
            hostname = parsed.hostname
            if not hostname:
                return False, "無效的主機名"

            # 4. 檢查是否為 IP 地址
            try:
                ip = ipaddress.ip_address(hostname)
                # 檢查是否為內部 IP
                for blocked_range in cls.BLOCKED_IP_RANGES:
                    if ip in blocked_range:
                        return False, f"禁止存取內部 IP 地址: {ip}"
            except ValueError:
                # 不是 IP 地址，是域名
                pass

            # 5. DNS 解析檢查（防止 DNS rebinding）
            try:
                resolved_ips = socket.getaddrinfo(hostname, None)
                for addr_info in resolved_ips:
                    ip_str = addr_info[4][0]
                    try:
                        ip = ipaddress.ip_address(ip_str)
                        for blocked_range in cls.BLOCKED_IP_RANGES:
                            if ip in blocked_range:
                                return False, f"域名解析到內部 IP: {hostname} -> {ip}"
                    except ValueError:
                        continue
            except socket.gaierror:
                return False, f"無法解析域名: {hostname}"

            # 6. 域名白名單檢查
            domain_allowed = False
            for allowed_domain in cls.ALLOWED_DOMAINS:
                if hostname == allowed_domain or hostname.endswith(
                    "." + allowed_domain
                ):
                    domain_allowed = True
                    break

            if not domain_allowed:
                return False, f"域名不在白名單中: {hostname}"

            # 7. 檢查端口（如果指定）
            if parsed.port:
                if parsed.port not in cls.ALLOWED_PORTS:  # 僅允許標準端口
                    return False, f"不允許的端口: {parsed.port}"

            return True, "驗證通過"

        except Exception as e:
            return False, f"URL 驗證錯誤: {str(e)}"

    @classmethod
    def sanitize_url(cls, url: str) -> str:
        """
        清理和標準化 URL
        """
        url = url.strip()
        # 移除可能的惡意字符
        url = re.sub(r"[\r\n\t]", "", url)
        return url
