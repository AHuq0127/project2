from json.encoder import INFINITY
import sys


def c_loop(self):
        while True:
            try:
                line = input().strip()
            except EOFError:
                break
            if not line:
                continue
            parts = line.split()
            c = parts[0].lower()
            if c == "Update":
                self.c_update(parts)
            elif c == "Step":
                self.c_step()
            elif c == "Packet":
                self.c_packets()
            elif c == "Display":
                self.c_display()
            elif c == "Disable":
                self.c_disable(parts)
            elif c == "Crash":
                self.c_crash()
                return
            else:
                print(f"***{line} ERROR! Unknown command!***")

def c_update(self, p):
        c_str = " ".join(p)
        if len(p) != 4:
            print(f"***{c_str} ERROR! Invalid argument!***")
            return
        try:
            a = int(p[1]); b = int(p[2]); c_raw = p[3]
        except Exception:
            print(f"***{c_str} ERROR! Invalid server IDs!***")
            return
        n_cost = INFINITY if c_raw.lower() == "inf" else int(c_raw)
        # Only servers a and b should receive this command; each side modifies its own view.
        # Modify the link cost just for that neighbor if this server is either an or b.
        if self.local_id not in (a, b):
            print(f"***{c_str} ERROR! Non-command not applicable to the server!***")
            return
        n_id = b if self.local_id == a else a
        with self.lock:
            if n_id not in self.neighbors:
                print(f"***{c_str} ERROR! Not a neighbor!***")
                return
            # Neighbor link 
            self.neighbors[n_id]['cost'] = n_cost
            # It updates routing table for entry per neighbor
            if self.routing_table.get(n_id) is None:
                self.routing_table[n_id] = {"The next hop": n_id if n_cost != INFINITY else None, "The cost": n_cost}
            else:
                self.routing_table[n_id]['cost'] = n_cost
                self.routing_table[n_id]['next_hop'] = n_id if n_cost != INFINITY else None
        print(f"The {c_str} was a SUCCESS!")

def c_step(self):
        m = self._serialize_distance_vector()
        with self.lock:
            n_copy = dict(self.neighbors)
        for nid, info in n_copy.items():
            if info['cost'] == INFINITY:
                continue
            self.net.send(m, info['addr'])
        print("The step was a SUCCESS")

def c_packet(self):
        with self.lock:
            c = self.recv_count
            self.recv_count = 0
        print("The packets was a SUCCESS!")
        print(f"The # of received distance vectors: {c}")

def c_display(self):
        # It shows sorted per Destination ID: "<dest> <next-hop> <cost>"
        with self.lock:
            k = sorted(self.routing_table.keys())
            print("***The display was a SUCCESS!***")
            for d in k:
                e = self.routing_table[d]
                nh = e["next_hop"] if e["next_hop"] is not None else "-"
                cost = "inf" if e["cost"] == INFINITY else str(int(e["cost"]))
                print(f"{d} {nh} {cost}")

def c_disable(self, parts):
        cmd_str = " ".join(parts)
        if len(parts) != 2:
            print(f"***{cmd_str} ERROR! Invalid argument!")
            return
        try:
            nid = int(parts[1])
        except Exception:
            print(f"{cmd_str} ERROR! Invalid server ID!")
            return
        with self.lock:
            if nid not in self.neighbors:
                print(f"{cmd_str} ERROR! Invalid server ID!")
                return
            ip, port = self.neighbors[nid]['addr']
            self.neighbors[nid]['cost'] = INFINITY
            # It updates the routing table neighbor input
            if self.routing_table.get(nid):
                self.routing_table[nid]['cost'] = INFINITY
                self.routing_table[nid]['next_hop'] = None
        print("The disable feature was a SUCCESS!")

def c_crash(self):
        # It closes the sockets and mark running to false
        self.net.close()
        with self.lock:
            self.running = False
        print("The crash was a SUCCESS!")
        # After crash, it will exit out the process
        sys.exit(0)