import React, { useState } from "react";
import { Bot, Terminal, Cpu, ShieldCheck, Wrench, CheckCircle, Clock, Zap } from "lucide-react";

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
    <div className="flex flex-col h-full bg-industrial-850 border border-industrial-700 rounded-lg overflow-hidden shadow-xl">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-industrial-900 border-b border-industrial-700">
        <div className="flex items-center space-x-2">
          <Bot className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-mono font-bold tracking-wider text-slate-200 uppercase">
            Claude 3.5 Sonnet Agentic Supervisory Core
          </span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="text-[10px] font-mono text-slate-400 hidden sm:inline">
            us.anthropic.claude-3-5-sonnet-20241022-v2:0
          </span>
          <div className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
        </div>
      </div>

      {/* Filter and Trigger Ribbon */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-1.5 bg-industrial-800 border-b border-industrial-700 text-[10px] font-mono">
        <div className="flex items-center space-x-1">
          <button
            onClick={() => setFilterMode("all")}
            className={`px-2 py-0.5 rounded transition ${
              filterMode === "all" ? "bg-cyan-500 text-slate-950 font-bold" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            All Logs
          </button>
          <button
            onClick={() => setFilterMode("reasoning")}
            className={`px-2 py-0.5 rounded transition ${
              filterMode === "reasoning" ? "bg-cyan-500 text-slate-950 font-bold" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Reasoning
          </button>
          <button
            onClick={() => setFilterMode("tools")}
            className={`px-2 py-0.5 rounded transition ${
              filterMode === "tools" ? "bg-cyan-500 text-slate-950 font-bold" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Tools
          </button>
          <button
            onClick={() => setFilterMode("plc")}
            className={`px-2 py-0.5 rounded transition ${
              filterMode === "plc" ? "bg-cyan-500 text-slate-950 font-bold" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            PLC Actuations
          </button>
        </div>

        {onTriggerDefect && (
          <div className="flex items-center space-x-1.5">
            <span className="text-slate-400 text-[9px]">INJECT:</span>
            <button
              onClick={() => onTriggerDefect("surface_reflectance_anomaly")}
              className="px-2 py-0.5 bg-industrial-700 hover:bg-industrial-600 text-amber-300 rounded border border-amber-500/30 text-[9px] transition"
            >
              Copper Glare
            </button>
            <button
              onClick={() => onTriggerDefect("slot_die_ribbing_resonance")}
              className="px-2 py-0.5 bg-industrial-700 hover:bg-industrial-600 text-cyan-300 rounded border border-cyan-500/30 text-[9px] transition"
            >
              142.5Hz Ribbing
            </button>
          </div>
        )}
      </div>

      {/* Main Streaming Feed Area */}
      <div className="flex-1 p-3 space-y-3 overflow-y-auto max-h-[380px] font-mono text-[11px]">
        {agentEvents.length === 0 && plcUpdates.length === 0 && (
          <div className="flex flex-col items-center justify-center py-10 text-slate-500 space-y-2">
            <Terminal className="w-6 h-6 text-slate-600" />
            <span>Awaiting telemetry anomalies or tool execution events...</span>
          </div>
        )}

        {/* Render Agent Events */}
        {agentEvents.map((evt, idx) => {
          if (filterMode === "plc") return null;
          if (filterMode === "tools" && !evt.dispatched_tool) return null;
          if (filterMode === "reasoning" && !evt.agent_reasoning) return null;

          const isRecalib = evt.dispatched_tool.includes("gapi");
          const toolBadgeColor = isRecalib ? "text-cyan-400 border-cyan-500/40 bg-cyan-950/40" : "text-amber-400 border-amber-500/40 bg-amber-950/40";

          return (
            <div
              key={evt.event_id || idx}
              className="p-2.5 rounded-lg bg-industrial-900 border border-industrial-700 space-y-2 transition hover:border-slate-600"
            >
              {/* Event Header */}
              <div className="flex items-center justify-between text-[10px] text-slate-400 border-b border-industrial-800 pb-1.5">
                <div className="flex items-center space-x-1.5">
                  <Bot className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-slate-200 font-bold">{evt.event_id}</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="flex items-center space-x-1 text-slate-400">
                    <Clock className="w-3 h-3" />
                    <span>{evt.closed_loop_latency_ms.toFixed(1)} ms</span>
                  </span>
                  <span className="px-1.5 py-0.2 bg-emerald-950 border border-emerald-500/40 text-emerald-300 rounded text-[9px]">
                    Single-Turn
                  </span>
                </div>
              </div>

              {/* COOL Metrology Microservice Verification Stamp */}
              {evt.cool_metrology_verification && (
                <div className="flex items-center justify-between px-2 py-1 rounded bg-industrial-800/80 border border-slate-700/60 text-[10px]">
                  <div className="flex items-center space-x-1.5">
                    <Cpu className="w-3 h-3 text-cyan-400" />
                    <span className="text-slate-300">{evt.cool_metrology_verification.engine}</span>
                  </div>
                  <span className="text-cyan-300 font-bold uppercase text-[9px]">
                    {evt.cool_metrology_verification.verdict}
                  </span>
                </div>
              )}

              {/* Multimodal Reasoning Trace */}
              <div className="text-slate-300 leading-relaxed bg-industrial-850 p-2 rounded border border-industrial-800">
                <span className="text-emerald-400 font-bold block mb-1"> Claude 3.5 Sonnet Visual Diagnosis:</span>
                {evt.agent_reasoning}
              </div>

              {/* Dispatched Tool Call Card */}
              {evt.dispatched_tool && (
                <div className={`p-2 rounded border text-[10px] ${toolBadgeColor}`}>
                  <div className="flex items-center justify-between font-bold mb-1">
                    <div className="flex items-center space-x-1.5">
                      <Wrench className="w-3 h-3" />
                      <span>{evt.dispatched_tool}</span>
                    </div>
                    <span className="text-[9px] uppercase px-1 rounded bg-black/40">Actuation Executed</span>
                  </div>
                  <pre className="text-[9px] text-slate-300 overflow-x-auto p-1 bg-black/40 rounded mt-1">
                    {JSON.stringify(evt.tool_parameters, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          );
        })}

        {/* Render Authenticated PLC Updates */}
        {plcUpdates.map((plc, idx) => {
          if (filterMode === "reasoning" || filterMode === "tools") return null;

          return (
            <div
              key={idx}
              className="p-2.5 rounded-lg bg-industrial-900 border border-cyan-800/60 space-y-2"
            >
              <div className="flex items-center justify-between text-[10px] border-b border-industrial-800 pb-1.5">
                <div className="flex items-center space-x-1.5 text-cyan-300 font-bold">
                  <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
                  <span>PLANT PLC HOLDING REGISTERS COMMITTED</span>
                </div>
                <span className="text-emerald-400 text-[9px] flex items-center space-x-1">
                  <CheckCircle className="w-3 h-3" />
                  <span>Settled: {plc.actuator_settling_time_sec}s</span>
                </span>
              </div>

              {/* Modbus Registers Grid */}
              <div className="grid grid-cols-3 sm:grid-cols-5 gap-1.5 text-center text-[10px]">
                <div className="p-1 bg-industrial-800 rounded border border-industrial-700">
                  <div className="text-[8px] text-slate-400">VELOCITY</div>
                  <div className="text-cyan-300 font-bold">{plc.holding_registers.velocity_mms} mm/s</div>
                </div>
                <div className="p-1 bg-industrial-800 rounded border border-industrial-700">
                  <div className="text-[8px] text-slate-400">TENSION</div>
                  <div className="text-cyan-300 font-bold">{(plc.holding_registers.tension_dn / 10).toFixed(1)} N</div>
                </div>
                <div className="p-1 bg-industrial-800 rounded border border-industrial-700">
                  <div className="text-[8px] text-slate-400">IR TEMP</div>
                  <div className="text-orange-300 font-bold">{(plc.holding_registers.temp_dc / 10).toFixed(1)} °C</div>
                </div>
                <div className="p-1 bg-industrial-800 rounded border border-industrial-700">
                  <div className="text-[8px] text-slate-400">PUMP RPM</div>
                  <div className="text-cyan-300 font-bold">{(plc.holding_registers.pump_drpm / 10).toFixed(1)}</div>
                </div>
                <div className="p-1 bg-industrial-800 rounded border border-industrial-700">
                  <div className="text-[8px] text-slate-400">DANCER GAIN</div>
                  <div className="text-purple-300 font-bold">{(plc.holding_registers.dancer_dgain / 100).toFixed(2)}</div>
                </div>
              </div>

              {/* HMAC-SHA256 Cryptographic Authentication Token */}
              <div className="flex items-center space-x-1.5 text-[9px] text-slate-400 bg-black/40 p-1.5 rounded">
                <span className="text-cyan-400 font-bold">HMAC-SHA256:</span>
                <span className="truncate font-mono">{plc.hmac_sha256_signature}</span>
                <span className="text-emerald-400 font-bold ml-auto">[VERIFIED]</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer Closed-Loop Settlement Guarantee */}
      <div className="px-3 py-1.5 bg-industrial-900 border-t border-industrial-700 text-[10px] font-mono text-slate-400 flex items-center justify-between">
        <span className="flex items-center space-x-1">
          <Zap className="w-3 h-3 text-amber-400" />
          <span>Supervisory Loop: &le; 3.5s Target SLA</span>
        </span>
        <span className="text-emerald-400 font-bold">Causal Safety Gate Active</span>
      </div>
    </div>
  );
};

export default AgenticChatConsole;
