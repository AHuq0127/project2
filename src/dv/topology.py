"""
topology.py
------------
Role D: Topology & Tests
• Parses a topology file.
• Builds the initial routing table for a given server.
• Provides a display helper that prints the table
  in the same format expected by Role C (CLI & Commands).
"""

import math
import os
from pprint import pprint


# -------------------------------------------------------------
# Parse the topology file
# -------------------------------------------------------------
def parse_topology(filepath: str):
    """
    Reads a topology.txt file and returns its structure as a dict.
    Format:
        <num-servers>
        <num-neighbors>
        <server-ID> <server-IP> <server-port>
        ...
        <server-ID1> <server-ID2> <cost>
    Lines starting with '#' are ignored.
    """
    with open(filepath, "r") as f:
        # Remove blank lines and comment lines
        lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    if len(lines) < 2:
        raise ValueError("Topology file must have at least 2 lines (num_servers and num_neighbors)")

    num_servers = int(lines[0])
    num_neighbors = int(lines[1])

    # --- Server information ---
    servers = {}
    for i in range(2, 2 + num_servers):
        sid, ip, port = lines[i].split()
        servers[int(sid)] = (ip, int(port))

    # --- Link (edge) information ---
    links = []
    for line in lines[2 + num_servers:]:
        s1, s2, cost = line.split()
        links.append((int(s1), int(s2), int(cost)))

    return {
        "num_servers": num_servers,
        "num_neighbors": num_neighbors,
        "servers": servers,
        "links": links,
    }


# -------------------------------------------------------------
# Build the initial routing table
# -------------------------------------------------------------
def build_routing_table(topology_data: dict, current_id: int):
    """
    Initializes the routing table for the given server.
    Each entry looks like:
        { destination_id: { "next_hop": X, "cost": Y } }
    """
    routing_table = {}
    servers = topology_data["servers"]
    links = topology_data["links"]

    # Default values: cost = ∞, next_hop = None
    for sid in servers:
        routing_table[sid] = {"next_hop": None, "cost": math.inf}

    # Cost to self
    routing_table[current_id] = {"next_hop": current_id, "cost": 0}

    # Direct neighbors from the link list
    for s1, s2, cost in links:
        if s1 == current_id:
            routing_table[s2] = {"next_hop": s2, "cost": cost}
        elif s2 == current_id:
            routing_table[s1] = {"next_hop": s1, "cost": cost}

    return routing_table


# -------------------------------------------------------------
# Display routing table (Role C compatible format)
# -------------------------------------------------------------
def display_routing_table(routing_table: dict):
    """
    Prints routing table entries in sorted order:
        <destination-ID> <next-hop-ID> <cost>
    """
    for dest in sorted(routing_table.keys()):
        entry = routing_table[dest]
        nh = entry["next_hop"] if entry["next_hop"] is not None else "-"
        cost = int(entry["cost"]) if entry["cost"] != math.inf else "inf"
        print(f"{dest} {nh} {cost}")


# -------------------------------------------------------------
# Local test runner (for your own verification)
# -------------------------------------------------------------
if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    topo_path = os.path.join(base_dir, "topologies", "sample_topology.txt")

    print(f"Reading topology file from: {topo_path}\n")
    topo = parse_topology(topo_path)
    print("Parsed topology:")
    pprint(topo)

    current_server_id = 1
    print(f"\nInitial routing table for server {current_server_id}:")
    table = build_routing_table(topo, current_server_id)

    # Pretty internal dict view
    pprint(table)

    print("\nDisplay format (matches CLI 'display' command):")
    display_routing_table(table)
