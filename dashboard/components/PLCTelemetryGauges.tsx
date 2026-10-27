import React from "react";
import { Gauge, Flame, Activity, ShieldAlert, Cpu } from "lucide-react";
import { TelemetryData } from "./VideoInspectionFeed";

interface PLCTelemetryGaugesProps {
  telemetry: TelemetryData;
  defectCount: number;
  estopArmed?: boolean;
}

export const PLCTelemetryGauges: React.FC<PLCTelemetryGaugesProps> = ({
  telemetry,
  defectCount,
  estopArmed = true,
}) => {
  const speed = telemetry.line_speed_mps || 2.50;
  const tension = telemetry.tension_newtons || 150.0;
  const temp = telemetry.dryer_temp_c || 120.0;
  const pumpRpm = telemetry.pump_rpm || 1200.0;

  // Percentage calculations against operating envelope
  const speedPct = Math.min(100, Math.max(0, ((speed - 2.0) / 1.0) * 100));
  const tensionPct = Math.min(100, Math.max(0, ((tension - 120.0) / 60.0) * 100));
  const tempPct = Math.min(100, Math.max(0, ((temp - 80.0) / 60.0) * 100));
  const pumpPct = Math.min(100, Math.max(0, ((pumpRpm - 900.0) / 600.0) * 100));

  return (
    <div className="flex flex-col bg-industrial-850 border border-industrial-700 rounded-lg overflow-hidden shadow-xl">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-industrial-900 border-b border-industrial-700">
        <div className="flex items-center space-x-2">
          <Gauge className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-mono font-bold tracking-wider text-slate-200 uppercase">
            Cyber-Physical Modbus Telemetry Gauges (Port 5020)
          </span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-500/30 font-bold">
            {estopArmed ? "GPIO E-STOP: ARMED (<5ms)" : "GPIO TRIP"}
          </span>
        </div>
      </div>

      {/* Grid of Gauges */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3 font-mono">
        {/* Gauge 1: Line Speed */}
        <div className="flex flex-col items-center justify-center p-2.5 rounded-lg bg-industrial-900 border border-industrial-700 relative overflow-hidden">
          <div className="flex items-center space-x-1 text-[10px] text-slate-400 mb-1">
            <Activity className="w-3 h-3 text-cyan-400" />
            <span>LINE VELOCITY</span>
          </div>
          <div className="text-xl font-bold text-cyan-300">
            {speed.toFixed(2)}{" "}
            <span className="text-[10px] font-normal text-slate-400">m/s</span>
          </div>
          <div className="text-[9px] text-slate-500 mt-0.5">
            {(speed * 60).toFixed(0)} m/min (Nom: 2.50)
          </div>
          <div className="w-full bg-industrial-800 h-1.5 rounded-full mt-2 overflow-hidden">
            <div
              className="bg-cyan-400 h-full transition-all duration-300"
              style={{ width: `${speedPct}%` }}
            />
          </div>
        </div>

        {/* Gauge 2: Web Tension */}
        <div className="flex flex-col items-center justify-center p-2.5 rounded-lg bg-industrial-900 border border-industrial-700 relative overflow-hidden">
          <div className="flex items-center space-x-1 text-[10px] text-slate-400 mb-1">
            <Gauge className="w-3 h-3 text-cyan-400" />
            <span>WEB TENSION</span>
          </div>
          <div className="text-xl font-bold text-cyan-300">
            {tension.toFixed(1)}{" "}
            <span className="text-[10px] font-normal text-slate-400">N</span>
          </div>
          <div className="text-[9px] text-slate-500 mt-0.5">
            Dancer Gain: {telemetry.dancer_damping_gain.toFixed(2)}
          </div>
          <div className="w-full bg-industrial-800 h-1.5 rounded-full mt-2 overflow-hidden">
            <div
              className="bg-cyan-400 h-full transition-all duration-300"
              style={{ width: `${tensionPct}%` }}
            />
          </div>
        </div>

        {/* Gauge 3: IR Dryer Temp */}
        <div className="flex flex-col items-center justify-center p-2.5 rounded-lg bg-industrial-900 border border-industrial-700 relative overflow-hidden">
          <div className="flex items-center space-x-1 text-[10px] text-slate-400 mb-1">
            <Flame className="w-3 h-3 text-orange-400" />
            <span>IR DRYER ZONE 1</span>
          </div>
          <div className="text-xl font-bold text-orange-400">
            {temp.toFixed(1)}{" "}
            <span className="text-[10px] font-normal text-slate-400">°C</span>
          </div>
          <div className="text-[9px] text-slate-500 mt-0.5">
            Thermodynamic Loop (120°C)
          </div>
          <div className="w-full bg-industrial-800 h-1.5 rounded-full mt-2 overflow-hidden">
            <div
              className="bg-orange-500 h-full transition-all duration-300"
              style={{ width: `${tempPct}%` }}
            />
          </div>
        </div>

        {/* Gauge 4: Slurry Pump RPM */}
        <div className="flex flex-col items-center justify-center p-2.5 rounded-lg bg-industrial-900 border border-industrial-700 relative overflow-hidden">
          <div className="flex items-center space-x-1 text-[10px] text-slate-400 mb-1">
            <Cpu className="w-3 h-3 text-cyan-400" />
            <span>SLURRY PUMP</span>
          </div>
          <div className="text-xl font-bold text-cyan-300">
            {pumpRpm.toFixed(0)}{" "}
            <span className="text-[10px] font-normal text-slate-400">RPM</span>
          </div>
          <div className="text-[9px] text-slate-500 mt-0.5">
            Fluid Metering Servo
          </div>
          <div className="w-full bg-industrial-800 h-1.5 rounded-full mt-2 overflow-hidden">
            <div
              className="bg-cyan-400 h-full transition-all duration-300"
              style={{ width: `${pumpPct}%` }}
            />
          </div>
        </div>
      </div>

      {/* Footer Banner: Cumulative Defect Counter */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-industrial-900 border-t border-industrial-700 text-[10px] font-mono">
        <div className="flex items-center space-x-2">
          <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
          <span className="text-slate-300">Cumulative Defects Intercepted:</span>
          <span className="px-1.5 py-0.2 bg-amber-950 text-amber-300 rounded font-bold border border-amber-500/30">
            {defectCount}
          </span>
        </div>
        <div className="flex items-center space-x-2 text-slate-400">
          <span>Modbus TCP S7-1500:</span>
          <span className="text-emerald-400 font-bold">Registers 40001 - 40005 Synchronized</span>
        </div>
      </div>
    </div>
  );
};

export default PLCTelemetryGauges;
