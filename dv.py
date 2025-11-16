#!/usr/bin/env python3
"""
Main entry point for Distance Vector Routing project.
"""

import sys   
import argparse
from dv_core import DVServer


def main():
    parser = argparse.ArgumentParser(description="Distance Vector Routing Server")
    parser.add_argument("-t", "--topology", required=True,
                        help="Path to the topology file")
    parser.add_argument("-i", "--interval", required=True, type=float,
                        help="Update interval in seconds")

    args = parser.parse_args()

    topo = args.topology
    interval = args.interval

    # Create DV server
    server = DVServer(topo, interval)

    # Start server (listener + timer + command loop)
    server.start()

if __name__ == "__main__":
    main()
