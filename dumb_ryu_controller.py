from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.topology.event import EventSwitchEnter, EventSwitchLeave
from ryu.lib.mac import haddr_to_bin
from ryu.ofproto import ofproto_v1_0
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types

from topology import load_topology
import networkx as nx

# This function takes as input a networkx graph. It then computes
# the minimum Spanning Tree, and returns it, as a networkx graph.
def compute_spanning_tree(G):

    # The Spanning Tree of G
    ST = nx.minimum_spanning_tree(G)

    return ST


def my_compute_spanning_tree(graph):
    print graph.node


class L2Forwarding(app_manager.RyuApp):
    def __init__(self, *args, **kwargs):
        super(L2Forwarding, self).__init__(*args, **kwargs)

        # Load the topology
        topo_file = 'topology.txt'
        self.G = load_topology(topo_file)

        # For each node in the graph, add an attribute mac-to-port
        for n in self.G.nodes():
            self.G.add_node(n, mactoport={})

        self.mac_to_port = {}

        self.counter = 0

        # Compute a Spanning Tree for the graph G
        self.ST = compute_spanning_tree(self.G)

        print self.get_str_topo(self.G)
        print self.get_str_topo(self.ST)
        my_compute_spanning_tree(self.G)

    # This method returns a string that describes a graph (nodes and edges, with
    # their attributes). You do not need to modify this method.
    def get_str_topo(self, graph):
        res = 'Nodes\tneighbors:port_id\n'

        att = nx.get_node_attributes(graph, 'ports')
        for n in graph.nodes_iter():
            res += str(n)+'\t'+str(att[n])+'\n'

        res += 'Edges:\tfrom->to\n'
        for f in graph:
            totmp = []
            for t in graph[f]:
                totmp.append(t)
            res += str(f)+' -> '+str(totmp)+'\n'

        return res

    # This method returns a string that describes the Mac-to-Port table of a
    # switch in the graph. You do not need to modify this method.
    def get_str_mactoport(self, graph, dpid):
        res = 'MAC-To-Port table of the switch '+str(dpid)+'\n'

        for mac_addr, outport in graph.node[dpid]['mactoport'].items():
            res += str(mac_addr)+' -> '+str(outport)+'\n'

        return res.rstrip('\n')

    @set_ev_cls(EventSwitchEnter)
    def _ev_switch_enter_handler(self, ev):
        print('enter: %s' % ev)

    @set_ev_cls(EventSwitchLeave)
    def _ev_switch_leave_handler(self, ev):
        print('leave: %s' % ev)

    # from simple_switch.py
    def add_flow(self, datapath, in_port, dst, actions):
        ofproto = datapath.ofproto

        match = datapath.ofproto_parser.OFPMatch(
            in_port=in_port, dl_dst=haddr_to_bin(dst))

        mod = datapath.ofproto_parser.OFPFlowMod(
            datapath=datapath, match=match, cookie=0,
            command=ofproto.OFPFC_ADD, idle_timeout=0, hard_timeout=0,
            priority=ofproto.OFP_DEFAULT_PRIORITY,
            flags=ofproto.OFPFF_SEND_FLOW_REM, actions=actions)
        datapath.send_msg(mod)

    def get_neighbors(self, dpid, graph):
        neighbors = [graph.node[dpid]['ports']['host']]
        for neighbor in graph[dpid]:
            neighbors.append(graph.node[dpid]['ports'][str(neighbor)])
        return neighbors

    def flood_on_graph(self, dpid, datapath):
        neighbors = self.get_neighbors(dpid, self.ST)
        actions = []
        for out_port in neighbors:
            actions.append(ofp_parser.OFPActionOutput(out_port))
        out = ofp_parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id, in_port=msg.in_port,
                                      actions=actions)
        datapath.send_msg(out)

    # This method is called every time an OF_PacketIn message is received by
    # the switch. Here we must calculate the best action to take and install
    # a new entry on the switch's forwarding table if necessary
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        dst = eth.dst
        src = eth.src

        print "destination: " + str(dst) + "\tsource: " + src

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        # graph.node[dpid]['mactoport'][src] = msg.in_port
        # print self.get_str_mactoport(graph, dpid)

        self.mac_to_port[dpid][src] = msg.in_port
        # print self.get_str_mactoport(self.ST, dpid)
        res = 'MAC-To-Port table of the switch ' + str(dpid) + '\n'
        for mac_addr, outport in self.ST.node[dpid].items():
            res += str(mac_addr) + ' -> ' + str(outport) + '\n'
            print res

        if dst in self.mac_to_port[dpid]:
            # print "found in dictionary"
            out_port = self.mac_to_port[dpid][dst]
            # print "out_port: " + str(out_port)
            actions = [ofp_parser.OFPActionOutput(out_port)]
            self.add_flow(datapath, msg.in_port, dst, actions)
            out = ofp_parser.OFPPacketOut(
                datapath=datapath, buffer_id=msg.buffer_id, in_port=msg.in_port,
                actions=actions)
            datapath.send_msg(out)
        else:
            neighbors = self.get_neighbors(dpid, self.ST)
            actions = []
            for out_port in neighbors:
                actions.append(ofp_parser.OFPActionOutput(out_port))
            out = ofp_parser.OFPPacketOut(
                datapath=datapath, buffer_id=msg.buffer_id, in_port=msg.in_port,
                actions=actions)
            datapath.send_msg(out)

            # out_port = ofproto.OFPP_FLOOD
            # actions = [ofp_parser.OFPActionOutput(out_port)]
            # out = ofp_parser.OFPPacketOut(
            #     datapath=datapath, buffer_id=msg.buffer_id, in_port=msg.in_port,
            #     actions=actions)
            # datapath.send_msg(out)

            # for mac_addr, outport in self.ST.node[dpid].items():
            #     for key, value in outport.items():
            #         actions = [ofp_parser.OFPActionOutput(value)]
            #         out = ofp_parser.OFPPacketOut(
            #                 datapath=datapath, buffer_id=msg.buffer_id, in_port=msg.in_port,
            #                 actions=actions)
            #         datapath.send_msg(out)

            # att = nx.get_node_attributes(self.ST, 'ports')
            # neighbors = self.ST[dpid]
            # str_neighbors = str(neighbors)
            # print str_neighbors
            # print att[dpid]

            # print neighbors
            # print "can't find in dictionary"
            # att = nx.get_node_attributes(self.ST, 'ports')
            # print att[dpid]['host']
            # outport = att[dpid]['host']
            # actions = [ofp_parser.OFPActionOutput(outport)]
            #
            # data = None
            # if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            #     data = msg.data
            #
            # out = ofp_parser.OFPPacketOut(
            #     datapath=datapath, buffer_id=msg.buffer_id, in_port=msg.in_port,
            #     actions=actions, data=data)
            # datapath.send_msg(out)

            # for neighbor, port in att[dpid].iteritems():
            #     print neighbor, port
            #     if neighbor == 'host':
            #         print "I am equal to the host"
            #     actions = [ofp_parser.OFPActionOutput(port)]
            #     out = ofp_parser.OFPPacketOut(
            #         datapath=datapath, buffer_id=msg.buffer_id, in_port=msg.in_port,
            #         actions=actions)
            #     datapath.send_msg(out)

        # actions = [ofp_parser.OFPActionOutput(out_port)]

        # if out_port != ofp.OFPP_FLOOD:
        #     self.add_flow(datapath, msg.in_port, dst, actions)


    # We create an OF_PacketOut message with action of type FLOOD
    # This simple forwarding action works only for loopless topologies
        #actions = [ofp_parser.OFPActionOutput(ofp.OFPP_FLOOD)]
        # out = ofp_parser.OFPPacketOut(
        #     datapath=datapath, buffer_id=msg.buffer_id, in_port=msg.in_port,
        #     actions=actions)
        # datapath.send_msg(out)

