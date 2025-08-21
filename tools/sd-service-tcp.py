
import asyncio
import socket
import logging

import someip.config
import someip.header
from someip.sd import ServiceDiscoveryProtocol as SDProto, ClientServiceListener, ServerServiceListener, ServiceInstance, Timings, SOMEIPTCPServerProtocol
from someip.sd import SOMEIPTCPServerProtocol


import ipaddress

def setup_log(fmt="", **kwargs):
    try:
        import coloredlogs  # type: ignore[import]
        coloredlogs.install(fmt="%(asctime)s,%(msecs)03d " + fmt, **kwargs)
    except ModuleNotFoundError:
        logging.basicConfig(format="%(asctime)s " + fmt, **kwargs)
        logging.info("install coloredlogs for colored logs :-)")

async def run():

    transport, prot = await SOMEIPTCPServerProtocol.create_unicast_endpoint(('127.0.0.2', 20000))
    asyncio.ensure_future(transport.serve_forever())

    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass

#class AlwinSSL(ServerServiceListener):



async def run2():
    #local_addr = "127.0.0.1"
    
    local_addr = "192.168.44.235"
    multicast_addr = "229.168.110.1"
    service_port = 5555

    trsp_u, trsp_m, protocol = await SDProto.create_endpoints(
        family=socket.AF_INET,
        local_addr=str(local_addr),
        multicast_addr=str(multicast_addr),
        port=30490,
    )

    

    config = someip.config.Service(0xAAAA, options_1=[someip.header.IPv4EndpointOption(address=ipaddress.ip_address(local_addr), l4proto=someip.header.L4Protocols.TCP, port=service_port)], reliable=True)
    instance = ServiceInstance(config, ServerServiceListener(), protocol.announcer, Timings)

    protocol.announcer.announce_service(instance)
    protocol.start()


    service_prot, service_trans = await SOMEIPTCPServerProtocol.create_unicast_endpoint(local_addr=(local_addr, service_port))

    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass


def main():
    setup_log("%(levelname)-8s %(name)s: %(message)s", level=logging.DEBUG)

    try:
        asyncio.get_event_loop().run_until_complete(
            run2()
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":

    sockname="bob"
    naddr = "127.0.0.1" 

    option1 = someip.header.IPv4EndpointOption(
            address="127.0.0.1", l4proto=someip.header.L4Protocols.TCP, port=12345
    )
    service_config = someip.config.Service(service_id = 0x00AA, options_1 = [option1])
    print(service_config)


    print(service_config.options_1)
    print(service_config.create_offer_entry())
    #service_anouncer = 

    main()
