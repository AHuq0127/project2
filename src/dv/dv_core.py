#!/usr/bin/env python3
"""
Core Distance Vector server implementation (DVServer class).

This module contains the DVServer class (moved from the original `dv.py`). It
keeps the original behavior but delegates low-level socket sends to
`networking.send_udp_packet` and socket creation to `networking.create_udp_socket`.
"""

import threading
import time
import json
import sys
import socket
from typing import Dict

import networking

INF = float('inf')

lock = threading.Lock()


def now_str():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


class DVServer:
    def __init__(self, topology_file, interval):
        self.topology_file = topology_file
        self.interval = float(interval)
        # parsed from topology file
        # SERVERS: id -> {"ip":..,"port":..}
        self.SERVERS: Dict[int, Dict] = {}
        # neighbors costs: neighbor_id -> cost (bidirectional assumed)
        self.NEIGHBORS = {}
        # neighbor addresses: neighbor_id -> (ip,port)
        self.NEIGHBOR_ADDR = {}
        # Track last received update time per neighbor for timeout detection
        self.last_recv = {}
        # packet received counter
        self.packets_received = 0
        # alive flag
        self.running = True
        # load topology and initialize
        self._read_topology()
        # initialize UDP socket bound to our address/port
        self.sock = networking.create_udp_socket(self.MY_IP, self.MY_PORT, timeout=1.0)
        # Routing table
        # ROUTING_TABLE: dest_id -> {"next_hop": id or None, "cost": cost, "ip": ip, "port": port}
        self.ROUTING_TABLE = {}
        for sid, sinfo in self.SERVERS.items():
            if sid == self.MY_ID:
                self.ROUTING_TABLE[sid] = {"next_hop": sid, "cost": 0, "ip": sinfo['ip'], "port": sinfo['port']}
            elif sid in self.NEIGHBORS:
                self.ROUTING_TABLE[sid] = {"next_hop": sid, "cost": float(self.NEIGHBORS[sid]), "ip": sinfo['ip'], "port": sinfo['port']}
            else:
                self.ROUTING_TABLE[sid] = {"next_hop": None, "cost": INF, "ip": sinfo['ip'], "port": sinfo['port']}
        # thread for listening
        self.listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        # thread for periodic updates
        self.timer_thread = threading.Thread(target=self._timer_loop, daemon=True)

    def _read_topology(self):
        with open(self.topology_file, 'r') as f:
            lines = [ln.strip() for ln in f.readlines() if ln.strip() and not ln.strip().startswith('#')]
        if len(lines) < 3:
            print("Topology file too short.", file=sys.stderr); sys.exit(1)
        num_servers = int(lines[0].split()[0])
        num_neighbors = int(lines[1].split()[0])
        # parse server entries
        idx = 2
        for _ in range(num_servers):
            parts = lines[idx].split()
            sid = int(parts[0])
            ip = parts[1]
            port = int(parts[2])
            self.SERVERS[sid] = {"ip": ip, "port": port}
            idx += 1
        # parse neighbor cost lines (edges)
        for _ in range(num_neighbors):
            parts = lines[idx].split()
            a = int(parts[0]); b = int(parts[1])
            cost_raw = parts[2]
            cost = INF if cost_raw.lower() in ('inf', 'infty', 'infinity') else int(cost_raw)
            if not hasattr(self, '_edges'): self._edges = []
            self._edges.append((a,b,cost))
            idx += 1
        # determine my server id by matching local IP against server entries
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        except Exception:
            local_ip = "127.0.0.1"
        finally:
            s.close()
        candidate = None
        for sid, sinfo in self.SERVERS.items():
            if sinfo['ip'] == local_ip:
                candidate = sid
                break
        if candidate is None:
            for sid, sinfo in self.SERVERS.items():
                if sinfo['ip'] == '127.0.0.1' and local_ip.startswith('127.'):
                    candidate = sid
                    break
        if candidate is None:
            candidate = next(iter(self.SERVERS.keys()))
        try:
            manual_id = int(input("Enter server ID (1-4) for this instance: ").strip())
            if manual_id in self.SERVERS:candidate = manual_id
        except Exception:
            pass
        self.MY_ID = candidate
        self.MY_IP = self.SERVERS[self.MY_ID]['ip']
        self.MY_PORT = self.SERVERS[self.MY_ID]['port']
        # Build neighbor lists from edges where one endpoint is MY_ID
        for (a,b,cost) in getattr(self, '_edges', []):
            if a == self.MY_ID:
                self.NEIGHBORS[b] = cost
            elif b == self.MY_ID:
                self.NEIGHBORS[a] = cost
        # build neighbor addr map
        for nid in list(self.NEIGHBORS.keys()):
            if nid in self.SERVERS:
                self.NEIGHBOR_ADDR[nid] = (self.SERVERS[nid]['ip'], self.SERVERS[nid]['port'])
                self.last_recv[nid] = 0.0

    def start(self):
        print(f"SERVER STARTED: id={self.MY_ID} ip={self.MY_IP} port={self.MY_PORT} interval={self.interval}")
        self.listener_thread.start()
        self.timer_thread.start()
        try:
            while self.running:
                cmd = input().strip()
                if not cmd: continue
                self._handle_command(cmd)
        except (KeyboardInterrupt, EOFError):
            print("Shutting down (Keyboard/EOF)")
            self.running = False
        finally:
            try:
                self.sock.close()
            except Exception:
                pass

    def _listen_loop(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(65536)
            except socket.timeout:
                # do periodic neighbor timeout checks
                self._check_neighbor_timeouts()
                continue
            except Exception as e:
                if self.running:
                    print("Listener socket error:", e, file=sys.stderr)
                break
            try:
                packet = json.loads(data.decode('utf-8'))
            except Exception:
                print("Received unparsable packet from", addr)
                continue
            sender_id = packet.get('sender_id')
            with lock:
                self.packets_received += 1
                self.last_recv[sender_id] = time.time()
            print(f"RECEIVED A MESSAGE FROM SERVER {sender_id}")
            # process entries and apply Bellman-Ford update
            updated = False
            sender_cost_to_sender = self.ROUTING_TABLE.get(sender_id, {}).get('cost', INF)
            # If sender is a neighbor with direct cost, use that for cost_to_sender
            direct = self.NEIGHBORS.get(sender_id, INF)
            cost_to_sender = direct if direct != INF else sender_cost_to_sender
            entries = packet.get('entries', [])
            with lock:
                for e in entries:
                    dest = int(e['id'])
                    recv_cost = float(e['cost']) if e['cost'] != "inf" else INF
                    # skip if dest is this server
                    if dest == self.MY_ID:
                        continue
                    new_cost = INF if cost_to_sender == INF or recv_cost == INF else cost_to_sender + recv_cost
                    cur = self.ROUTING_TABLE.get(dest, {"cost": INF})
                    cur_cost = cur['cost']
                    # Bellman-Ford relaxation: if new_cost < cur_cost, update route via sender
                    if new_cost < cur_cost:
                        self.ROUTING_TABLE[dest]['cost'] = new_cost
                        self.ROUTING_TABLE[dest]['next_hop'] = sender_id
                        updated = True
                # Also ensure that direct neighbor entries reflect current neighbor costs
                for nid, ncost in self.NEIGHBORS.items():
                    if self.ROUTING_TABLE[nid]['cost'] != ncost:
                        self.ROUTING_TABLE[nid]['cost'] = float(ncost)
                        self.ROUTING_TABLE[nid]['next_hop'] = nid
                        updated = True

    def _timer_loop(self):
        # send initial update immediately then every interval
        next_time = time.time()
        while self.running:
            now = time.time()
            if now >= next_time:
                self.send_updates()
                next_time = now + self.interval
            time.sleep(0.1)
            # also check neighbor timeouts frequently
            self._check_neighbor_timeouts()

    def send_updates(self):
        # prepare packet with number of update fields and list of entries (id,cost,ip,port)
        entries = []
        with lock:
            for dest_id, info in self.ROUTING_TABLE.items():
                c = info['cost']
                entries.append({"id": dest_id, "ip": info['ip'], "port": info['port'], "cost": ("inf" if c==INF else int(c))})
        packet = {
            "sender_id": self.MY_ID,
            "sender_ip": self.MY_IP,
            "sender_port": self.MY_PORT,
            "entries": entries
        }
        # send only to neighbors
        for nid, addr in self.NEIGHBOR_ADDR.items():
            try:
                networking.send_udp_packet(self.sock, addr, packet)
            except Exception as e:
                print("Error sending update to", nid, addr, e)

    def _handle_command(self, cmd_str):
        parts = cmd_str.split()
        cmd = parts[0].lower()
        if cmd == "update":
            # update <server-ID1> <server-ID2> <Link Cost>
            if len(parts) != 4:
                print(f"{cmd_str} ERROR: wrong arguments")
                return
            a = int(parts[1]); b = int(parts[2]); cost_raw = parts[3]
            cost = INF if cost_raw.lower() in ('inf','infty','infinity') else int(cost_raw)
            if self.MY_ID not in (a,b):
                print(f"{cmd_str} ERROR: this update does not involve this server")
                return
            other = b if a==self.MY_ID else a
            if other not in self.NEIGHBORS:
                print(f"{cmd_str} ERROR: server {other} is not a neighbor")
                return
            with lock:
                self.NEIGHBORS[other] = cost
                if cost == INF:
                    self.ROUTING_TABLE[other]['cost'] = INF
                    self.ROUTING_TABLE[other]['next_hop'] = None
                else:
                    self.ROUTING_TABLE[other]['cost'] = cost
                    self.ROUTING_TABLE[other]['next_hop'] = other
            print(f"{cmd_str} SUCCESS")
        elif cmd == "step":
            # send routing update to neighbors right away
            self.send_updates()
            print(f"{cmd_str} SUCCESS")
        elif cmd == "packets":
            with lock:
                cnt = self.packets_received
                self.packets_received = 0
            print(f"{cmd_str} SUCCESS")
            print(cnt)
        elif cmd == "display":
            # Display the current routing table sorted by destination ID increasing
            with lock:
                items = sorted(self.ROUTING_TABLE.items(), key=lambda x: x[0])
            print(f"{cmd_str} SUCCESS")
            for dest, info in items:
                nh = info['next_hop'] if info['next_hop'] is not None else "-"
                cost = "inf" if info['cost']==INF else int(info['cost'])
                print(f"{dest} {nh} {cost}")
        elif cmd == "disable":
            # disable <server-ID> : set link to given server to infinity (only if neighbor)
            if len(parts) != 2:
                print(f"{cmd_str} ERROR: wrong arguments")
                return
            nid = int(parts[1])
            if nid not in self.NEIGHBORS:
                print(f"{cmd_str} ERROR: server {nid} is not a neighbor")
                return
            with lock:
                self.NEIGHBORS[nid] = INF
                self.ROUTING_TABLE[nid]['cost'] = INF
                self.ROUTING_TABLE[nid]['next_hop'] = None
            print(f"{cmd_str} SUCCESS")
        elif cmd == "crash":
            # close all connections and stop running
            with lock:
                self.running = False
            print(f"{cmd_str} SUCCESS")
            # close socket to break listener loop
            try:
                self.sock.close()
            except:
                pass
            # exit program
            sys.exit(0)
        else:
            print(f"{cmd_str} ERROR: unknown command")

    def _check_neighbor_timeouts(self):
        # if neighbor hasn't sent updates for 3 consecutive update intervals, assume it's gone and set link cost to infinity
        with lock:
            t = time.time()
            for nid in list(self.last_recv.keys()):
                last = self.last_recv.get(nid, 0)
                if last == 0: continue
                if t - last > 3 * self.interval and self.NEIGHBORS.get(nid, INF) != INF:
                    self.NEIGHBORS[nid] = INF
                    if self.ROUTING_TABLE[nid]['cost'] != INF:
                        self.ROUTING_TABLE[nid]['cost'] = INF
                        self.ROUTING_TABLE[nid]['next_hop'] = None
                        # we do not immediately send update (assignment specifies periodic or step), but routing table changed.
                        print(f"[TIMEOUT] neighbor {nid} timed out; set cost to infinity")
