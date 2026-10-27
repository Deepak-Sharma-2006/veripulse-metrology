import React from "react";
import { Gauge, Flame, Activity, ShieldAlert, Cpu, CheckCircle2, RotateCcw } from "lucide-react";
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

  // Percentage calculations against standard manufacturing envelope
  const speedPct = Math.min(100, Math.max(0, ((speed - 2.0) / 1.0) * 100));
  const tensionPct = Math.min(100, Math.max(0, ((tension - 120.0) / 60.0) * 100));
  const tempPct = Math.min(100, Math.max(0, ((temp - 80.0) / 60.0) * 100));
  const pumpPct = Math.min(100, Math.max(0, ((pumpRpm - 900.0) / 600.0) * 100));

  const isSpeedAdjusted = Math.abs(speed - 2.50) > 0.04;

  return (
    <div className="flex flex-col bg-slate-900 border border-slate-800 rounded-lg overflow-hidden shadow-lg">
      {/* Precision Header */}
      <div className="flex items-center justify-between px-3.5 py-2.5 bg-slate-950/80 border-b border-slate-800">
        <div className="flex items-center space-x-2.5">
          <Gauge className="w-4 h-4 text-sky-400" />
          <span className="text-xs font-semibold tracking-wide text-slate-100">
            SCADA Modbus Setpoints & Actuators
          </span>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
            Port 5020 • Siemens S7-1500
          </span>
        </div>

        <div className="flex items-center space-x-2">
          <span
            className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold border ${
              estopArmed
                ? "bg-emerald-950/80 text-emerald-400 border-emerald-800/60"
                : "bg-red-950/80 text-red-400 border-red-800/60"
            }`}
          >
            {estopArmed ? "GPIO FAIL-SAFE: ARMED (<5ms)" : "E-STOP TRIPPED"}
          </span>
        </div>
      </div>

      {/* Grid of Precision Gauges */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3 font-mono">
        {/* Gauge 1: Line Speed */}
        <div className="flex flex-col justify-between p-3 rounded-lg bg-slate-950/70 border border-slate-800 relative overflow-hidden">
          <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1 font-sans">
            <span className="font-semibold text-slate-300">Line Velocity</span>
            <span className="text-[9px] font-mono text-slate-500">40001</span>
          </div>

          <div className="my-1">
            <div className="text-2xl font-bold tracking-tight text-slate-100">
              {speed.toFixed(2)}{" "}
              <span className="text-xs font-normal text-slate-400">m/s</span>
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5 flex items-center space-x-1">
              <span>{(speed * 60).toFixed(0)} m/min</span>
              {isSpeedAdjusted && (
                <span className="text-amber-400 font-semibold">(Bedrock Settled)</span>
              )}
            </div>
          </div>

          <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
            <div
              className={`h-full transition-all duration-300 ${isSpeedAdjusted ? "bg-amber-400" : "bg-sky-400"}`}
              style={{ width: `${speedPct}%` }}
            />
          </div>
        </div>

        {/* Gauge 2: Web Tension */}
        <div className="flex flex-col justify-between p-3 rounded-lg bg-slate-950/70 border border-slate-800 relative overflow-hidden">
          <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1 font-sans">
            <span className="font-semibold text-slate-300">Web Tension</span>
            <span className="text-[9px] font-mono text-slate-500">40002</span>
          </div>

          <div className="my-1">
            <div className="text-2xl font-bold tracking-tight text-slate-100">
              {tension.toFixed(1)}{" "}
              <span className="text-xs font-normal text-slate-400">N</span>
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">
              Dancer Gain: <strong className="text-slate-200">{telemetry.dancer_damping_gain.toFixed(2)}</strong>
            </div>
          </div>

          <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
            <div
              className="bg-sky-400 h-full transition-all duration-300"
              style={{ width: `${tensionPct}%` }}
            />
          </div>
        </div>

        {/* Gauge 3: IR Dryer Temp */}
        <div className="flex flex-col justify-between p-3 rounded-lg bg-slate-950/70 border border-slate-800 relative overflow-hidden">
          <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1 font-sans">
            <span className="font-semibold text-slate-300">Dryer Zone 1</span>
            <span className="text-[9px] font-mono text-slate-500">40003</span>
          </div>

          <div className="my-1">
            <div className="text-2xl font-bold tracking-tight text-amber-400">
              {temp.toFixed(1)}{" "}
              <span className="text-xs font-normal text-slate-400">°C</span>
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">
              Target: 120.0 °C (±1.5°C)
            </div>
          </div>

          <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
            <div
              className="bg-amber-500 h-full transition-all duration-300"
              style={{ width: `${tempPct}%` }}
            />
          </div>
        </div>

        {/* Gauge 4: Slurry Pump Speed */}
        <div className="flex flex-col justify-between p-3 rounded-lg bg-slate-950/70 border border-slate-800 relative overflow-hidden">
          <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1 font-sans">
            <span className="font-semibold text-slate-300">Slurry Pump</span>
            <span className="text-[9px] font-mono text-slate-500">40004</span>
          </div>

          <div className="my-1">
            <div className="text-2xl font-bold tracking-tight text-slate-100">
              {pumpRpm.toFixed(0)}{" "}
              <span className="text-xs font-normal text-slate-400">RPM</span>
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">
              Hydraulic Metering Servo
            </div>
          </div>

          <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
            <div
              className="bg-sky-400 h-full transition-all duration-300"
              style={{ width: `${pumpPct}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
};
