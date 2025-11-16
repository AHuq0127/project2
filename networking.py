# networking.py
# Handles sending and receiving distance vector messages between servers

import socket
import threading
import time
import json



def create_udp_socket(ip, port, timeout=1.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((ip, port))
    s.settimeout(timeout)
    return s

def send_udp_packet(sock, addr, packet):
    """packet is a Python dict; we JSON encode it here"""
    try:
        data = json.dumps(packet).encode('utf-8')
        sock.sendto(data, addr)
    except Exception as e:
        print("send_udp_packet error:", e)


class Network:
    def __init__(self, server_id, server_ip, server_port, interval, neighbors):
        self.server_id = server_id
        self.server_ip = server_ip
        self.server_port = server_port
        self.interval = interval
        self.neighbors = neighbors    # dict: {neighbor_id: (ip, port, cost)}
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.server_ip, self.server_port))
        self.running = True
        self.update_count = 0

    # function to send updates to neighbors periodically
    def start_updates(self, get_distance_vector):
        def send_loop():
            while self.running:
                msg = get_distance_vector()
                data = msg.encode()
                for nid, info in self.neighbors.items():
                    ip, port, cost = info
                    if cost != float('inf'):
                        self.sock.sendto(data, (ip, port))
                time.sleep(self.interval)
        t = threading.Thread(target=send_loop, daemon=True)
        t.start()

    # function to listen for incoming packets
    def start_listener(self, handle_update):
        def listen_loop():
            while self.running:
                try:
                    data, addr = self.sock.recvfrom(1024)
                    message = data.decode()
                    self.update_count += 1
                    handle_update(message, addr)
                except:
                    break
        t = threading.Thread(target=listen_loop, daemon=True)
        t.start()

    # send one-time update (used by 'step' command)
    def send_step(self, msg):
        data = msg.encode()
        for nid, info in self.neighbors.items():
            ip, port, cost = info
            if cost != float('inf'):
                self.sock.sendto(data, (ip, port))
        print("step SUCCESS")

    # show how many packets were received
    def show_packets(self):
        print(f"packets SUCCESS")
        print(f"Number of received distance vectors: {self.update_count}")
        self.update_count = 0

    # disable a link to a neighbor (set cost to infinity)
    def disable(self, neighbor_id):
        if neighbor_id in self.neighbors:
            ip, port, _ = self.neighbors[neighbor_id]
            self.neighbors[neighbor_id] = (ip, port, float('inf'))
            print("disable SUCCESS")
        else:
            print("disable ERROR invalid server ID")

    # stop server to simulate crash
    def crash(self):
        self.running = False
        self.sock.close()
        print("crash SUCCESS")
