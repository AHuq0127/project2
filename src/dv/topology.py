# src/dv/topology.py
import math

def parse_topology(filepath):
    with open(filepath, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]

    num_servers = int(lines[0])
    num_neighbors = int(lines[1])

    servers = {}
    for i in range(2, 2 + num_servers):
        sid, ip, port = lines[i].split()
        servers[int(sid)] = (ip, int(port))

    links = []
    for line in lines[2 + num_servers:]:
        s1, s2, cost = line.split()
        links.append((int(s1), int(s2), int(cost)))

    return {
        "num_servers": num_servers,
        "num_neighbors": num_neighbors,
        "servers": servers,
        "links": links
    }

def build_routing_table(topology_data, current_id):
    routing_table = {}
    servers = topology_data["servers"]
    links = topology_data["links"]

    # initialize
    for sid in servers:
        routing_table[sid] = {
            "next_hop": None,
            "cost": math.inf
        }

    # cost to self
    routing_table[current_id] = {"next_hop": current_id, "cost": 0}

    # add direct neighbors
    for s1, s2, cost in links:
        if s1 == current_id:
            routing_table[s2] = {"next_hop": s2, "cost": cost}
        elif s2 == current_id:
            routing_table[s1] = {"next_hop": s1, "cost": cost}

    return routing_table
