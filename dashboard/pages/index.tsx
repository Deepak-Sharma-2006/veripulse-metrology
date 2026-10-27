import React, { useEffect, useRef, useState, useCallback } from "react";
import Head from "next/head";
import dynamic from "next/dynamic";
import {
  Activity,
  Radio,
  ShieldCheck,
  AlertOctagon,
  RefreshCw,
  Cpu,
  Wifi,
  WifiOff,
  Sliders,
  Play,
  RotateCcw,
  Zap,
  Crosshair,
  Sun,
  Power,
  Layers,
} from "lucide-react";

import { VideoInspectionFeed, TelemetryData, ActiveAlert } from "../components/VideoInspectionFeed";
import { FFTSpectrumView } from "../components/FFTSpectrumView";
import { AgenticChatConsole, AgentEvent, PLCUpdateEvent } from "../components/AgenticChatConsole";
import { PLCTelemetryGauges } from "../components/PLCTelemetryGauges";

// SSR disabled dynamic import for Three.js Digital Twin
const DigitalTwinCanvas = dynamic(
  () => import("../components/DigitalTwinCanvas"),
  { ssr: false }
);

const DEFAULT_TELEMETRY: TelemetryData = {
  line_speed_mps: 2.50,
  tension_newtons: 150.0,
  dryer_temp_c: 120.0,
  pump_rpm: 1200.0,
  dancer_damping_gain: 5.00,
};

export default function OperatorConsole() {
  // Connection states
  const [connectionStatus, setConnectionStatus] = useState<"connecting" | "connected" | "simulation">("simulation");
  const [activeScenario, setActiveScenario] = useState<"nominal" | "ribbing" | "pinhole" | "glare">("nominal");
  const [estopArmed, setEstopArmed] = useState<boolean>(true);
  const [systemClock, setSystemClock] = useState<string>("");

  // Real-time telemetry state
  const [telemetry, setTelemetry] = useState<TelemetryData>(DEFAULT_TELEMETRY);
  const [spectrumData, setSpectrumData] = useState<number[]>([]);
  const [isRibbingActive, setIsRibbingActive] = useState<boolean>(false);

  // Agent Event stream & PLC updates
  const [agentEvents, setAgentEvents] = useState<AgentEvent[]>([]);
  const [plcUpdates, setPLCUpdates] = useState<PLCUpdateEvent[]>([]);

  // High-frequency mutable refs for direct HTML5 Canvas painting (Zero React Jitter)
  const telemetryRef = useRef<TelemetryData>(DEFAULT_TELEMETRY);
  const alertRef = useRef<ActiveAlert | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const simTimerRef = useRef<NodeJS.Timeout | null>(null);
  const simStepRef = useRef<number>(0);
  const manualScenarioTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Initial Clock
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setSystemClock(now.toISOString().replace("T", " ").substring(0, 19) + " UTC");
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  // -------------------------------------------------------------
  // Manual Interactive Scenario Triggering (Instant Response)
  // -------------------------------------------------------------
  const triggerManualScenario = useCallback((scenario: "nominal" | "ribbing" | "pinhole" | "glare") => {
    setActiveScenario(scenario);
    if (manualScenarioTimerRef.current) {
      clearTimeout(manualScenarioTimerRef.current);
    }

    if (scenario === "nominal") {
      setIsRibbingActive(false);
      alertRef.current = { detected: false, defect_type: "nominal", severity: "NOMINAL", bounding_box: null };
      setTelemetry((prev) => ({ ...prev, line_speed_mps: 2.50, dancer_damping_gain: 5.00, tension_newtons: 150.0 }));
      telemetryRef.current = { ...telemetryRef.current, line_speed_mps: 2.50, dancer_damping_gain: 5.00, tension_newtons: 150.0 };

    } else if (scenario === "ribbing") {
      setIsRibbingActive(true);
      alertRef.current = {
        detected: true,
        defect_type: "slot_die_ribbing_resonance",
        severity: "WARNING",
        bounding_box: { x: 14200, y: 8500, width: 450, height: 180 },
      };

      // Add Claude 3.5 Sonnet Agent Event
      const ribbingEvt: AgentEvent = {
        event_id: `evt_${Date.now().toString(16).substring(6)}`,
        timestamp_ns: Date.now() * 1000000,
        model_id: "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        cool_metrology_verification: {
          engine: "COOL-v3.1-Arm64-KleidiCV",
          verdict: "slot_die_ribbing_resonance_confirmed",
          morphological_solidity: 0.38,
          gabor_energy_ratio: 0.88,
        },
        agent_reasoning:
          "Spatial 2D-FFT confirms 142.50 Hz fundamental harmonic (+44.3 dB). SCADA coupling indicates slurry metering surge. Dispatched velocity shift (-120 mm/s) and dancer roll damping increase (+1.50) to shift line out of resonance.",
        dispatched_tool: "execute_plc_recalibration",
        tool_parameters: {
          line_id: "line_04_lithium_anode",
          target_plc_ip: "192.168.10.50",
          engineering_setpoints: {
            line_velocity_mps: 2.38,
            web_tension_newtons: 145.0,
            dancer_damping_gain: 6.50,
          },
        },
        closed_loop_latency_ms: 2150.8,
      };
      setAgentEvents((prev) => [ribbingEvt, ...prev.slice(0, 19)]);

      // Closed-Loop Decay: Settle after 2.5 seconds
      manualScenarioTimerRef.current = setTimeout(() => {
        setTelemetry((prev) => ({ ...prev, line_speed_mps: 2.38, dancer_damping_gain: 6.50 }));
        telemetryRef.current = { ...telemetryRef.current, line_speed_mps: 2.38, dancer_damping_gain: 6.50 };
        setIsRibbingActive(false);
        setActiveScenario("nominal");
      }, 2500);

    } else if (scenario === "glare") {
      setIsRibbingActive(false);
      alertRef.current = {
        detected: true,
        defect_type: "surface_reflectance_anomaly",
        severity: "INFO",
        bounding_box: { x: 5000, y: 8000, width: 300, height: 300 },
      };

      const glareEvt: AgentEvent = {
        event_id: `evt_${Date.now().toString(16).substring(6)}`,
        timestamp_ns: Date.now() * 1000000,
        model_id: "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        cool_metrology_verification: {
          engine: "COOL-v3.1-Arm64-KleidiCV",
          verdict: "specular_reflection_suspected",
          morphological_solidity: 0.94,
          gabor_energy_ratio: 0.12,
        },
        agent_reasoning:
          "High specular saturation ratio (0.82) confirms bare copper glare rather than slurry delamination. Dynamically retuning bilateral filter and Scharr gradient thresholds to eradicate scrap false-positives.",
        dispatched_tool: "recalibrate_gapi_vision_pipeline",
        tool_parameters: {
          line_id: "line_04_lithium_anode",
          bilateral_spatial_sigma: 1.8,
          bilateral_range_sigma: 0.08,
          scharr_gradient_threshold: 45.0,
        },
        closed_loop_latency_ms: 1890.4,
      };
      setAgentEvents((prev) => [glareEvt, ...prev.slice(0, 19)]);

      manualScenarioTimerRef.current = setTimeout(() => {
        alertRef.current = { detected: false, defect_type: "nominal", severity: "NOMINAL", bounding_box: null };
        setActiveScenario("nominal");
      }, 2000);

    } else if (scenario === "pinhole") {
      setIsRibbingActive(false);
      alertRef.current = {
        detected: true,
        defect_type: "micro_pinhole_anomaly",
        severity: "WARNING",
        bounding_box: { x: 10500, y: 9800, width: 120, height: 120 },
      };

      const pinholeEvt: AgentEvent = {
        event_id: `evt_${Date.now().toString(16).substring(6)}`,
        timestamp_ns: Date.now() * 1000000,
        model_id: "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        cool_metrology_verification: {
          engine: "COOL-v3.1-Arm64-KleidiCV",
          verdict: "micro_pinhole_verified",
          morphological_solidity: 0.96,
          gabor_energy_ratio: 0.74,
        },
        agent_reasoning:
          "Targeted sub-pixel metrology isolates 52.1 µm void. Multi-spectral fusion confirms zero graphite coverage exposing copper current collector. Logged coordinates into SCADA incident database.",
        dispatched_tool: "query_scada_historian",
        tool_parameters: {
          line_id: "line_04_lithium_anode",
          defect_class: "pinhole_50um",
          coordinates_um: { x: 26000, y: 24500 },
        },
        closed_loop_latency_ms: 1720.0,
      };
      setAgentEvents((prev) => [pinholeEvt, ...prev.slice(0, 19)]);

      manualScenarioTimerRef.current = setTimeout(() => {
        alertRef.current = { detected: false, defect_type: "nominal", severity: "NOMINAL", bounding_box: null };
        setActiveScenario("nominal");
      }, 3000);
    }
  }, []);

  // -------------------------------------------------------------
  // Background Simulation Step (Cycles seamlessly when idle)
  // -------------------------------------------------------------
  const runSimulationStep = useCallback(() => {
    simStepRef.current += 1;
    const step = simStepRef.current;
    const t = step * (1.0 / 30.0);

    // If manual scenario is active, do not override
    if (activeScenario === "nominal") {
      const cycle = t % 30.0;
      const ribbing = cycle >= 18.0 && cycle < 24.0;
      setIsRibbingActive(ribbing);

      let vel = 2.50 + Math.sin(t * 0.1) * 0.005;
      let tension = 150.0 + (ribbing ? Math.sin(t * 14.25 * 2 * Math.PI) * 4.2 : Math.sin(t * 0.4) * 0.6);
      let temp = 120.0 + Math.sin(t * 0.05) * 0.4;
      let pump = 1200.0 + (ribbing ? 35.0 * Math.sin(t * 2.0) : Math.sin(t * 0.8) * 2.0);
      let gain = ribbing ? 6.50 : 5.00;

      if (ribbing) {
        vel = 2.38;
      }

      const nextTel: TelemetryData = {
        line_speed_mps: Number(vel.toFixed(3)),
        tension_newtons: Number(tension.toFixed(2)),
        dryer_temp_c: Number(temp.toFixed(2)),
        pump_rpm: Number(pump.toFixed(1)),
        dancer_damping_gain: Number(gain.toFixed(2)),
      };
      telemetryRef.current = nextTel;
      setTelemetry(nextTel);

      if (ribbing && !alertRef.current?.detected) {
        alertRef.current = {
          detected: true,
          defect_type: "slot_die_ribbing_resonance",
          severity: "WARNING",
          bounding_box: { x: 14200, y: 8500, width: 450, height: 180 },
        };
      } else if (!ribbing && alertRef.current?.detected) {
        alertRef.current = { detected: false, defect_type: "nominal", severity: "NOMINAL", bounding_box: null };
      }
    }

    // Generate 512-bin FFT spectrum
    const isRib = isRibbingActive || activeScenario === "ribbing";
    const spectrum = new Array(512).fill(0).map((_, i) => {
      let base = 0.015 + 0.005 * Math.sin(i * 0.15) + (Math.random() * 0.005);
      if (i === 14) base = 0.30 + Math.random() * 0.03; // 14.25 Hz Runout
      if (i === 142) base = isRib ? 0.88 + Math.random() * 0.05 : 0.075; // 142.5 Hz Ribbing
      if (i === 285 && isRib) base = 0.40 + Math.random() * 0.03;
      return Number(base.toFixed(4));
    });
    setSpectrumData(spectrum);
  }, [activeScenario, isRibbingActive]);

  // WebSocket / Simulation connection lifecycle
  useEffect(() => {
    let ws: WebSocket | null = null;
    let didConnect = false;

    try {
      ws = new WebSocket("ws://localhost:8765");
      socketRef.current = ws;

      ws.onopen = () => {
        didConnect = true;
        setConnectionStatus("connected");
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "telemetry") {
            telemetryRef.current = data.payload;
            setTelemetry(data.payload);
          } else if (data.type === "alert") {
            alertRef.current = data.payload;
          }
        } catch {
          // fallback
        }
      };

      ws.onerror = () => {
        if (!didConnect) {
          setConnectionStatus("simulation");
        }
      };
    } catch {
      setConnectionStatus("simulation");
    }

    // Always run simulation step timer as base heartbeat
    simTimerRef.current = setInterval(runSimulationStep, 100);

    return () => {
      if (ws) ws.close();
      if (simTimerRef.current) clearInterval(simTimerRef.current);
      if (manualScenarioTimerRef.current) clearTimeout(manualScenarioTimerRef.current);
    };
  }, [runSimulationStep]);

  return (
    <div className="h-screen max-h-screen overflow-hidden bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-sky-500 selection:text-white">
      <Head>
        <title>VeriPulse Dynamics | Autonomous Roll-to-Roll Metrology Console</title>
        <meta
          name="description"
          content="OpenCV 5 G-API and AWS Graviton3 COOL autonomous metrology and supervisory self-healing digital twin."
        />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      {/* ------------------------------------------------------------- */}
      {/* 1. Sleek Industrial Enterprise Top Header                     */}
      {/* ------------------------------------------------------------- */}
      <header className="h-12 px-4 py-1.5 bg-slate-900 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3 shrink-0 z-50 shadow-md">
        {/* Brand & Line Identification */}
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <div className="w-7 h-7 rounded bg-sky-600 flex items-center justify-center font-bold text-sm tracking-tight text-white shadow-sm">
              VP
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-sm tracking-tight text-slate-50">
                  VERIPULSE DYNAMICS
                </span>
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 border border-slate-700">
                  v1.2-PROD
                </span>
              </div>
              <div className="text-[11px] text-slate-400">
                Continuous Lithium-Ion Anode Coater • Line 04 (2.50 m/s)
              </div>
            </div>
          </div>
        </div>

        {/* Tactile Interactive Scenario Toolbar (Judicial Controls) */}
        <div className="flex items-center space-x-1.5 bg-slate-950 p-1 rounded-lg border border-slate-800">
          <span className="text-[10px] font-medium text-slate-400 px-2 uppercase tracking-wider hidden md:inline">
            Test Scenario:
          </span>
          <button
            onClick={() => triggerManualScenario("nominal")}
            className={`px-2.5 py-1 text-[11px] font-medium rounded transition flex items-center space-x-1.5 ${
              activeScenario === "nominal"
                ? "bg-emerald-600 text-white shadow-xs font-semibold"
                : "text-slate-300 hover:bg-slate-800/80"
            }`}
          >
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span>Nominal (120 FPS)</span>
          </button>
          <button
            onClick={() => triggerManualScenario("ribbing")}
            className={`px-2.5 py-1 text-[11px] font-medium rounded transition flex items-center space-x-1.5 ${
              activeScenario === "ribbing"
                ? "bg-amber-600 text-white shadow-xs font-semibold"
                : "text-slate-300 hover:bg-slate-800/80"
            }`}
          >
            <Zap className="w-3 h-3 text-amber-300" />
            <span>142.5 Hz Ribbing</span>
          </button>
          <button
            onClick={() => triggerManualScenario("pinhole")}
            className={`px-2.5 py-1 text-[11px] font-medium rounded transition flex items-center space-x-1.5 ${
              activeScenario === "pinhole"
                ? "bg-rose-600 text-white shadow-xs font-semibold"
                : "text-slate-300 hover:bg-slate-800/80"
            }`}
          >
            <Crosshair className="w-3 h-3 text-rose-300" />
            <span>50 µm Pinhole</span>
          </button>
          <button
            onClick={() => triggerManualScenario("glare")}
            className={`px-2.5 py-1 text-[11px] font-medium rounded transition flex items-center space-x-1.5 ${
              activeScenario === "glare"
                ? "bg-sky-600 text-white shadow-xs font-semibold"
                : "text-slate-300 hover:bg-slate-800/80"
            }`}
          >
            <Sun className="w-3 h-3 text-sky-300" />
            <span>Copper Glare</span>
          </button>
        </div>

        {/* Status Indicators & Clock */}
        <div className="flex items-center space-x-3 text-xs font-mono">
          <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded bg-slate-950 border border-slate-800 text-slate-300">
            <div
              className={`w-2 h-2 rounded-full ${
                connectionStatus === "connected" ? "bg-emerald-400" : "bg-sky-400 animate-pulse"
              }`}
            />
            <span className="text-[11px]">
              {connectionStatus === "connected" ? "LIVE IPC (SHM)" : "STANDALONE SIMULATOR"}
            </span>
          </div>

          <div className="text-slate-400 text-[11px] hidden lg:inline">
            {systemClock}
          </div>

          <button
            onClick={() => setEstopArmed((prev) => !prev)}
            className={`px-2.5 py-1 rounded font-semibold text-[11px] transition flex items-center space-x-1.5 border ${
              estopArmed
                ? "bg-red-950/80 hover:bg-red-900 text-red-300 border-red-800/80"
                : "bg-emerald-950/80 hover:bg-emerald-900 text-emerald-300 border-emerald-800/80"
            }`}
          >
            <Power className="w-3.5 h-3.5" />
            <span>{estopArmed ? "E-STOP ARMED" : "RESET E-STOP"}</span>
          </button>
        </div>
      </header>

      {/* ------------------------------------------------------------- */}
      {/* 2. Main High-Density Industrial Dashboard Grid                */}
      {/* ------------------------------------------------------------- */}
      <main className="flex-1 min-h-0 p-2.5 grid grid-cols-1 lg:grid-cols-12 gap-2.5 max-w-[1920px] mx-auto w-full overflow-hidden">
        {/* Left Column: Edge Perception & Optical Inspection (5 Cols) */}
        <div className="lg:col-span-5 flex flex-col h-full min-h-0 gap-2.5 overflow-hidden">
          <div className="h-[55%] min-h-0">
            <VideoInspectionFeed
              telemetryRef={telemetryRef}
              alertRef={alertRef}
              fps={120.0}
            />
          </div>
          <div className="h-[45%] min-h-0">
            <FFTSpectrumView spectrumData={spectrumData} />
          </div>
        </div>

        {/* Middle Column: 3D Digital Twin & Modbus Gauges (4 Cols) */}
        <div className="lg:col-span-4 flex flex-col h-full min-h-0 gap-2.5 overflow-hidden">
          <div className="h-[60%] min-h-0 bg-slate-900 border border-slate-800 rounded-lg overflow-hidden shadow-lg flex flex-col">
            <div className="flex items-center justify-between px-3.5 py-2 bg-slate-950/80 border-b border-slate-800 shrink-0">
              <div className="flex items-center space-x-2">
                <Layers className="w-4 h-4 text-sky-400" />
                <span className="text-xs font-semibold text-slate-100">
                  3D Mechanical Digital Twin
                </span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                  Three.js R2R Line
                </span>
              </div>
              <span className="text-[10px] font-mono text-slate-400">
                Drag to Orbit • Scroll to Zoom
              </span>
            </div>
            <div className="flex-1 min-h-0 relative bg-slate-950">
              <DigitalTwinCanvas
                telemetry={telemetry}
                isRibbingActive={isRibbingActive || activeScenario === "ribbing"}
              />
            </div>
          </div>

          <div className="h-[40%] min-h-0 flex flex-col">
            <PLCTelemetryGauges
              telemetry={telemetry}
              defectCount={agentEvents.length}
              estopArmed={estopArmed}
            />
          </div>
        </div>

        {/* Right Column: Autonomous Supervisory Controller (3 Cols) */}
        <div className="lg:col-span-3 flex flex-col h-full min-h-0 overflow-hidden">
          <AgenticChatConsole
            agentEvents={agentEvents}
            plcUpdates={plcUpdates}
            onTriggerDefect={(type) => {
              if (type.includes("ribbing")) triggerManualScenario("ribbing");
              else triggerManualScenario("glare");
            }}
          />
        </div>
      </main>

      {/* ------------------------------------------------------------- */}
      {/* 3. Executive Telemetry Status Bar                             */}
      {/* ------------------------------------------------------------- */}
      <footer className="h-8 px-4 bg-slate-950 border-t border-slate-800 flex flex-wrap items-center justify-between text-[11px] font-mono text-slate-400 gap-2 shrink-0">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span>G-API Pipeline: <strong className="text-slate-200">Nominal (120.0 FPS)</strong></span>
          </div>
          <div className="hidden sm:inline text-slate-600">|</div>
          <div className="hidden sm:inline">
            COOL Verification: <strong className="text-slate-200">Graviton Arm64 KleidiCV</strong>
          </div>
          <div className="hidden md:inline text-slate-600">|</div>
          <div className="hidden md:inline">
            Modbus TCP: <strong className="text-slate-200">Port 5020 (Siemens S7-1500)</strong>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          <div>
            Target Metrology: <strong className="text-emerald-400">±2.44 µm</strong>
          </div>
          <div className="text-slate-600">|</div>
          <div>
            Zero-Copy IPC: <strong className="text-sky-400">veripulse_shm_v1 (5.0 MB)</strong>
          </div>
        </div>
      </footer>
    </div>
  );
}
