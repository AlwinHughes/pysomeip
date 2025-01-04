from __future__ import annotations

import asyncio
import collections
import dataclasses
import ipaddress
import itertools
import logging
import os
import platform
import random
import socket
import struct
import threading
import typing

import someip.header
import someip.config
from someip.config import _T_SOCKNAME as _T_SOCKADDR
from someip.utils import log_exceptions, wait_cancelled

LOG = logging.getLogger("someip.sd")
_T_IPADDR = typing.Union[ipaddress.IPv4Address, ipaddress.IPv6Address]
_T_OPT_SOCKADDR = typing.Optional[_T_SOCKADDR]

from someip.protocol import SOMEIPDatagramProtocol
from someip.protocol import DatagramProtocolAdapter
from service_subscriber import ServiceSubscriber

from interfaces import IServiceDiscoveryProtocol

class ServiceDiscoveryProtocol(IServiceDiscoveryProtocol):
    @classmethod
    async def _create_endpoint(
        cls,
        loop: asyncio.BaseEventLoop,
        prot: SOMEIPDatagramProtocol,
        family: socket.AddressFamily,
        local_addr: str,
        port: int,
        multicast_addr: typing.Optional[str] = None,
        multicast_interface: typing.Optional[str] = None,
        ttl: int = 1,
    ):

        if family not in (socket.AF_INET, socket.AF_INET6):
            raise ValueError("only IPv4 and IPv6 supported, got {family!r}")

        if os.name == "posix":  # pragma: nocover
            # multicast binding:
            # - BSD: will only receive packets destined for multicast addr,
            #        but will send with address from bind()
            # - Linux: will receive all multicast traffic destined for this port,
            #          can be filtered using bind()
            bind_addr: typing.Optional[str] = local_addr
            if multicast_addr:
                bind_addr = None
                if platform.system() == "Linux":  # pragma: nocover
                    if family == socket.AF_INET or "%" in multicast_addr:
                        bind_addr = multicast_addr
                    else:
                        bind_addr = f"{multicast_addr}%{multicast_interface}"
            # wrong type in asyncio typeshed, should be optional
            bind_addr = typing.cast(str, bind_addr)

            trsp, _ = await loop.create_datagram_endpoint(
                lambda: DatagramProtocolAdapter(
                    prot, is_multicast=bool(multicast_addr)
                ),
                local_addr=(bind_addr, port),
                reuse_port=True,
                family=family,
                proto=socket.IPPROTO_UDP,
                flags=socket.AI_PASSIVE,
            )
        elif platform.system() == "Windows":  # pragma: nocover
            sock = socket.socket(
                family=family, type=socket.SOCK_DGRAM, proto=socket.IPPROTO_UDP
            )

            if (
                family == socket.AF_INET6
                and platform.python_version_tuple() < ("3", "8", "4")
                and isinstance(loop, getattr(asyncio, "ProactorEventLoop", ()))
            ):
                prot.log.warning(
                    "ProactorEventLoop has issues with ipv6 datagram sockets!"
                    " https://bugs.python.org/issue39148. Update to Python>=3.8.4, or"
                    " workaround with asyncio.set_event_loop_policy("
                    "asyncio.WindowsSelectorEventLoopPolicy())",
                )

            # python disallowed SO_REUSEADDR on create_datagram_endpoint.
            # https://bugs.python.org/issue37228
            # Windows doesnt have SO_REUSEPORT and the problem apparently does not exist
            # for multicast, so we need to set SO_REUSEADDR on the socket manually
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            addrinfos = await loop.getaddrinfo(
                local_addr,
                port,
                family=sock.family,
                type=sock.type,
                proto=sock.proto,
                flags=socket.AI_PASSIVE,
            )
            if not addrinfos:
                raise RuntimeError(
                    f"could not resolve local_addr={local_addr!r} port={port!r}"
                )

            ai = addrinfos[0]

            sock.bind(ai[4])
            trsp, _ = await loop.create_datagram_endpoint(
                lambda: DatagramProtocolAdapter(
                    prot, is_multicast=bool(multicast_addr)
                ),
                sock=sock,
            )
        else:  # pragma: nocover
            raise NotImplementedError(
                f"unsupported platform {os.name} {platform.system()}"
            )

        sock = trsp.get_extra_info("socket")

        try:
            if family == socket.AF_INET:
                packed_local_addr = pack_addr_v4(local_addr)
                if multicast_addr:
                    packed_mcast_addr = pack_addr_v4(multicast_addr)
                    mreq = struct.pack("=4s4s", packed_mcast_addr, packed_local_addr)
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
                sock.setsockopt(
                    socket.IPPROTO_IP, socket.IP_MULTICAST_IF, packed_local_addr
                )
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)

            else:  # AF_INET6
                if multicast_interface is None:
                    raise ValueError("ipv6 requires interface name")
                ifindex = socket.if_nametoindex(multicast_interface)
                if multicast_addr:
                    packed_mcast_addr = pack_addr_v6(multicast_addr)
                    mreq = struct.pack("=16sl", packed_mcast_addr, ifindex)
                    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)
                sock.setsockopt(
                    socket.IPPROTO_IPV6,
                    socket.IPV6_MULTICAST_IF,
                    struct.pack("=i", ifindex),
                )
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_HOPS, ttl)
        except BaseException:
            trsp.close()
            raise

        return trsp

    @classmethod
    async def create_endpoints(
        cls,
        family: socket.AddressFamily,
        local_addr: str,
        multicast_addr: str,
        multicast_interface: typing.Optional[str] = None,
        port: int = 30490,
        ttl=1,
        loop=None,
    ):
        if loop is None:  # pragma: nobranch
            loop = asyncio.get_event_loop()
        if not ip_address(multicast_addr).is_multicast:
            raise ValueError("multicast_addr is not multicast")

        # since posix does not provide a portable interface to figure out what address a
        # datagram was received on, we need one unicast and one multicast socket
        prot = cls((str(multicast_addr), port))

        # order matters, at least for Windows. If the multicast socket was created
        # first, both unicast and multicast packets would go to the multicast socket
        trsp_u = await cls._create_endpoint(
            loop,
            prot,
            family,
            local_addr,
            port,
            multicast_interface=multicast_interface,
            ttl=ttl,
        )

        trsp_m = await cls._create_endpoint(
            loop,
            prot,
            family,
            local_addr,
            port,
            multicast_addr=multicast_addr,
            multicast_interface=multicast_interface,
            ttl=ttl,
        )

        prot.transport = trsp_u

       return trsp_u, trsp_m, prot

    def __init__(
        self,
        multicast_addr: _T_SOCKADDR,
        timings: typing.Optional[Timings] = None,
        logger: str = "someip.sd",
    ):
        super().__init__(logger=logger)
        self.timings = timings or Timings()
        self.default_addr = multicast_addr
        self.discovery = ServiceDiscover(self)
        self.subscriber = ServiceSubscriber(self)
        self.announcer = ServiceAnnouncer(self)

    def message_received(
        self,
        someip_message: someip.header.SOMEIPHeader,
        addr: _T_SOCKADDR,
        multicast: bool,
    ) -> None:
        if (
            someip_message.service_id != someip.header.SD_SERVICE
            or someip_message.method_id != someip.header.SD_METHOD
            or someip_message.interface_version != someip.header.SD_INTERFACE_VERSION
            or someip_message.return_code != someip.header.SOMEIPReturnCode.E_OK
            or someip_message.message_type
            != someip.header.SOMEIPMessageType.NOTIFICATION
        ):
            self.log.error("SD protocol received non-SD message: %s", someip_message)
            return

        try:
            sdhdr, rest = someip.header.SOMEIPSDHeader.parse(someip_message.payload)
        except someip.header.ParseError as exc:
            self.log.error("SD-message did not parse: %r", exc)
            return

        if self.session_storage.check_received(
            addr, multicast, sdhdr.flag_reboot, someip_message.session_id
        ):
            self.reboot_detected(addr)

        # FIXME this will drop the SD Endpoint options, since they are not referenced by
        # entries. see 4.2.1 TR_SOMEIP_00548
        sdhdr_resolved = sdhdr.resolve_options()
        self.sd_message_received(sdhdr_resolved, addr, multicast)

        if rest:  # pragma: nocover
            self.log.warning(
                "unparsed data after SD from %s: %r", format_address(addr), rest
            )

    def send_sd(
        self,
        entries: typing.Collection[someip.header.SOMEIPSDEntry],
        remote: _T_OPT_SOCKADDR = None,
    ) -> None:
        if not entries:
            return
        flag_reboot, session_id = self.session_storage.assign_outgoing(remote)

        msg = someip.header.SOMEIPSDHeader(
            flag_reboot=flag_reboot,
            flag_unicast=True,  # 4.2.1, TR_SOMEIP_00540 receiving unicast is supported
            entries=tuple(entries),
        )
        msg_assigned = msg.assign_option_indexes()

        hdr = someip.header.SOMEIPHeader(
            service_id=someip.header.SD_SERVICE,
            method_id=someip.header.SD_METHOD,
            client_id=0,
            session_id=session_id,
            interface_version=1,
            message_type=someip.header.SOMEIPMessageType.NOTIFICATION,
            payload=msg_assigned.build(),
        )

        self.send(hdr.build(), remote)

    def start(self) -> None:
        self.subscriber.start()
        self.announcer.start()
        self.discovery.start()

    def stop(self) -> None:
        self.discovery.stop()
        self.announcer.stop()
        self.subscriber.stop()

    def connection_lost(self, exc: typing.Optional[Exception]) -> None:
        log = self.log.exception if exc else self.log.info
        log("connection lost. stopping all child tasks", exc_info=exc)
        asyncio.get_event_loop().call_soon(self.subscriber.connection_lost, exc)
        asyncio.get_event_loop().call_soon(self.discovery.connection_lost, exc)
        asyncio.get_event_loop().call_soon(self.announcer.connection_lost, exc)

    def reboot_detected(self, addr: _T_SOCKADDR) -> None:
        asyncio.get_event_loop().call_soon(self.subscriber.reboot_detected, addr)
        asyncio.get_event_loop().call_soon(self.discovery.reboot_detected, addr)
        asyncio.get_event_loop().call_soon(self.announcer.reboot_detected, addr)

    def sd_message_received(
        self, sdhdr: someip.header.SOMEIPSDHeader, addr: _T_SOCKADDR, multicast: bool
    ) -> None:
        """
        called when a well-formed SOME/IP SD message was received
        """
        LOG.debug(
            "sd_message_received received from %s (multicast=%r): %s",
            format_address(addr),
            multicast,
            sdhdr,
        )

        if not sdhdr.flag_unicast:
            # R21-11 PRS_SOMEIPSD_00843 ignoring multicast-only SD messages
            LOG.warning(
                "discarding multicast-only SD message from %s",
                format_address(addr),
            )
            return

        for entry in sdhdr.entries:
            if entry.sd_type == someip.header.SOMEIPSDEntryType.OfferService:
                asyncio.get_event_loop().call_soon(
                    self.discovery.handle_offer, entry, addr
                )
                continue

            if entry.sd_type == someip.header.SOMEIPSDEntryType.SubscribeAck:
                # TODO raise to application
                # TODO figure out what to do when not receiving an ACK after X?
                if entry.ttl == 0:
                    self.log.info("received Subscribe NACK from %s: %s", addr, entry)
                else:
                    self.log.info("received Subscribe ACK from %s: %s", addr, entry)
                continue

            if entry.sd_type == someip.header.SOMEIPSDEntryType.FindService:
                self.announcer.handle_findservice(
                    entry, addr, multicast
                )
                continue

            if (  # pragma: nobranch
                entry.sd_type == someip.header.SOMEIPSDEntryType.Subscribe
            ):
                if multicast:
                    self.log.warning(
                        "discarding subscribe received over multicast from %s: %s",
                        format_address(addr),
                        entry,
                    )
                    continue
                self.announcer.handle_subscribe(entry, addr)
                continue
