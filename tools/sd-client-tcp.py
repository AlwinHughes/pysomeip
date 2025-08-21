import asyncio
import socket
import logging

import someip.config
from someip.sd import ServiceDiscoveryProtocol as SDProto, ClientServiceListener, SOMEIPTCPServerProtocol
from someip.sd import SOMEIPTCPClient 

class Monitor(ClientServiceListener):

    def __init__(self, event):
        self.event = event
        self.source = None

    def service_offered(self, service, source):
        print(f"service offered: {service}")
        self.source = service.options_1
        self.event.set()

    def service_stopped(self, service, source):
        print(f"service stopped: {service}")


def setup_log(fmt="", **kwargs):
    try:
        import coloredlogs  # type: ignore[import]
        coloredlogs.install(fmt="%(asctime)s,%(msecs)03d " + fmt, **kwargs)
    except ModuleNotFoundError:
        logging.basicConfig(format="%(asctime)s " + fmt, **kwargs)
        logging.info("install coloredlogs for colored logs :-)")

async def run():


    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass

async def run2():
    local_addr = "127.0.0.2"
    multicast_addr = "229.168.110.1"

    trsp_u, trsp_m, protocol = await SDProto.create_endpoints(
        family=socket.AF_INET,
        local_addr=str(local_addr),
        multicast_addr=str(multicast_addr),
        port=30490,
    )

    event = asyncio.Event()
    config = someip.config.Service(0xAAAA, reliable=False)
    m = Monitor(event)
    protocol.discovery.watch_service(config, m)

    await event.wait()
    print(m.source)
    print(m.source[0])

    client_transport, client_prot = await SOMEIPTCPClient.create_unicast_endpoint((str(m.source[0].address), m.source[0].port))

    print(f" transport: {client_transport} proto: {client_prot}")

    #instance = ServiceInstance(config, ServerServiceListener(), protocol.announcer, Timings)

    try:
        while True:
            await asyncio.sleep(1)

            client_transport.write(someip.header.SOMEIPHeader(
                service_id = 0xAAAA,
                method_id = 1,
                client_id = 0xBEAF,
                session_id = 0,
                interface_version = 1,
                message_type = someip.header.SOMEIPMessageType.REQUEST,
                protocol_version = 1,
                return_code  = someip.header.SOMEIPReturnCode.E_OK,
                payload = b"AAAAAAAAAAAAAAAAAAAAAA"
                ).build())
            #await client_transport.drain()
    except asyncio.CancelledError:
        pass



def main():
    setup_log("%(levelname)-8s %(name)s: %(message)s", level=logging.DEBUG)

    #service = someip.config.Service(0x00AA, 0x0001, 0x0001, 0x0001)
    #print(service)
    #print(service.create_offer_entry())
    try:
        asyncio.get_event_loop().run_until_complete(
            run2()
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
