"""One module per command family. Importing a module registers its parsers."""

from fabric_weft.parsers import interfaces, ip, isid, isis, lldp, mlt, system, vlan

__all__ = ["interfaces", "ip", "isid", "isis", "lldp", "mlt", "system", "vlan"]
