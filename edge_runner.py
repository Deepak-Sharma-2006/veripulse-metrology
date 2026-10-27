#!/usr/bin/env python3
"""Top-level convenience entrypoint for VeriPulse G-API Edge Vision Runner."""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from edge_vision.edge_runner import main

if __name__ == "__main__":
    main()
