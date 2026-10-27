#!/usr/bin/env python3
"""Top-level convenience entrypoint for VeriPulse Simulated Siemens S7-1500 PLC Server."""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from plc_bridge.simulated_plc_server import main

if __name__ == "__main__":
    main()
