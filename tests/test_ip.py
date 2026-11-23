from __future__ import annotations

from fabric_weft import parse_arp_entries, parse_ip_routes

ROUTES = """\
                                                IP Route - VRF blue
========================================================================================================================
                                                     NH                      INTER
DST             MASK            NEXT                 VRF/ISID         COST   FACE     PROT   AGE TYPE   PRF ACCESS
------------------------------------------------------------------------------------------------------------------------
10.100.4.0      255.255.255.0   fe-04                blue             20     4051     ISIS   0   IBSV   7   Trusted
10.100.5.0      255.255.0.0     10.100.3.1           -                1      103      LOC    0   DB     0   Trusted
"""


def test_route_prefix_is_checked_and_vrf_comes_from_the_title() -> None:
    result = parse_ip_routes(ROUTES)
    (route,) = result.records
    assert (route.vrf, route.prefix, route.next_hop) == ("blue", "10.100.4.0/24", "fe-04")
    # 10.100.5.0/16 has host bits set: reported, not silently turned into 10.100.0.0/16
    assert result.skipped[0].reason.endswith("has host bits set")


ARP = """\
========================================================================================================================
                                                 IP Arp - GlobalRouter
========================================================================================================================
IP_ADDRESS      MAC_ADDRESS        VLAN  PORT                 TYPE    TTL(10 Sec) TUNNEL             L3 ACCESS
------------------------------------------------------------------------------------------------------------------------
10.10.10.14     00:50:79:66:68:01  10    1/2                  DYNAMIC 2149        fe-04              GlobalRouter
10.255.0.3      00:00:00:00:00:01  -     -                    LOCAL   2160                           GlobalRouter
"""


def test_arp_ttl_is_in_seconds_and_placeholders_are_none() -> None:
    remote, clip = parse_arp_entries(ARP, strict=True)
    assert (remote.ttl_seconds, remote.tunnel, remote.port) == (21490, "fe-04", "1/2")
    assert (clip.vlan_id, clip.port, clip.tunnel) == (None, None, None)
