# Copyright (C) 2013 Nippon Telegraph and Telephone Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import logging
import netaddr

from ryu.ofproto import ether
from ryu.ofproto import inet
from ryu.ofproto import ofproto_v1_3
from ryu.ofproto import ofproto_v1_3_parser
from ryu.lib import hub
from ryu.lib import ofctl_utils


LOG = logging.getLogger('ryu.lib.ofctl_v1_3')

DEFAULT_TIMEOUT = 1.0

UTIL = ofctl_utils.OFCtlUtil(ofproto_v1_3)


def to_action(dp, dic):
    ofp = dp.ofproto
    parser = dp.ofproto_parser

    action_type = dic.get('type')
    if action_type == 'OUTPUT':
        out_port = UTIL.ofp_port_from_user(dic.get('port', ofp.OFPP_ANY))
        max_len = UTIL.ofp_cml_from_user(dic.get('max_len', ofp.OFPCML_MAX))
        result = parser.OFPActionOutput(out_port, max_len)
    elif action_type == 'COPY_TTL_OUT':
        result = parser.OFPActionCopyTtlOut()
    elif action_type == 'COPY_TTL_IN':
        result = parser.OFPActionCopyTtlIn()
    elif action_type == 'SET_MPLS_TTL':
        mpls_ttl = int(dic.get('mpls_ttl'))
        result = parser.OFPActionSetMplsTtl(mpls_ttl)
    elif action_type == 'DEC_MPLS_TTL':
        result = parser.OFPActionDecMplsTtl()
    elif action_type == 'PUSH_VLAN':
        ethertype = int(dic.get('ethertype'))
        result = parser.OFPActionPushVlan(ethertype)
    elif action_type == 'POP_VLAN':
        result = parser.OFPActionPopVlan()
    elif action_type == 'PUSH_MPLS':
        ethertype = int(dic.get('ethertype'))
        result = parser.OFPActionPushMpls(ethertype)
    elif action_type == 'POP_MPLS':
        ethertype = int(dic.get('ethertype'))
        result = parser.OFPActionPopMpls(ethertype)
    elif action_type == 'SET_QUEUE':
        queue_id = UTIL.ofp_queue_from_user(dic.get('queue_id'))
        result = parser.OFPActionSetQueue(queue_id)
    elif action_type == 'GROUP':
        group_id = UTIL.ofp_group_from_user(dic.get('group_id'))
        result = parser.OFPActionGroup(group_id)
    elif action_type == 'SET_NW_TTL':
        nw_ttl = int(dic.get('nw_ttl'))
        result = parser.OFPActionSetNwTtl(nw_ttl)
    elif action_type == 'DEC_NW_TTL':
        result = parser.OFPActionDecNwTtl()
    elif action_type == 'SET_FIELD':
        field = dic.get('field')
        value = dic.get('value')
        result = parser.OFPActionSetField(**{field: value})
    elif action_type == 'PUSH_PBB':
        ethertype = int(dic.get('ethertype'))
        result = parser.OFPActionPushPbb(ethertype)
    elif action_type == 'POP_PBB':
        result = parser.OFPActionPopPbb()
    else:
        result = None

    return result


def to_actions(dp, acts):
    inst = []
    actions = []
    ofp = dp.ofproto
    parser = dp.ofproto_parser

    for a in acts:
        action = to_action(dp, a)

        if action is not None:
            actions.append(action)
        else:
            action_type = a.get('type')
            if action_type == 'WRITE_ACTIONS':
                write_actions = []
                write_acts = a.get('actions')
                for a in write_acts:
                    action = to_action(dp, a)
                    if action is not None:
                        write_actions.append(action)
                    else:
                        LOG.error('Unknown action type: %s', action_type)
                if write_actions:
                    inst.append(parser.OFPInstructionActions(ofp.OFPIT_WRITE_ACTIONS,
                                                             write_actions))
            elif action_type == 'CLEAR_ACTIONS':
                inst.append(parser.OFPInstructionActions(
                            ofp.OFPIT_CLEAR_ACTIONS, []))
            elif action_type == 'GOTO_TABLE':
                table_id = UTIL.ofp_table_from_user(a.get('table_id'))
                inst.append(parser.OFPInstructionGotoTable(table_id))
            elif action_type == 'WRITE_METADATA':
                metadata = ofctl_utils.str_to_int(a.get('metadata'))
                metadata_mask = (ofctl_utils.str_to_int(a['metadata_mask'])
                                 if 'metadata_mask' in a
                                 else parser.UINT64_MAX)
                inst.append(
                    parser.OFPInstructionWriteMetadata(
                        metadata, metadata_mask))
            elif action_type == 'METER':
                meter_id = UTIL.ofp_meter_from_user(a.get('meter_id'))
                inst.append(parser.OFPInstructionMeter(meter_id))
            else:
                LOG.error('Unknown action type: %s', action_type)

    if actions:
        inst.append(parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS,
                                                 actions))
    return inst


def action_to_str(act):
    action_type = act.cls_action_type

    if action_type == ofproto_v1_3.OFPAT_OUTPUT:
        port = UTIL.ofp_port_to_user(act.port)
        buf = 'OUTPUT:' + str(port)
    elif action_type == ofproto_v1_3.OFPAT_COPY_TTL_OUT:
        buf = 'COPY_TTL_OUT'
    elif action_type == ofproto_v1_3.OFPAT_COPY_TTL_IN:
        buf = 'COPY_TTL_IN'
    elif action_type == ofproto_v1_3.OFPAT_SET_MPLS_TTL:
        buf = 'SET_MPLS_TTL:' + str(act.mpls_ttl)
    elif action_type == ofproto_v1_3.OFPAT_DEC_MPLS_TTL:
        buf = 'DEC_MPLS_TTL'
    elif action_type == ofproto_v1_3.OFPAT_PUSH_VLAN:
        buf = 'PUSH_VLAN:' + str(act.ethertype)
    elif action_type == ofproto_v1_3.OFPAT_POP_VLAN:
        buf = 'POP_VLAN'
    elif action_type == ofproto_v1_3.OFPAT_PUSH_MPLS:
        buf = 'PUSH_MPLS:' + str(act.ethertype)
    elif action_type == ofproto_v1_3.OFPAT_POP_MPLS:
        buf = 'POP_MPLS:' + str(act.ethertype)
    elif action_type == ofproto_v1_3.OFPAT_SET_QUEUE:
        queue_id = UTIL.ofp_queue_to_user(act.queue_id)
        buf = 'SET_QUEUE:' + str(queue_id)
    elif action_type == ofproto_v1_3.OFPAT_GROUP:
        group_id = UTIL.ofp_group_to_user(act.group_id)
        buf = 'GROUP:' + str(group_id)
    elif action_type == ofproto_v1_3.OFPAT_SET_NW_TTL:
        buf = 'SET_NW_TTL:' + str(act.nw_ttl)
    elif action_type == ofproto_v1_3.OFPAT_DEC_NW_TTL:
        buf = 'DEC_NW_TTL'
    elif action_type == ofproto_v1_3.OFPAT_SET_FIELD:
        buf = 'SET_FIELD: {%s:%s}' % (act.key, act.value)
    elif action_type == ofproto_v1_3.OFPAT_PUSH_PBB:
        buf = 'PUSH_PBB:' + str(act.ethertype)
    elif action_type == ofproto_v1_3.OFPAT_POP_PBB:
        buf = 'POP_PBB'
    else:
        buf = 'UNKNOWN'
    return buf


def actions_to_str(instructions):
    actions = []

    for instruction in instructions:
        if isinstance(instruction,
                      ofproto_v1_3_parser.OFPInstructionActions):
            if instruction.type == ofproto_v1_3.OFPIT_APPLY_ACTIONS:
                for a in instruction.actions:
                    actions.append(action_to_str(a))
            elif instruction.type == ofproto_v1_3.OFPIT_WRITE_ACTIONS:
                write_actions = []
                for a in instruction.actions:
                    write_actions.append(action_to_str(a))
                if write_actions:
                    actions.append({'WRITE_ACTIONS': write_actions})
            elif instruction.type == ofproto_v1_3.OFPIT_CLEAR_ACTIONS:
                actions.append('CLEAR_ACTIONS')
            else:
                actions.append('UNKNOWN')
        elif isinstance(instruction,
                        ofproto_v1_3_parser.OFPInstructionGotoTable):
            table_id = UTIL.ofp_table_to_user(instruction.table_id)
            buf = 'GOTO_TABLE:' + str(table_id)
            actions.append(buf)

        elif isinstance(instruction,
                        ofproto_v1_3_parser.OFPInstructionWriteMetadata):
            buf = ('WRITE_METADATA:0x%x/0x%x' % (instruction.metadata,
                                                 instruction.metadata_mask)
                   if instruction.metadata_mask
                   else 'WRITE_METADATA:0x%x' % instruction.metadata)
            actions.append(buf)

        elif isinstance(instruction,
                        ofproto_v1_3_parser.OFPInstructionMeter):
            meter_id = UTIL.ofp_meter_to_user(instruction.meter_id)
            buf = 'METER:' + str(meter_id)
            actions.append(buf)

        else:
            continue

    return actions


def to_match(dp, attrs):
    convert = {'in_port': UTIL.ofp_port_from_user,
               'in_phy_port': int,
               'metadata': to_match_masked_int,
               'dl_dst': to_match_eth,
               'dl_src': to_match_eth,
               'eth_dst': to_match_eth,
               'eth_src': to_match_eth,
               'dl_type': int,
               'eth_type': int,
               'dl_vlan': to_match_vid,
               'vlan_vid': to_match_vid,
               'vlan_pcp': int,
               'ip_dscp': int,
               'ip_ecn': int,
               'nw_proto': int,
               'ip_proto': int,
               'nw_src': to_match_ip,
               'nw_dst': to_match_ip,
               'ipv4_src': to_match_ip,
               'ipv4_dst': to_match_ip,
               'tp_src': int,
               'tp_dst': int,
               'tcp_src': int,
               'tcp_dst': int,
               'udp_src': int,
               'udp_dst': int,
               'sctp_src': int,
               'sctp_dst': int,
               'icmpv4_type': int,
               'icmpv4_code': int,
               'arp_op': int,
               'arp_spa': to_match_ip,
               'arp_tpa': to_match_ip,
               'arp_sha': to_match_eth,
               'arp_tha': to_match_eth,
               'ipv6_src': to_match_ip,
               'ipv6_dst': to_match_ip,
               'ipv6_flabel': int,
               'icmpv6_type': int,
               'icmpv6_code': int,
               'ipv6_nd_target': to_match_ip,
               'ipv6_nd_sll': to_match_eth,
               'ipv6_nd_tll': to_match_eth,
               'mpls_label': int,
               'mpls_tc': int,
               'mpls_bos': int,
               'pbb_isid': to_match_masked_int,
               'tunnel_id': to_match_masked_int,
               'ipv6_exthdr': to_match_masked_int}

    keys = {'dl_dst': 'eth_dst',
            'dl_src': 'eth_src',
            'dl_type': 'eth_type',
            'dl_vlan': 'vlan_vid',
            'nw_src': 'ipv4_src',
            'nw_dst': 'ipv4_dst',
            'nw_proto': 'ip_proto'}

    if attrs.get('dl_type') == ether.ETH_TYPE_ARP or \
            attrs.get('eth_type') == ether.ETH_TYPE_ARP:
        if 'nw_src' in attrs and 'arp_spa' not in attrs:
            attrs['arp_spa'] = attrs['nw_src']
            del attrs['nw_src']
        if 'nw_dst' in attrs and 'arp_tpa' not in attrs:
            attrs['arp_tpa'] = attrs['nw_dst']
            del attrs['nw_dst']

    kwargs = {}
    for key, value in attrs.items():
        if key in keys:
            # For old field name
            key = keys[key]
        if key in convert:
            value = convert[key](value)
            if key == 'tp_src' or key == 'tp_dst':
                # TCP/UDP port
                conv = {inet.IPPROTO_TCP: {'tp_src': 'tcp_src',
                                           'tp_dst': 'tcp_dst'},
                        inet.IPPROTO_UDP: {'tp_src': 'udp_src',
                                           'tp_dst': 'udp_dst'}}
                ip_proto = attrs.get('nw_proto', attrs.get('ip_proto', 0))
                key = conv[ip_proto][key]
                kwargs[key] = value
            else:
                # others
                kwargs[key] = value
        else:
            LOG.error('Unknown match field: %s', key)

    return dp.ofproto_parser.OFPMatch(**kwargs)


def to_match_eth(value):
    if '/' in value:
        value = value.split('/')
        return value[0], value[1]
    else:
        return value


def to_match_ip(value):
    if '/' in value:
        (ip_addr, ip_mask) = value.split('/')
        if ip_mask.isdigit():
            ip = netaddr.ip.IPNetwork(value)
            ip_addr = str(ip.ip)
            ip_mask = str(ip.netmask)
        return ip_addr, ip_mask
    else:
        return value


def to_match_vid(value):
    # NOTE: If "vlan_id/dl_vlan" field is described as decimal int value
    #       (and decimal string value), it is treated as values of
    #       VLAN tag, and OFPVID_PRESENT(0x1000) bit is automatically
    #       applied. OTOH, If it is described as hexadecimal string,
    #       treated as values of oxm_value (including OFPVID_PRESENT
    #       bit), and OFPVID_PRESENT bit is NOT automatically applied.
    if isinstance(value, int):
        # described as decimal int value
        return value | ofproto_v1_3.OFPVID_PRESENT
    else:
        if '/' in value:
            val = value.split('/')
            return int(val[0], 0), int(val[1], 0)
        else:
            if value.isdigit():
                # described as decimal string value
                return int(value, 10) | ofproto_v1_3.OFPVID_PRESENT
            else:
                return int(value, 0)


def to_match_masked_int(value):
    if isinstance(value, str) and '/' in value:
        value = value.split('/')
        return (ofctl_utils.str_to_int(value[0]),
                ofctl_utils.str_to_int(value[1]))
    else:
        return ofctl_utils.str_to_int(value)


def match_to_str(ofmatch):

    keys = {'eth_src': 'dl_src',
            'eth_dst': 'dl_dst',
            'eth_type': 'dl_type',
            'vlan_vid': 'dl_vlan',
            'ipv4_src': 'nw_src',
            'ipv4_dst': 'nw_dst',
            'ip_proto': 'nw_proto',
            'tcp_src': 'tp_src',
            'tcp_dst': 'tp_dst',
            'udp_src': 'tp_src',
            'udp_dst': 'tp_dst'
            }

    match = {}

    ofmatch = ofmatch.to_jsondict()['OFPMatch']
    ofmatch = ofmatch['oxm_fields']

    for match_field in ofmatch:
        key = match_field['OXMTlv']['field']
        if key in keys:
            key = keys[key]
        mask = match_field['OXMTlv']['mask']
        value = match_field['OXMTlv']['value']
        if key == 'dl_vlan':
            value = match_vid_to_str(value, mask)
        elif key == 'in_port':
            value = UTIL.ofp_port_to_user(value)
        else:
            if mask is not None:
                value = str(value) + '/' + str(mask)
        match.setdefault(key, value)

    return match


def match_vid_to_str(value, mask):
    if mask is not None:
        value = '0x%04x/0x%04x' % (value, mask)
    else:
        if value & ofproto_v1_3.OFPVID_PRESENT:
            value = str(value & ~ofproto_v1_3.OFPVID_PRESENT)
        else:
            value = '0x%04x' % value
    return value


def send_stats_request(dp, stats, waiters, msgs):
    dp.set_xid(stats)
    waiters_per_dp = waiters.setdefault(dp.id, {})
    lock = hub.Event()
    previous_msg_len = len(msgs)
    waiters_per_dp[stats.xid] = (lock, msgs)
    dp.send_msg(stats)

    lock.wait(timeout=DEFAULT_TIMEOUT)
    current_msg_len = len(msgs)

    while current_msg_len > previous_msg_len:
        previous_msg_len = current_msg_len
        lock.wait(timeout=DEFAULT_TIMEOUT)
        current_msg_len = len(msgs)

    if not lock.is_set():
        del waiters_per_dp[stats.xid]


def get_desc_stats(dp, waiters):
    stats = dp.ofproto_parser.OFPDescStatsRequest(dp, 0)
    msgs = []
    send_stats_request(dp, stats, waiters, msgs)
    s = {}

    for msg in msgs:
        stats = msg.body
        s = {'mfr_desc': stats.mfr_desc,
             'hw_desc': stats.hw_desc,
             'sw_desc': stats.sw_desc,
             'serial_num': stats.serial_num,
             'dp_desc': stats.dp_desc}
    desc = {str(dp.id): s}
    return desc


def get_queue_stats(dp, waiters):
    ofp = dp.ofproto
    stats = dp.ofproto_parser.OFPQueueStatsRequest(dp, 0, ofp.OFPP_ANY,
                                                   ofp.OFPQ_ALL)
    msgs = []
    send_stats_request(dp, stats, waiters, msgs)

    s = []
    for msg in msgs:
        stats = msg.body
        for stat in stats:
            s.append({'duration_nsec': stat.duration_nsec,
                      'duration_sec': stat.duration_sec,
                      'port_no': stat.port_no,
                      'queue_id': stat.queue_id,
                      'tx_bytes': stat.tx_bytes,
                      'tx_errors': stat.tx_errors,
                      'tx_packets': stat.tx_packets})
    desc = {str(dp.id): s}
    return desc


def get_queue_config(dp, port, waiters):
    ofp = dp.ofproto
    port = UTIL.ofp_port_from_user(port)
    stats = dp.ofproto_parser.OFPQueueGetConfigRequest(dp, port)
    msgs = []
    send_stats_request(dp, stats, waiters, msgs)

    prop_type = {dp.ofproto.OFPQT_MIN_RATE: 'MIN_RATE',
                 dp.ofproto.OFPQT_MAX_RATE: 'MAX_RATE',
                 dp.ofproto.OFPQT_EXPERIMENTER: 'EXPERIMENTER',
                 }

    configs = []
    for config in msgs:
        queue_list = []
        for queue in config.queues:
            prop_list = []
            for prop in queue.properties:
                p = {'property': prop_type.get(prop.property, 'UNKNOWN')}
                if prop.property == dp.ofproto.OFPQT_MIN_RATE or \
                   prop.property == dp.ofproto.OFPQT_MAX_RATE:
                    p['rate'] = prop.rate
                elif prop.property == dp.ofproto.OFPQT_EXPERIMENTER:
                    p['experimenter'] = prop.experimenter
                    p['data'] = prop.data
                prop_list.append(p)
            q = {'port': UTIL.ofp_port_to_user(queue.port),
                 'properties': prop_list,
                 'queue_id': UTIL.ofp_queue_to_user(queue.queue_id)}
            queue_list.append(q)
        c = {'port': UTIL.ofp_port_to_user(config.port),
             'queues': queue_list}
        configs.append(c)
    configs = {str(dp.id): configs}

    return configs


def get_flow_stats(dp, waiters, flow=None):
    flow = flow if flow else {}
    table_id = UTIL.ofp_table_from_user(
        flow.get('table_id', dp.ofproto.OFPTT_ALL))
    flags = int(flow.get('flags', 0))
    out_port = UTIL.ofp_port_from_user(
        flow.get('out_port', dp.ofproto.OFPP_ANY))
    out_group = UTIL.ofp_group_from_user(
        flow.get('out_group', dp.ofproto.OFPG_ANY))
    cookie = int(flow.get('cookie', 0))
    cookie_mask = int(flow.get('cookie_mask', 0))
    match = to_match(dp, flow.get('match', {}))

    stats = dp.ofproto_parser.OFPFlowStatsRequest(
        dp, flags, table_id, out_port, out_group, cookie, cookie_mask,
        match)

    msgs = []
    send_stats_request(dp, stats, waiters, msgs)

    flows = []
    for msg in msgs:
        for stats in msg.body:
            actions = actions_to_str(stats.instructions)
            match = match_to_str(stats.match)

            s = {'priority': stats.priority,
                 'cookie': stats.cookie,
                 'idle_timeout': stats.idle_timeout,
                 'hard_timeout': stats.hard_timeout,
                 'actions': actions,
                 'match': match,
                 'byte_count': stats.byte_count,
                 'duration_sec': stats.duration_sec,
                 'duration_nsec': stats.duration_nsec,
                 'packet_count': stats.packet_count,
                 'table_id': UTIL.ofp_table_to_user(stats.table_id),
                 'length': stats.length,
                 'flags': stats.flags}
            flows.append(s)
    flows = {str(dp.id): flows}

    return flows


def get_aggregate_flow_stats(dp, waiters, flow=None):
    flow = flow if flow else {}
    table_id = UTIL.ofp_table_from_user(
        flow.get('table_id', dp.ofproto.OFPTT_ALL))
    flags = int(flow.get('flags', 0))
    out_port = UTIL.ofp_port_from_user(
        flow.get('out_port', dp.ofproto.OFPP_ANY))
    out_group = UTIL.ofp_group_from_user(
        flow.get('out_group', dp.ofproto.OFPG_ANY))
    cookie = int(flow.get('cookie', 0))
    cookie_mask = int(flow.get('cookie_mask', 0))
    match = to_match(dp, flow.get('match', {}))

    stats = dp.ofproto_parser.OFPAggregateStatsRequest(
        dp, flags, table_id, out_port, out_group, cookie, cookie_mask,
        match)

    msgs = []
    send_stats_request(dp, stats, waiters, msgs)

    flows = []
    for msg in msgs:
        stats = msg.body
        s = {'packet_count': stats.packet_count,
             'byte_count': stats.byte_count,
             'flow_count': stats.flow_count}
        flows.append(s)
    flows = {str(dp.id): flows}

    return flows


def get_table_stats(dp, waiters):
    stats = dp.ofproto_parser.OFPTableStatsRequest(dp, 0)
    msgs = []
    send_stats_request(dp, stats, waiters, msgs)

    tables = []
    for msg in msgs:
        stats = msg.body
        for stat in stats:
            s = {'table_id': UTIL.ofp_table_to_user(stat.table_id),
                 'active_count': stat.active_count,
                 'lookup_count': stat.lookup_count,
                 'matched_count': stat.matched_count}
            tables.append(s)
    desc = {str(dp.id): tables}

    return desc


def get_table_features(dp, waiters):
    stats = dp.ofproto_parser.OFPTableFeaturesStatsRequest(dp, 0, [])
    msgs = []
    ofproto = dp.ofproto
    send_stats_request(dp, stats, waiters, msgs)

    prop_type = {ofproto.OFPTFPT_INSTRUCTIONS: 'INSTRUCTIONS',
                 ofproto.OFPTFPT_INSTRUCTIONS_MISS: 'INSTRUCTIONS_MISS',
                 ofproto.OFPTFPT_NEXT_TABLES: 'NEXT_TABLES',
                 ofproto.OFPTFPT_NEXT_TABLES_MISS: 'NEXT_TABLES_MISS',
                 ofproto.OFPTFPT_WRITE_ACTIONS: 'WRITE_ACTIONS',
                 ofproto.OFPTFPT_WRITE_ACTIONS_MISS: 'WRITE_ACTIONS_MISS',
                 ofproto.OFPTFPT_APPLY_ACTIONS: 'APPLY_ACTIONS',
                 ofproto.OFPTFPT_APPLY_ACTIONS_MISS: 'APPLY_ACTIONS_MISS',
                 ofproto.OFPTFPT_MATCH: 'MATCH',
                 ofproto.OFPTFPT_WILDCARDS: 'WILDCARDS',
                 ofproto.OFPTFPT_WRITE_SETFIELD: 'WRITE_SETFIELD',
                 ofproto.OFPTFPT_WRITE_SETFIELD_MISS: 'WRITE_SETFIELD_MISS',
                 ofproto.OFPTFPT_APPLY_SETFIELD: 'APPLY_SETFIELD',
                 ofproto.OFPTFPT_APPLY_SETFIELD_MISS: 'APPLY_SETFIELD_MISS',
                 ofproto.OFPTFPT_EXPERIMENTER: 'EXPERIMENTER',
                 ofproto.OFPTFPT_EXPERIMENTER_MISS: 'EXPERIMENTER_MISS'
                 }

    p_type_instructions = [ofproto.OFPTFPT_INSTRUCTIONS,
                           ofproto.OFPTFPT_INSTRUCTIONS_MISS]

    p_type_next_tables = [ofproto.OFPTFPT_NEXT_TABLES,
                          ofproto.OFPTFPT_NEXT_TABLES_MISS]

    p_type_actions = [ofproto.OFPTFPT_WRITE_ACTIONS,
                      ofproto.OFPTFPT_WRITE_ACTIONS_MISS,
                      ofproto.OFPTFPT_APPLY_ACTIONS,
                      ofproto.OFPTFPT_APPLY_ACTIONS_MISS]

    p_type_oxms = [ofproto.OFPTFPT_MATCH,
                   ofproto.OFPTFPT_WILDCARDS,
                   ofproto.OFPTFPT_WRITE_SETFIELD,
                   ofproto.OFPTFPT_WRITE_SETFIELD_MISS,
                   ofproto.OFPTFPT_APPLY_SETFIELD,
                   ofproto.OFPTFPT_APPLY_SETFIELD_MISS]

    p_type_experimenter = [ofproto.OFPTFPT_EXPERIMENTER,
                           ofproto.OFPTFPT_EXPERIMENTER_MISS]

    tables = []
    for msg in msgs:
        stats = msg.body
        for stat in stats:
            properties = []
            for prop in stat.properties:
                p = {'type': prop_type.get(prop.type, 'UNKNOWN')}
                if prop.type in p_type_instructions:
                    instruction_ids = []
                    for id in prop.instruction_ids:
                        i = {'len': id.len,
                             'type': id.type}
                        instruction_ids.append(i)
                    p['instruction_ids'] = instruction_ids
                elif prop.type in p_type_next_tables:
                    table_ids = []
                    for id in prop.table_ids:
                        table_ids.append(id)
                    p['table_ids'] = table_ids
                elif prop.type in p_type_actions:
                    action_ids = []
                    for id in prop.action_ids:
                        i = {'len': id.len,
                             'type': id.type}
                        action_ids.append(i)
                    p['action_ids'] = action_ids
                elif prop.type in p_type_oxms:
                    oxm_ids = []
                    for id in prop.oxm_ids:
                        i = {'hasmask': id.hasmask,
                             'length': id.length,
                             'type': id.type}
                        oxm_ids.append(i)
                    p['oxm_ids'] = oxm_ids
                elif prop.type in p_type_experimenter:
                    pass
                properties.append(p)
            s = {'table_id': UTIL.ofp_table_to_user(stat.table_id),
                 'name': stat.name.decode('utf-8'),
                 'metadata_match': stat.metadata_match,
                 'metadata_write': stat.metadata_write,
                 'config': stat.config,
                 'max_entries': stat.max_entries,
                 'properties': properties,
                 }
            tables.append(s)
    desc = {str(dp.id): tables}

    return desc


def get_port_stats(dp, waiters):
    stats = dp.ofproto_parser.OFPPortStatsRequest(
        dp, 0, dp.ofproto.OFPP_ANY)
    msgs = []
    send_stats_request(dp, stats, waiters, msgs)

    ports = []
    for msg in msgs:
        for stats in msg.body:
            s = {'port_no': UTIL.ofp_port_to_user(stats.port_no),
                 'rx_packets': stats.rx_packets,
                 'tx_packets': stats.tx_packets,
                 'rx_bytes': stats.rx_bytes,
                 'tx_bytes': stats.tx_bytes,
                 'rx_dropped': stats.rx_dropped,
                 'tx_dropped': stats.tx_dropped,
                 'rx_errors': stats.rx_errors,
                 'tx_errors': stats.tx_errors,
                 'rx_frame_err': stats.rx_frame_err,
                 'rx_over_err': stats.rx_over_err,
                 'rx_crc_err': stats.rx_crc_err,
                 'collisions': stats.collisions,
                 'duration_sec': stats.duration_sec,
                 'duration_nsec': stats.duration_nsec}
            ports.append(s)
    ports = {str(dp.id): ports}
    return ports


def get_meter_stats(dp, waiters):
    stats = dp.ofproto_parser.OFPMeterStatsRequest(
        dp, 0, dp.ofproto.OFPM_ALL)
    msgs = []
    send_stats_request(dp, stats, waiters, msgs)

    meters = []
    for msg in msgs:
        for stats in msg.body:
            bands = []
            for band in stats.band_stats:
                b = {'packet_band_count': band.packet_band_count,
                     'byte_band_count': band.byte_band_count}
                bands.append(b)
            s = {'meter_id': UTIL.ofp_meter_to_user(stats.meter_id),
                 'len': stats.len,
                 'flow_count': stats.flow_count,
                 'packet_in_count': stats.packet_in_count,
                 'byte_in_count': stats.byte_in_count,
                 'duration_sec': stats.duration_sec,
                 'duration_nsec': stats.duration_nsec,
                 'band_stats': bands}
            meters.append(s)
    meters = {str(dp.id): meters}
    return meters


def get_meter_features(dp, waiters):

    ofp = dp.ofproto
    type_convert = {ofp.OFPMBT_DROP: 'DROP',
                    ofp.OFPMBT_DSCP_REMARK: 'DSCP_REMARK'}

    capa_convert = {ofp.OFPMF_KBPS: 'KBPS',
                    ofp.OFPMF_PKTPS: 'PKTPS',
                    ofp.OFPMF_BURST: 'BURST',
                    ofp.OFPMF_STATS: 'STATS'}

    stats = dp.ofproto_parser.OFPMeterFeaturesStatsRequest(dp, 0)
    msgs = []
    send_stats_request(dp, stats, waiters, msgs)

    features = []
    for msg in msgs:
        for feature in msg.body:
            band_types = []
            for k, v in type_convert.items():
                if (1 << k) & feature.band_types:
                    band_types.append(v)
            capabilities = []
            for k, v in sorted(capa_convert.items()):
                if k & feature.capabilities:
                    capabilities.append(v)
            f = {'max_meter': feature.max_meter,
                 'band_types': band_types,
                 'capabilities': capabilities,
                 'max_bands': feature.max_bands,
                 'max_color': feature.max_color}
            features.append(f)
    features = {str(dp.id): features}
    return features


def get_meter_config(dp, waiters):
    flags = {dp.ofproto.OFPMF_KBPS: 'KBPS',
             dp.ofproto.OFPMF_PKTPS: 'PKTPS',
             dp.ofproto.OFPMF_BURST: 'BURST',
             dp.ofproto.OFPMF_STATS: 'STATS'}

    band_type = {dp.ofproto.OFPMBT_DROP: 'DROP',
                 dp.ofproto.OFPMBT_DSCP_REMARK: 'DSCP_REMARK',
                 dp.ofproto.OFPMBT_EXPERIMENTER: 'EXPERIMENTER'}

    stats = dp.ofproto_parser.OFPMeterConfigStatsRequest(
        dp, 0, dp.ofproto.OFPM_ALL)
    msgs = []
    send_stats_request(dp, stats, waiters, msgs)

    configs = []
    for msg in msgs:
        for config in msg.body:
            bands = []
            for band in config.bands:
                b = {'type': band_type.get(band.type, ''),
                     'rate': band.rate,
                     'burst_size': band.burst_size}
                if band.type == dp.ofproto.OFPMBT_DSCP_REMARK:
                    b['prec_level'] = band.prec_level
                elif band.type == dp.ofproto.OFPMBT_EXPERIMENTER:
                    b['experimenter'] = band.experimenter
                bands.append(b)
            c_flags = []
            for k, v in sorted(flags.items()):
                if k & config.flags:
                    c_flags.append(v)
            c = {'flags': c_flags,
                 'meter_id': UTIL.ofp_meter_to_user(config.meter_id),
                 'bands': bands}
            configs.append(c)
    configs = {str(dp.id): configs}
    return configs


def get_group_stats(dp, waiters):
    stats = dp.ofproto_parser.OFPGroupStatsRequest(
        dp, 0, dp.ofproto.OFPG_ALL)
    msgs = []
    send_stats_request(dp, stats, waiters, msgs)

    groups = []
    for msg in msgs:
        for stats in msg.body:
            bucket_stats = []
            for bucket_stat in stats.bucket_stats:
                c = {'packet_count': bucket_stat.packet_count,
                     'byte_count': bucket_stat.byte_count}
                bucket_stats.append(c)
            g = {'length': stats.length,
                 'group_id': UTIL.ofp_group_to_user(stats.group_id),
                 'ref_count': stats.ref_count,
                 'packet_count': stats.packet_count,
                 'byte_count': stats.byte_count,
                 'duration_sec': stats.duration_sec,
                 'duration_nsec': stats.duration_nsec,
                 'bucket_stats': bucket_stats}
            groups.append(g)
    groups = {str(dp.id): groups}
    return groups


def get_group_features(dp, waiters):

    ofp = dp.ofproto
    type_convert = {ofp.OFPGT_ALL: 'ALL',
                    ofp.OFPGT_SELECT: 'SELECT',
                    ofp.OFPGT_INDIRECT: 'INDIRECT',
                    ofp.OFPGT_FF: 'FF'}
    cap_convert = {ofp.OFPGFC_SELECT_WEIGHT: 'SELECT_WEIGHT',
                   ofp.OFPGFC_SELECT_LIVENESS: 'SELECT_LIVENESS',
                   ofp.OFPGFC_CHAINING: 'CHAINING',
                   ofp.OFPGFC_CHAINING_CHECKS: 'CHAINING_CHECKS'}
    act_convert = {ofp.OFPAT_OUTPUT: 'OUTPUT',
                   ofp.OFPAT_COPY_TTL_OUT: 'COPY_TTL_OUT',
                   ofp.OFPAT_COPY_TTL_IN: 'COPY_TTL_IN',
                   ofp.OFPAT_SET_MPLS_TTL: 'SET_MPLS_TTL',
                   ofp.OFPAT_DEC_MPLS_TTL: 'DEC_MPLS_TTL',
                   ofp.OFPAT_PUSH_VLAN: 'PUSH_VLAN',
                   ofp.OFPAT_POP_VLAN: 'POP_VLAN',
                   ofp.OFPAT_PUSH_MPLS: 'PUSH_MPLS',
                   ofp.OFPAT_POP_MPLS: 'POP_MPLS',
                   ofp.OFPAT_SET_QUEUE: 'SET_QUEUE',
                   ofp.OFPAT_GROUP: 'GROUP',
                   ofp.OFPAT_SET_NW_TTL: 'SET_NW_TTL',
                   ofp.OFPAT_DEC_NW_TTL: 'DEC_NW_TTL',
                   ofp.OFPAT_SET_FIELD: 'SET_FIELD',
                   ofp.OFPAT_PUSH_PBB: 'PUSH_PBB',
                   ofp.OFPAT_POP_PBB: 'POP_PBB'}

    stats = dp.ofproto_parser.OFPGroupFeaturesStatsRequest(dp, 0)
    msgs = []
    send_stats_request(dp, stats, waiters, msgs)

    features = []
    for msg in msgs:
        feature = msg.body
        types = []
        for k, v in type_convert.items():
            if (1 << k) & feature.types:
                types.append(v)
        capabilities = []
        for k, v in cap_convert.items():
            if k & feature.capabilities:
                capabilities.append(v)
        max_groups = []
        for k, v in type_convert.items():
            max_groups.append({v: feature.max_groups[k]})
        actions = []
        for k1, v1 in type_convert.items():
            acts = []
            for k2, v2 in act_convert.items():
                if (1 << k2) & feature.actions[k1]:
                    acts.append(v2)
            actions.append({v1: acts})
        f = {'types': types,
             'capabilities': capabilities,
             'max_groups': max_groups,
             'actions': actions}
        features.append(f)
    features = {str(dp.id): features}
    return features


def get_group_desc(dp, waiters):

    type_convert = {dp.ofproto.OFPGT_ALL: 'ALL',
                    dp.ofproto.OFPGT_SELECT: 'SELECT',
                    dp.ofproto.OFPGT_INDIRECT: 'INDIRECT',
                    dp.ofproto.OFPGT_FF: 'FF'}

    stats = dp.ofproto_parser.OFPGroupDescStatsRequest(dp, 0)
    msgs = []
    send_stats_request(dp, stats, waiters, msgs)

    descs = []
    for msg in msgs:
        for stats in msg.body:
            buckets = []
            for bucket in stats.buckets:
                actions = []
                for action in bucket.actions:
                    actions.append(action_to_str(action))
                b = {'weight': bucket.weight,
                     'watch_port': bucket.watch_port,
                     'watch_group': bucket.watch_group,
                     'actions': actions}
                buckets.append(b)
            d = {'type': type_convert.get(stats.type),
                 'group_id': UTIL.ofp_group_to_user(stats.group_id),
                 'buckets': buckets}
            descs.append(d)
    descs = {str(dp.id): descs}
    return descs


def get_port_desc(dp, waiters):

    stats = dp.ofproto_parser.OFPPortDescStatsRequest(dp, 0)
    msgs = []
    send_stats_request(dp, stats, waiters, msgs)

    descs = []

    for msg in msgs:
        stats = msg.body
        for stat in stats:
            d = {'port_no': UTIL.ofp_port_to_user(stat.port_no),
                 'hw_addr': stat.hw_addr,
                 'name': stat.name.decode('utf-8'),
                 'config': stat.config,
                 'state': stat.state,
                 'curr': stat.curr,
                 'advertised': stat.advertised,
                 'supported': stat.supported,
                 'peer': stat.peer,
                 'curr_speed': stat.curr_speed,
                 'max_speed': stat.max_speed}
            descs.append(d)
    descs = {str(dp.id): descs}
    return descs


def mod_flow_entry(dp, flow, cmd):
    cookie = int(flow.get('cookie', 0))
    cookie_mask = int(flow.get('cookie_mask', 0))
    table_id = UTIL.ofp_table_from_user(flow.get('table_id', 0))
    idle_timeout = int(flow.get('idle_timeout', 0))
    hard_timeout = int(flow.get('hard_timeout', 0))
    priority = int(flow.get('priority', 0))
    buffer_id = UTIL.ofp_buffer_from_user(
        flow.get('buffer_id', dp.ofproto.OFP_NO_BUFFER))
    out_port = UTIL.ofp_port_from_user(
        flow.get('out_port', dp.ofproto.OFPP_ANY))
    out_group = UTIL.ofp_group_from_user(
        flow.get('out_group', dp.ofproto.OFPG_ANY))
    flags = int(flow.get('flags', 0))
    match = to_match(dp, flow.get('match', {}))
    inst = to_actions(dp, flow.get('actions', []))

    flow_mod = dp.ofproto_parser.OFPFlowMod(
        dp, cookie, cookie_mask, table_id, cmd, idle_timeout,
        hard_timeout, priority, buffer_id, out_port, out_group,
        flags, match, inst)

    dp.send_msg(flow_mod)


def mod_meter_entry(dp, meter, cmd):

    flags_convert = {'KBPS': dp.ofproto.OFPMF_KBPS,
                     'PKTPS': dp.ofproto.OFPMF_PKTPS,
                     'BURST': dp.ofproto.OFPMF_BURST,
                     'STATS': dp.ofproto.OFPMF_STATS}

    flags = 0
    if 'flags' in meter:
        meter_flags = meter['flags']
        if not isinstance(meter_flags, list):
            meter_flags = [meter_flags]
        for flag in meter_flags:
            if flag not in flags_convert:
                LOG.error('Unknown meter flag: %s', flag)
                continue
            flags |= flags_convert.get(flag)

    meter_id = UTIL.ofp_meter_from_user(meter.get('meter_id', 0))

    bands = []
    for band in meter.get('bands', []):
        band_type = band.get('type')
        rate = int(band.get('rate', 0))
        burst_size = int(band.get('burst_size', 0))
        if band_type == 'DROP':
            bands.append(
                dp.ofproto_parser.OFPMeterBandDrop(rate, burst_size))
        elif band_type == 'DSCP_REMARK':
            prec_level = int(band.get('prec_level', 0))
            bands.append(
                dp.ofproto_parser.OFPMeterBandDscpRemark(
                    rate, burst_size, prec_level))
        elif band_type == 'EXPERIMENTER':
            experimenter = int(band.get('experimenter', 0))
            bands.append(
                dp.ofproto_parser.OFPMeterBandExperimenter(
                    rate, burst_size, experimenter))
        else:
            LOG.error('Unknown band type: %s', band_type)

    meter_mod = dp.ofproto_parser.OFPMeterMod(
        dp, cmd, flags, meter_id, bands)

    dp.send_msg(meter_mod)


def mod_group_entry(dp, group, cmd):

    type_convert = {'ALL': dp.ofproto.OFPGT_ALL,
                    'SELECT': dp.ofproto.OFPGT_SELECT,
                    'INDIRECT': dp.ofproto.OFPGT_INDIRECT,
                    'FF': dp.ofproto.OFPGT_FF}

    type_ = type_convert.get(group.get('type', 'ALL'))
    if type_ is None:
        LOG.error('Unknown group type: %s', group.get('type'))

    group_id = UTIL.ofp_group_from_user(group.get('group_id', 0))

    buckets = []
    for bucket in group.get('buckets', []):
        weight = int(bucket.get('weight', 0))
        watch_port = int(bucket.get('watch_port', dp.ofproto.OFPP_ANY))
        watch_group = int(bucket.get('watch_group', dp.ofproto.OFPG_ANY))
        actions = []
        for dic in bucket.get('actions', []):
            action = to_action(dp, dic)
            if action is not None:
                actions.append(action)
        buckets.append(dp.ofproto_parser.OFPBucket(
            weight, watch_port, watch_group, actions))

    group_mod = dp.ofproto_parser.OFPGroupMod(
        dp, cmd, type_, group_id, buckets)

    dp.send_msg(group_mod)


def mod_port_behavior(dp, port_config):
    port_no = UTIL.ofp_port_from_user(port_config.get('port_no', 0))
    hw_addr = str(port_config.get('hw_addr'))
    config = int(port_config.get('config', 0))
    mask = int(port_config.get('mask', 0))
    advertise = int(port_config.get('advertise'))

    port_mod = dp.ofproto_parser.OFPPortMod(
        dp, port_no, hw_addr, config, mask, advertise)

    dp.send_msg(port_mod)


def send_experimenter(dp, exp):
    experimenter = exp.get('experimenter', 0)
    exp_type = exp.get('exp_type', 0)
    data_type = exp.get('data_type', 'ascii')
    if data_type != 'ascii' and data_type != 'base64':
        LOG.error('Unknown data type: %s', data_type)
    data = exp.get('data', '')
    if data_type == 'base64':
        data = base64.b64decode(data)

    expmsg = dp.ofproto_parser.OFPExperimenter(
        dp, experimenter, exp_type, data)

    dp.send_msg(expmsg)
