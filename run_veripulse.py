#!/usr/bin/env python3
"""
VeriPulse Unified Multi-Process Orchestrator
============================================
Single-command supervision engine managing all background cyber-physical and cloud services:
  1. Simulated PLC Server (Siemens S7-1500 Modbus TCP on port 5020)
  2. Synthetic Streamer (120 FPS high-speed battery foil rendering into SHM)
  3. Edge Vision Engine (G-API & FFT reflex loop with sub-pixel metrology)
  4. SHM WebSocket Gateway (High-throughput IPC gateway on ws://localhost:8765)
  5. COOL Metrology Microservice (Arm KleidiCV accelerated FastAPI on port 8000)
  6. Bedrock Autonomous Agent (Claude 3.5 Sonnet supervisory closed-loop healer)

Includes:
  - Healthcheck port listener validation
  - Structured multi-process lifecycle supervision
  - Graceful SIGINT / SIGTERM shutdown and shared memory cleanup
"""

import os
import sys
import time
import socket
import signal
import threading
import subprocess
import argparse
import logging
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [ORCHESTRATOR] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("VeriPulseOrchestrator")

# Terminal color codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"


class ManagedService:
    def __init__(
        self,
        name: str,
        cmd: List[str],
        port: Optional[int] = None,
        host: str = "127.0.0.1",
        color: str = CYAN,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        startup_wait_sec: float = 1.0,
    ):
        self.name = name
        self.cmd = cmd
        self.port = port
        self.host = host
        self.color = color
        self.cwd = cwd or PROJECT_ROOT
        self.env = env
        self.startup_wait_sec = startup_wait_sec
        self.proc: Optional[subprocess.Popen] = None
        self.thread: Optional[threading.Thread] = None
        self.is_alive = False

    def start(self):
        full_env = os.environ.copy()
        if self.env:
            full_env.update(self.env)
        # Ensure project root is in PYTHONPATH
        py_path = full_env.get("PYTHONPATH", "")
        full_env["PYTHONPATH"] = (
            f"{PROJECT_ROOT}{os.pathsep}{py_path}" if py_path else PROJECT_ROOT
        )

        logger.info(
            "Launching service %s%s%s (cmd: %s)",
            self.color + BOLD,
            self.name,
            RESET,
            " ".join(self.cmd),
        )
        self.proc = subprocess.Popen(
            self.cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=self.cwd,
            env=full_env,
            text=True,
            bufsize=1,
        )
        self.is_alive = True
        self.thread = threading.Thread(
            target=self._log_pump, name=f"LogPump-{self.name}", daemon=True
        )
        self.thread.start()

    def _log_pump(self):
        tag = f"{self.color}[{self.name}]{RESET}"
        try:
            if self.proc and self.proc.stdout:
                for line in iter(self.proc.stdout.readline, ""):
                    clean = line.rstrip()
                    if clean:
                        print(f"{tag} {clean}", flush=True)
        except Exception:
            pass
        finally:
            self.is_alive = False

    def wait_for_port(self, timeout_sec: float = 10.0) -> bool:
        if not self.port:
            time.sleep(self.startup_wait_sec)
            return True

        t_start = time.perf_counter()
        while time.perf_counter() - t_start < timeout_sec:
            if self.proc and self.proc.poll() is not None:
                logger.error(
                    "Service %s exited prematurely with code %d",
                    self.name,
                    self.proc.returncode,
                )
                return False
            try:
                with socket.create_connection((self.host, self.port), timeout=0.5):
                    logger.info(
                        "Service %s%s%s is listening on %s:%d (verified in %.2fs)",
                        self.color,
                        self.name,
                        RESET,
                        self.host,
                        self.port,
                        time.perf_counter() - t_start,
                    )
                    return True
            except (ConnectionRefusedError, socket.timeout, OSError):
                time.sleep(0.2)

        logger.warning(
            "Service %s failed to open port %d within %.1fs timeout",
            self.name,
            self.port,
            timeout_sec,
        )
        return False

    def stop(self, timeout_sec: float = 3.0):
        if not self.proc:
            return
        if self.proc.poll() is None:
            logger.info("Stopping %s (PID %d)...", self.name, self.proc.pid)
            try:
                self.proc.terminate()
                self.proc.wait(timeout=timeout_sec)
            except (subprocess.TimeoutExpired, Exception):
                logger.warning("Force killing %s...", self.name)
                try:
                    self.proc.kill()
                    self.proc.wait(timeout=1.0)
                except Exception:
                    pass
        self.is_alive = False


class VeriPulseOrchestrator:
    def __init__(
        self,
        mode: str = "DRY_RUN",
        fps: float = 120.0,
        enable_plc: bool = True,
        enable_streamer: bool = True,
        enable_edge: bool = True,
        enable_gateway: bool = True,
        enable_cool: bool = True,
        enable_agent: bool = True,
    ):
        self.mode = mode.upper()
        self.fps = fps
        self.enable_plc = enable_plc
        self.enable_streamer = enable_streamer
        self.enable_edge = enable_edge
        self.enable_gateway = enable_gateway
        self.enable_cool = enable_cool
        self.enable_agent = enable_agent

        self.services: List[ManagedService] = []
        self.is_running = False
        self._init_service_definitions()

    def _init_service_definitions(self):
        py_exe = sys.executable

        # 1. Simulated Siemens S7-1500 PLC Server (Port 5020)
        if self.enable_plc:
            plc_script = os.path.join(PROJECT_ROOT, "plc_bridge", "simulated_plc_server.py")
            self.services.append(
                ManagedService(
                    name="PLC-SIM",
                    cmd=[py_exe, plc_script, "--port", "5020", "--host", "127.0.0.1"],
                    port=5020,
                    host="127.0.0.1",
                    color=YELLOW,
                    startup_wait_sec=1.0,
                )
            )

        # 2. COOL Metrology Server (Port 8000)
        if self.enable_cool:
            cool_script = os.path.join(
                PROJECT_ROOT, "cloud_metrology_cool", "cool_metrology_server.py"
            )
            self.services.append(
                ManagedService(
                    name="COOL-SRV",
                    cmd=[py_exe, cool_script, "--port", "8000", "--host", "127.0.0.1"],
                    port=8000,
                    color=BLUE,
                    startup_wait_sec=1.5,
                )
            )

        # 3. 120 FPS Synthetic Substrate Streamer (Shared Memory Producer)
        if self.enable_streamer:
            streamer_script = os.path.join(
                PROJECT_ROOT, "synthetic_streamer", "synthetic_generator.py"
            )
            self.services.append(
                ManagedService(
                    name="SYNTH-120FPS",
                    cmd=[py_exe, streamer_script, "--fps", str(self.fps)],
                    color=GREEN,
                    startup_wait_sec=1.0,
                )
            )

        # 4. Edge Vision & Physics Reflex Engine (G-API & FFT Consumer)
        if self.enable_edge:
            edge_script = os.path.join(PROJECT_ROOT, "edge_vision", "edge_runner.py")
            self.services.append(
                ManagedService(
                    name="EDGE-GAPI",
                    cmd=[py_exe, edge_script],
                    color=CYAN,
                    startup_wait_sec=1.0,
                )
            )

        # 5. High-Throughput SHM WebSocket Gateway (Port 8765)
        if self.enable_gateway:
            gateway_script = os.path.join(
                PROJECT_ROOT, "gateway_ipc", "shm_websocket_gateway.py"
            )
            self.services.append(
                ManagedService(
                    name="WS-GATEWAY",
                    cmd=[py_exe, gateway_script, "--port", "8765", "--host", "127.0.0.1"],
                    port=8765,
                    color=MAGENTA,
                    startup_wait_sec=1.0,
                )
            )

        # 6. AWS Bedrock Autonomous Supervisory Healer Agent
        if self.enable_agent:
            agent_script = os.path.join(
                PROJECT_ROOT, "cloud_agent", "bedrock_metrology_agent.py"
            )
            self.services.append(
                ManagedService(
                    name="BEDROCK-AGENT",
                    cmd=[py_exe, agent_script, "--daemon", "--mode", self.mode],
                    color=BOLD + GREEN,
                    startup_wait_sec=1.0,
                )
            )

    def print_banner(self):
        banner = f"""
{BOLD}{CYAN}========================================================================================
            VERIPULSE UNIFIED CYBER-PHYSICAL & CLOUD ORCHESTRATOR
========================================================================================{RESET}
  * Execution Mode       : {BOLD}{self.mode}{RESET}
  * Inspection Velocity  : {BOLD}{self.fps:.1f} FPS (8.33 ms frame budget){RESET}
  * Sub-Pixel Precision  : {BOLD}+-2.44 um (24.4 um optical CMOS pixel pitch){RESET}
  * Modbus PLC Endpoint  : {BOLD}127.0.0.1:5020{RESET}
  * COOL Metrology API   : {BOLD}http://127.0.0.1:8000{RESET}
  * WebSocket Gateway    : {BOLD}ws://127.0.0.1:8765{RESET}
  * Shared Memory Buffer : {BOLD}veripulse_shm_v1 (5.0 MB zero-copy ring){RESET}
  * Active Services      : {len(self.services)} supervised processes
{BOLD}{CYAN}========================================================================================{RESET}
"""
        print(banner, flush=True)

    def start_all(self):
        self.print_banner()
        self.is_running = True

        for service in self.services:
            service.start()
            if service.port:
                healthy = service.wait_for_port(timeout_sec=12.0)
                if not healthy:
                    logger.warning(
                        "Service %s failed port check on %d. Continuing startup sequence.",
                        service.name,
                        service.port,
                    )
            else:
                time.sleep(service.startup_wait_sec)

        logger.info(
            "%sAll VeriPulse background services initialized and supervised.%s",
            BOLD + GREEN,
            RESET,
        )

    def monitor_loop(self, duration_sec: Optional[float] = None, interval_sec: float = 5.0):
        t_start = time.perf_counter()
        try:
            while self.is_running:
                time.sleep(interval_sec)
                dead_services = [s for s in self.services if s.proc and s.proc.poll() is not None]
                if dead_services:
                    for ds in dead_services:
                        logger.error(
                            "CRITICAL: Supervised service %s died unexpectedly (exit code %s)",
                            ds.name,
                            ds.proc.returncode if ds.proc else "UNKNOWN",
                        )

                if duration_sec and (time.perf_counter() - t_start >= duration_sec):
                    logger.info("Specified runtime duration (%.1fs) elapsed. Initiating shutdown.", duration_sec)
                    break

        except KeyboardInterrupt:
            logger.info("Interrupt signal received. Initiating graceful shutdown...")
        finally:
            self.stop_all()

    def stop_all(self):
        if not self.is_running:
            return
        self.is_running = False
        logger.info("%sShutting down all VeriPulse managed services in reverse dependency order...%s", BOLD + YELLOW, RESET)

        for service in reversed(self.services):
            service.stop(timeout_sec=2.5)

        # Cleanup shared memory if attached
        try:
            from edge_vision.shm_common import get_or_create_shm
            shm = get_or_create_shm(create=False)
            shm.close()
            if hasattr(shm, "unlink"):
                try:
                    shm.unlink()
                except Exception:
                    pass
            logger.info("Cleaned up veripulse_shm_v1.")
        except Exception:
            pass

        logger.info("%sVeriPulse Orchestrator shutdown complete. All services terminated.%s", BOLD + GREEN, RESET)


def parse_args():
    parser = argparse.ArgumentParser(description="VeriPulse Unified Multi-Process Orchestrator")
    parser.add_argument("--mode", choices=["DRY_RUN", "LIVE"], default="DRY_RUN", help="Execution mode (default: DRY_RUN)")
    parser.add_argument("--fps", type=float, default=120.0, help="Target streamer framerate (default: 120.0)")
    parser.add_argument("--timeout", type=float, default=None, help="Automatic shutdown timeout in seconds (useful for CI/test)")
    parser.add_argument("--no-plc", action="store_true", help="Disable simulated PLC Modbus server")
    parser.add_argument("--no-streamer", action="store_true", help="Disable synthetic foil streamer")
    parser.add_argument("--no-edge", action="store_true", help="Disable G-API edge vision runner")
    parser.add_argument("--no-gateway", action="store_true", help="Disable WebSocket IPC gateway")
    parser.add_argument("--no-cool", action="store_true", help="Disable COOL metrology microservice")
    parser.add_argument("--no-agent", action="store_true", help="Disable Bedrock autonomous agent")
    return parser.parse_args()


def main():
    args = parse_args()

    orchestrator = VeriPulseOrchestrator(
        mode=args.mode,
        fps=args.fps,
        enable_plc=not args.no_plc,
        enable_streamer=not args.no_streamer,
        enable_edge=not args.no_edge,
        enable_gateway=not args.no_gateway,
        enable_cool=not args.no_cool,
        enable_agent=not args.no_agent,
    )

    def handle_signal(signum, frame):
        orchestrator.stop_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    orchestrator.start_all()
    orchestrator.monitor_loop(duration_sec=args.timeout)


if __name__ == "__main__":
    main()
