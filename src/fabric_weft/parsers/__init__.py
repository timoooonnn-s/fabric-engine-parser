"""One module per command family. Importing a module registers its parsers."""

from fabric_weft.parsers import interfaces, isid, lldp, mlt, vlan

__all__ = ["interfaces", "isid", "lldp", "mlt", "vlan"]
