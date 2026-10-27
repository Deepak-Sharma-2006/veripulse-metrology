"""
VeriPulse SCADA Historian Tool
==============================
Manages local industrial historian telemetry using SQLite in WAL mode (Write-Ahead Logging)
with high-speed in-memory ring buffer caching.
Used by the Bedrock Metrology Agent for deep historical lookback drift diagnostics
when multi-hour anomalies cannot be resolved from the edge 60-second pre-hydrated window.
"""

import os
import sys
import time
import sqlite3
import logging
from collections import deque
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("SCADAHistorian")

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
DB_PATH = os.path.join(PROJECT_ROOT, "veripulse_scada.db")

# In-memory ring buffer storing the latest 1,000 SCADA telemetry records
_IN_MEMORY_RING_BUFFER = deque(maxlen=1000)


def get_db_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Initializes and returns an SQLite connection with WAL journal mode enabled."""
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_scada_db(db_path: str = DB_PATH) -> None:
    """Creates tables for time-series SCADA telemetry and incident logs."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scada_telemetry (
                    timestamp_ns INTEGER PRIMARY KEY,
                    line_id TEXT,
                    line_speed_mps REAL,
                    web_tension_n REAL,
                    dryer_temp_c REAL,
                    pump_rpm REAL,
                    dancer_gain REAL,
                    defect_count INTEGER,
                    alert_flags INTEGER
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS incident_ledger (
                    signature_id TEXT PRIMARY KEY,
                    timestamp_ns INTEGER,
                    line_id TEXT,
                    anomaly_type TEXT,
                    verdict TEXT,
                    action_taken TEXT,
                    settling_time_sec REAL
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_time ON scada_telemetry(timestamp_ns);")
    finally:
        conn.close()


def seed_nominal_telemetry_if_empty(db_path: str = DB_PATH, count: int = 60) -> None:
    """Pre-seeds recent nominal SCADA records if the database is currently empty."""
    init_scada_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM scada_telemetry;")
        existing_count = cursor.fetchone()[0]

        if existing_count == 0:
            now_ns = time.time_ns()
            records = []
            for i in range(count):
                t_ns = now_ns - (count - i) * 1_000_000_000  # 1-second cadence
                # Slight realistic drift: temp slowly climbing +1.45 C/min
                records.append(
                    (
                        t_ns,
                        "line_04_lithium_anode",
                        2.50,
                        150.0 + (i % 5 - 2) * 0.4,
                        118.0 + (i / 60.0) * 1.45,
                        1200.0 + (i % 3 - 1) * 2.5,
                        5.00,
                        0,
                        0,
                    )
                )
            with conn:
                conn.executemany(
                    """
                    INSERT INTO scada_telemetry
                    (timestamp_ns, line_id, line_speed_mps, web_tension_n, dryer_temp_c, pump_rpm, dancer_gain, defect_count, alert_flags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    records,
                )
            for r in records:
                _IN_MEMORY_RING_BUFFER.append(
                    {
                        "timestamp_ns": r[0],
                        "line_id": r[1],
                        "line_speed_mps": r[2],
                        "web_tension_n": r[3],
                        "dryer_temp_c": r[4],
                        "pump_rpm": r[5],
                        "dancer_gain": r[6],
                        "defect_count": r[7],
                        "alert_flags": r[8],
                    }
                )
    finally:
        conn.close()


def record_scada_sample(sample: Dict[str, Any], db_path: str = DB_PATH) -> None:
    """Appends a single telemetry record to both the in-memory buffer and SQLite."""
    t_ns = sample.get("timestamp_ns") or time.time_ns()
    record = {
        "timestamp_ns": t_ns,
        "line_id": sample.get("line_id", "line_04_lithium_anode"),
        "line_speed_mps": float(sample.get("line_speed_mps", 2.50)),
        "web_tension_n": float(sample.get("web_tension_n", 150.0)),
        "dryer_temp_c": float(sample.get("dryer_temp_c", 120.0)),
        "pump_rpm": float(sample.get("pump_rpm", 1200.0)),
        "dancer_gain": float(sample.get("dancer_gain", 5.00)),
        "defect_count": int(sample.get("defect_count", 0)),
        "alert_flags": int(sample.get("alert_flags", 0)),
    }
    _IN_MEMORY_RING_BUFFER.append(record)

    try:
        conn = get_db_connection(db_path)
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO scada_telemetry
                (timestamp_ns, line_id, line_speed_mps, web_tension_n, dryer_temp_c, pump_rpm, dancer_gain, defect_count, alert_flags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    record["timestamp_ns"],
                    record["line_id"],
                    record["line_speed_mps"],
                    record["web_tension_n"],
                    record["dryer_temp_c"],
                    record["pump_rpm"],
                    record["dancer_gain"],
                    record["defect_count"],
                    record["alert_flags"],
                ),
            )
        conn.close()
    except Exception as e:
        logger.warning("Could not persist SCADA record to SQLite: %s", e)


def query_scada_trends(
    start_time_ns: Optional[int] = None,
    end_time_ns: Optional[int] = None,
    window_sec: int = 60,
    line_id: str = "line_04_lithium_anode",
    db_path: str = DB_PATH,
) -> Dict[str, Any]:
    """
    Queries rolling SCADA trends across the specified window.
    Calculates temperature slope (deg C/min), tension variance, and speed stability.
    """
    seed_nominal_telemetry_if_empty(db_path=db_path)

    now_ns = time.time_ns()
    end_ns = end_time_ns if end_time_ns is not None else now_ns
    start_ns = start_time_ns if start_time_ns is not None else (end_ns - window_sec * 1_000_000_000)

    rows: List[Tuple] = []
    try:
        conn = get_db_connection(db_path)
        with conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT timestamp_ns, line_speed_mps, web_tension_n, dryer_temp_c, pump_rpm, dancer_gain
                FROM scada_telemetry
                WHERE timestamp_ns >= ? AND timestamp_ns <= ?
                ORDER BY timestamp_ns ASC;
                """,
                (start_ns, end_ns),
            )
            rows = cur.fetchall()
        conn.close()
    except Exception as e:
        logger.warning("Historian query falling back to in-memory ring buffer: %s", e)
        rows = [
            (
                r["timestamp_ns"],
                r["line_speed_mps"],
                r["web_tension_n"],
                r["dryer_temp_c"],
                r["pump_rpm"],
                r["dancer_gain"],
            )
            for r in _IN_MEMORY_RING_BUFFER
            if start_ns <= r["timestamp_ns"] <= end_ns
        ]

    if not rows:
        return {
            "status": "empty_window",
            "line_id": line_id,
            "window_sec": window_sec,
            "sample_count": 0,
            "dryer_temp_slope_c_per_min": 1.45,
            "tension_variance_dn": 12.8,
            "pump_speed_rpm": 1200.0,
            "line_velocity_mps": 2.50,
            "trend_verdict": "nominal_fallback",
        }

    sample_count = len(rows)
    speeds = [r[1] for r in rows]
    tensions = [r[2] for r in rows]
    temps = [r[3] for r in rows]
    pumps = [r[4] for r in rows]

    # Calculate dryer temperature slope (deg C / minute)
    dt_min = max(0.1, (rows[-1][0] - rows[0][0]) / 60_000_000_000.0)
    dtemp = temps[-1] - temps[0]
    temp_slope_c_per_min = round(float(dtemp / dt_min), 2)

    # Tension variance in 0.1 N units
    import numpy as np

    tension_var = round(float(np.var(tensions) * 100.0), 2)  # In 0.1 N units
    mean_speed = round(float(np.mean(speeds)), 3)
    mean_pump = round(float(np.mean(pumps)), 1)

    trend_verdict = "nominal_operating_envelope"
    if temp_slope_c_per_min > 2.0:
        trend_verdict = "thermal_overheating_trend"
    elif tension_var > 25.0:
        trend_verdict = "tension_flutter_detected"

    return {
        "status": "success",
        "action": "query_scada_historian",
        "line_id": line_id,
        "window_sec": window_sec,
        "sample_count": sample_count,
        "dryer_temp_slope_c_per_min": temp_slope_c_per_min,
        "tension_variance_dn": tension_var,
        "pump_speed_rpm": mean_pump,
        "line_velocity_mps": mean_speed,
        "trend_verdict": trend_verdict,
        "first_timestamp_ns": rows[0][0],
        "latest_timestamp_ns": rows[-1][0],
    }


if __name__ == "__main__":
    init_scada_db()
    seed_nominal_telemetry_if_empty()
    res = query_scada_trends(window_sec=60)
    import json

    print(json.dumps(res, indent=2))
