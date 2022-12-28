#!/usr/bin/env python3
import os
import time
from functools import partial
from subprocess import Popen, PIPE
import argparse

from mininet.node import CPULimitedHost
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.log import setLogLevel, info
from mininet.node import RemoteController
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.topolib import TreeNet
from mininet.node import Host
from mininet.term import makeTerm


PARSER = argparse.ArgumentParser()

PARSER.add_argument("--broadcast", "-b", dest="use_broadcast", default=False,
                    action="store_true", help="Run the OVS with broadcast instead of individual forwarding.")
PARSER.add_argument("--servers", "-e", dest="servers", type=int, default=1,
                    help="Specify the number of servers that should be launched.")
ARGS = PARSER.parse_args()


class PikeTopo(Topo):

    def __init__(self, sw_path=None, json_path=None, pcap_dump=False, num_hosts=None, **opts):
        "The custom BlueBridge topo we use for testing."

        # Initialize topology
        Topo.__init__(self, **opts)
        switch = self.addSwitch("s1")
        # Create a network topology of a single switch
        # connected to three nodes.
        # +------s1------+
        # |      |       |
        # h1     h2      h3
        for h in range(num_hosts):
            host = self.addHost("h%d" % (h + 1),
                                ip="10.0.0.%d/24" % (h + 1),
                                mac="00:04:00:00:00:%02x" % h)
            self.addLink(host, switch)


def generateServerTargets(num_hosts):
    server_str = ""
    for host_id in range(2, num_hosts + 1):
        server_str += "01%02x::," % host_id
    server_str = server_str[:-1]
    return server_str


def configureHosts(net, num_hosts):
    hosts = net.hosts
    server_str = generateServerTargets(num_hosts)
    for host_id, host in enumerate(hosts):

        # Insert host configuration
        config_str = ("\"INTERFACE=%s-eth0\nHOSTS=%s\nSERVERPORT=5000\nSRCPORT=0\n"
                      "SRCADDR=01%02x::\nDEBUG=1\" > ./tmp/config/topo.cnf > ./tmp/config/"
                      "topo.cnf" % (host, server_str, host_id + 1))
        host.cmdPrint("echo " + config_str)
        # Configure the interface and respective routing
        host.cmdPrint(
            "ip address change dev %s-eth0 scope global 01%02x::/16" % (host, host_id + 1))
        host.cmdPrint("ip -6 route add 0100::/8  dev %s-eth0" % host)
        # host.cmdPrint("ip -6 route add local 0:0:01" +
        #               "{0:02x}".format(hostNum) + "::/48 dev lo")
        # Gotta get dem jumbo frames
        host.cmdPrint("ifconfig " + str(host) + "-eth0 mtu 9000")

        if host_id != 0:
            # Just run the server
            host.cmdPrint("xterm  -T \"server%s\" -e \"./apps/bin/event_server "
                          "-c tmp/config/topo.cnf; bash\" &" % str(host)[1])
            # host.cmdPrint("./apps/bin/server tmp/config/topo.cnf &")


def configureSwitch(num_hosts):

    if ARGS.use_broadcast:
        # Flood all packets
        os.system("ovs-ofctl add-flow s1 priority=3,actions=output:flood")
    else:
        for host_id in range(1, num_hosts + 1):
            # Routing entries per port
            cmd = ("ovs-ofctl add-flow s1 dl_type=0x86DD,ipv6_dst=10%d::/16,"
                   "priority=1,actions=output:%d" % (host_id, host_id))
            os.system(cmd)
            cmd = ("ovs-ofctl add-flow s1 dl_type=0x86DD,ipv6_src=10%d::/16,"
                   "ipv6_dst=10%d::/16,priority=2,"
                   "actions=output:in_port" % (host_id, host_id))
            os.system(cmd)
    for host_id in range(1, num_hosts + 1):
        # Gotta get dem jumbo frames
        os.system("ifconfig s1-eth%d mtu 9000" % host_id)
    # Flood NDP requests (Deprecated)
    os.system(
        "ovs-ofctl add-flow s1 dl_type=0x86DD,ipv6_dst=ff02::1:ff00:0,priority=1,actions=output:flood")


def clean():
    " Clean any the running instances of POX "
    Popen("killall xterm", stdout=PIPE, shell=True)
    # Popen("mn -c", stdout=PIPE, shell=True)


def run():
    num_hosts = 1 + ARGS.servers
    privateDirs = [("./tmp/config", "/tmp/%(name)s/var/config")]
    host = partial(Host, privateDirs=privateDirs)
    topo = PikeTopo(num_hosts=num_hosts)
    net = Mininet(topo=topo, host=host, build=False, controller=None)
    net.build()
    net.start()
    directories = [directory[0] if isinstance(directory, tuple)
                   else directory for directory in privateDirs]
    info("Private Directories:", directories, "\n")

    # Configure our current "switch"
    configureSwitch(num_hosts)
    # Configure routing and generate the bluebridge settings
    configureHosts(net, num_hosts)
    # net.startTerms()

    makeTerm(net.hosts[0])  # The client
    # makeTerm(net.hosts[1]) # Thrift remote_mem server
    # makeTerm(net.hosts[2]) # Thrift simple_arr_comp server

    CLI(net)
    net.stop()
    clean()


if __name__ == "__main__":
    setLogLevel("info")
    run()
