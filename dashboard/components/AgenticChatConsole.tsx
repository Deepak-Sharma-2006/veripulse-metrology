import React, { useState } from "react";
import { Bot, Terminal, Cpu, ShieldCheck, Wrench, CheckCircle, Clock, Zap, ArrowRight, Activity } from "lucide-react";

export interface AgentEvent {
  event_id: string;
  timestamp_ns: number;
  model_id: string;
  cool_metrology_verification: {
    engine: string;
    verdict: string;
    morphological_solidity?: number;
    gabor_energy_ratio?: number;
  };
  agent_reasoning: string;
  dispatched_tool: string;
  tool_parameters: Record<string, any>;
  closed_loop_latency_ms: number;
}

export interface PLCUpdateEvent {
  timestamp_ns: number;
  holding_registers: {
    velocity_mms: number;
    tension_dn: number;
    temp_dc: number;
    pump_drpm: number;
    dancer_dgain: number;
  };
  hmac_sha256_signature: string;
  actuator_settling_time_sec: number;
}

interface AgenticChatConsoleProps {
  agentEvents: AgentEvent[];
  plcUpdates: PLCUpdateEvent[];
  onTriggerDefect?: (defectType: string) => void;
}

export const AgenticChatConsole: React.FC<AgenticChatConsoleProps> = ({
  agentEvents,
  plcUpdates,
  onTriggerDefect,
}) => {
  const [filterMode, setFilterMode] = useState<"all" | "reasoning" | "tools" | "plc">("all");

  return (
    <div className="flex flex-col h-full min-h-0 bg-slate-900 border border-slate-800 rounded-lg overflow-hidden shadow-lg">
      {/* Precision Industrial Header */}
      <div className="flex items-center justify-between px-3.5 py-2 bg-slate-950/80 border-b border-slate-800 min-w-0 shrink-0">
        <div className="flex items-center space-x-2.5 min-w-0">
          <Bot className="w-4 h-4 text-emerald-400 shrink-0" />
          <div className="flex items-center space-x-2 truncate">
            <span className="text-xs font-semibold tracking-wide text-slate-100 truncate">
              Autonomous Supervisory Controller
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800/60 font-medium shrink-0">
              Claude 3.5 Sonnet
            </span>
          </div>
        </div>

        <div className="flex items-center space-x-2 shrink-0">
          <div className="flex items-center space-x-1.5 px-2 py-0.5 rounded bg-slate-800/80 border border-slate-700/60 text-[10px] font-mono text-slate-300">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span>Active Agent</span>
          </div>
        </div>
      </div>

      {/* Filter and Quick Trigger Ribbon */}
      <div className="flex flex-wrap items-center justify-between gap-1.5 px-3 py-1.5 bg-slate-950/50 border-b border-slate-800/80 text-[11px] shrink-0">
        {/* Filter Tabs */}
        <div className="flex items-center space-x-1">
          <button
            onClick={() => setFilterMode("all")}
            className={`px-2.5 py-0.5 rounded text-[11px] font-medium transition ${
              filterMode === "all"
                ? "bg-sky-600 text-white shadow-xs"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            All Logs
          </button>
          <button
            onClick={() => setFilterMode("reasoning")}
            className={`px-2.5 py-0.5 rounded text-[11px] font-medium transition ${
              filterMode === "reasoning"
                ? "bg-sky-600 text-white shadow-xs"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            Reasoning
          </button>
          <button
            onClick={() => setFilterMode("tools")}
            className={`px-2.5 py-0.5 rounded text-[11px] font-medium transition ${
              filterMode === "tools"
                ? "bg-sky-600 text-white shadow-xs"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            Tools
          </button>
          <button
            onClick={() => setFilterMode("plc")}
            className={`px-2.5 py-0.5 rounded text-[11px] font-medium transition ${
              filterMode === "plc"
                ? "bg-sky-600 text-white shadow-xs"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            Modbus Actions
          </button>
        </div>

        {/* Quick Defect Scenario Triggers */}
        {onTriggerDefect && (
          <div className="flex items-center space-x-1.5 font-mono text-[10px]">
            <span className="text-slate-500 font-sans text-[10px] uppercase tracking-wider font-semibold">Test Scenario:</span>
            <button
              onClick={() => onTriggerDefect("slot_die_ribbing_resonance")}
              className="px-2 py-0.5 bg-amber-950/70 hover:bg-amber-900/80 text-amber-300 rounded border border-amber-800/70 transition flex items-center space-x-1 font-medium"
            >
              <Zap className="w-2.5 h-2.5 text-amber-400" />
              <span>142.5 Hz Ribbing</span>
            </button>
            <button
              onClick={() => onTriggerDefect("surface_reflectance_anomaly")}
              className="px-2 py-0.5 bg-slate-800/90 hover:bg-slate-700 text-slate-200 rounded border border-slate-700 transition font-medium"
            >
              Copper Glare
            </button>
          </div>
        )}
      </div>

      {/* Main Streaming Feed Area */}
      <div className="flex-1 min-h-0 overflow-y-auto p-2.5 space-y-2.5 font-sans text-xs">
        {agentEvents.length === 0 && plcUpdates.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-slate-500 space-y-2">
            <Activity className="w-6 h-6 text-slate-600 animate-pulse" />
            <p className="font-mono text-xs">Awaiting G-API Anomaly Signals...</p>
          </div>
        ) : (
          agentEvents.map((evt, idx) => {
            const isRibbing = evt.cool_metrology_verification.verdict?.includes("ribbing");
            return (
              <div
                key={evt.event_id || idx}
                className="flex flex-col p-3 rounded-lg bg-slate-950/70 border border-slate-800 shadow-sm space-y-2.5"
              >
                {/* Event Metadata Row */}
                <div className="flex items-center justify-between text-[11px] font-mono border-b border-slate-800/70 pb-1.5">
                  <div className="flex items-center space-x-2">
                    <span className="text-sky-400 font-semibold">{evt.event_id}</span>
                    <span className="text-slate-500">•</span>
                    <span className="px-1.5 py-0.5 rounded bg-slate-800/80 text-slate-300 border border-slate-700/60 text-[10px]">
                      {evt.cool_metrology_verification.engine}
                    </span>
                  </div>

                  <div className="flex items-center space-x-2 text-slate-400">
                    <Clock className="w-3 h-3 text-slate-500" />
                    <span className="text-emerald-400 font-semibold">{evt.closed_loop_latency_ms.toFixed(1)} ms</span>
                    <span className="text-slate-500">(Budget ≤3.5s)</span>
                  </div>
                </div>

                {/* COOL Verification Verdict Badge */}
                <div className="flex items-center space-x-2">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase ${
                      isRibbing
                        ? "bg-amber-950/80 text-amber-300 border border-amber-800/70"
                        : "bg-sky-950/80 text-sky-300 border border-sky-800/70"
                    }`}
                  >
                    VERDICT: {evt.cool_metrology_verification.verdict}
                  </span>
                </div>

                {/* Claude 3.5 Sonnet Reasoning Paragraph */}
                {(filterMode === "all" || filterMode === "reasoning") && (
                  <div className="text-slate-300 text-xs leading-relaxed bg-slate-900/60 p-2.5 rounded border border-slate-800/80">
                    <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1 flex items-center space-x-1.5">
                      <Terminal className="w-3 h-3 text-sky-400" />
                      <span>Claude 3.5 Sonnet Metrology Diagnosis</span>
                    </div>
                    <p className="font-normal text-slate-200">{evt.agent_reasoning}</p>
                  </div>
                )}

                {/* Tool Execution Card */}
                {(filterMode === "all" || filterMode === "tools") && (
                  <div className="flex flex-col p-2.5 rounded bg-slate-900/90 border border-slate-800 font-mono text-[11px] space-y-1.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-1.5 text-amber-400 font-semibold">
                        <Wrench className="w-3.5 h-3.5" />
                        <span>tool_call: {evt.dispatched_tool}</span>
                      </div>
                      <span className="px-1.5 py-0.5 rounded bg-emerald-950/80 text-emerald-400 text-[9px] font-semibold">
                        ACTUATED
                      </span>
                    </div>

                    <pre className="text-[10px] text-slate-300 overflow-x-auto p-2 bg-slate-950/90 rounded border border-slate-800/80 leading-snug">
                      {JSON.stringify(evt.tool_parameters, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Safety & SLA Footer Banner */}
      <div className="px-3 py-1.5 bg-slate-950 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400 shrink-0">
        <div className="flex items-center space-x-2">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span>Causal Safety Slew Gate: <strong className="text-emerald-400">Enforced (≤0.05 m/s²)</strong></span>
        </div>
        <div className="flex items-center space-x-2 font-mono text-[10px]">
          <span className="text-slate-500">Supervisory SLA:</span>
          <span className="text-slate-300 font-semibold">≤ 3.50s Settling</span>
        </div>
      </div>
    </div>
  );
};
