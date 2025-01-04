import socket
import typing

_T_IPADDR = typing.Union[ipaddress.IPv4Address, ipaddress.IPv6Address]

#4 all from util
def ip_address(s: str) -> _T_IPADDR:
    return ipaddress.ip_address(s.split("%", 1)[0])


def pack_addr_v4(a):
    return socket.inet_pton(socket.AF_INET, a.split("%", 1)[0])


def pack_addr_v6(a):
    return socket.inet_pton(socket.AF_INET6, a.split("%", 1)[0])


def format_address(addr: _T_SOCKADDR) -> str:
    host, port = socket.getnameinfo(addr, socket.NI_NUMERICHOST | socket.NI_NUMERICSERV)
    ip = ipaddress.ip_address(host)
    if isinstance(ip, ipaddress.IPv4Address):
        return f"{ip!s}:{port:s}"
    elif isinstance(ip, ipaddress.IPv6Address):
        return f"[{ip!s}]:{port:s}"
    else:  # pragma: nocover
        raise NotImplementedError(f"unknown ip address format: {addr!r} -> {ip!r}")
