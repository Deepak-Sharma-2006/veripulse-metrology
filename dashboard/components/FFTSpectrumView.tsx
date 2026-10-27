import React, { useEffect, useRef } from "react";
import { Activity, AlertOctagon, CheckCircle2, Radio } from "lucide-react";

interface FFTSpectrumViewProps {
  spectrumData: number[]; // 512 normalized float bins
}

export const FFTSpectrumView: React.FC<FFTSpectrumViewProps> = ({ spectrumData }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Peak harmonic detections
  const bin14Power = spectrumData && spectrumData.length > 14 ? spectrumData[14] : 0.28;
  const bin142Power = spectrumData && spectrumData.length > 142 ? spectrumData[142] : 0.08;
  const isRibbingResonant = bin142Power > 0.45;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;

    // Dark slate background
    ctx.fillStyle = "#020617";
    ctx.fillRect(0, 0, w, h);

    // Subtle Grid lines (dB power intervals: -64dB, -48dB, -32dB, -16dB, 0dB)
    ctx.strokeStyle = "rgba(30, 41, 59, 0.40)";
    ctx.lineWidth = 1;
    const dbSteps = [0.2, 0.4, 0.6, 0.8];
    dbSteps.forEach((step) => {
      const y = h - step * (h - 28) - 16;
      ctx.beginPath();
      ctx.moveTo(38, y);
      ctx.lineTo(w - 12, y);
      ctx.stroke();

      ctx.fillStyle = "#64748b";
      ctx.font = "9px monospace";
      const dbVal = Math.round((step - 1.0) * 80);
      ctx.fillText(`${dbVal} dB`, 4, y + 3);
    });

    // Draw spectrum bars
    const bins = spectrumData.length > 0 ? spectrumData : new Array(512).fill(0.02);
    const visibleBins = Math.min(bins.length, 300); // Focus on 0 - 300 Hz
    const barWidth = (w - 50) / visibleBins;

    for (let i = 0; i < visibleBins; i++) {
      const val = Math.min(1.0, Math.max(0.015, bins[i]));
      const barH = val * (h - 38);
      const x = 38 + i * barWidth;
      const y = h - 20 - barH;

      // Color coding based on frequency zone
      if (Math.abs(i - 142) <= 3) {
        ctx.fillStyle = isRibbingResonant ? "#f59e0b" : "#38bdf8";
      } else if (Math.abs(i - 14) <= 2) {
        ctx.fillStyle = "#c084fc"; // 14.25 Hz mechanical runout
      } else if (Math.abs(i - 285) <= 3 && isRibbingResonant) {
        ctx.fillStyle = "#f59e0b"; // 2nd Harmonic
      } else {
        ctx.fillStyle = "rgba(56, 189, 248, 0.35)";
      }

      ctx.fillRect(x, y, Math.max(1, barWidth - 0.5), barH);
    }

    // Callout Marker: 14.25 Hz Temporal Runout
    const x14 = 38 + 14 * barWidth;
    ctx.strokeStyle = "rgba(192, 132, 252, 0.60)";
    ctx.setLineDash([2, 2]);
    ctx.beginPath();
    ctx.moveTo(x14, 12);
    ctx.lineTo(x14, h - 20);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#c084fc";
    ctx.font = "bold 9px monospace";
    ctx.fillText("14.25 Hz (Runout)", Math.max(40, x14 - 36), 22);

    // Callout Marker: 142.5 Hz Fundamental Ribbing
    const x142 = 38 + 142 * barWidth;
    ctx.strokeStyle = isRibbingResonant ? "#f59e0b" : "rgba(56, 189, 248, 0.70)";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([3, 2]);
    ctx.beginPath();
    ctx.moveTo(x142, 8);
    ctx.lineTo(x142, h - 20);
    ctx.stroke();
    ctx.setLineDash([]);

    // Callout Pill on Ribbing Marker
    ctx.fillStyle = isRibbingResonant ? "#f59e0b" : "#38bdf8";
    ctx.font = "bold 9px monospace";
    ctx.fillText(
      `142.5 Hz [${(bin142Power * 60 - 20).toFixed(1)} dB]`,
      Math.max(40, x142 - 45),
      isRibbingResonant ? 16 : 24
    );

    // Bottom Frequency Axis Labels
    ctx.fillStyle = "#64748b";
    ctx.font = "9px monospace";
    [0, 50, 100, 150, 200, 250].forEach((freq) => {
      const xPos = 38 + freq * barWidth;
      ctx.fillText(`${freq}Hz`, xPos - 8, h - 6);
    });
  }, [spectrumData, bin14Power, bin142Power, isRibbingResonant]);

  return (
    <div className="flex flex-col h-full min-h-0 bg-slate-900 border border-slate-800 rounded-lg overflow-hidden shadow-lg">
      {/* Precision Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-slate-950/80 border-b border-slate-800 shrink-0">
        <div className="flex items-center space-x-2.5">
          <Activity className="w-4 h-4 text-sky-400" />
          <span className="text-xs font-semibold tracking-wide text-slate-100">
            Spatial 2D-FFT Harmonics Analyzer
          </span>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
            512 Bins • AVX2
          </span>
        </div>

        <div className="flex items-center space-x-2">
          {isRibbingResonant ? (
            <span className="flex items-center space-x-1.5 px-2 py-0.5 rounded bg-amber-950/80 text-amber-300 border border-amber-800/60 text-[10px] font-mono font-semibold animate-pulse">
              <AlertOctagon className="w-3 h-3 text-amber-400" />
              <span>RESONANCE DETECTED (142.5 Hz)</span>
            </span>
          ) : (
            <span className="flex items-center space-x-1.5 px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800/60 text-[10px] font-mono font-medium">
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              <span>HARMONICS NOMINAL</span>
            </span>
          )}
        </div>
      </div>

      {/* Main Canvas Area */}
      <div className="relative flex-1 min-h-0 bg-slate-950 p-1.5 flex items-center justify-center overflow-hidden">
        <canvas
          ref={canvasRef}
          width={560}
          height={210}
          className="w-full h-full object-contain block"
        />
      </div>

      {/* Harmonic Spectral Breakdown Footer */}
      <div className="grid grid-cols-3 gap-2 px-3 py-1.5 bg-slate-950 border-t border-slate-800 text-[10px] font-mono shrink-0">
        <div className="flex flex-col">
          <span className="text-[10px] text-slate-500 font-sans font-medium">14.25 Hz Mechanical Runout</span>
          <span className="text-purple-400 font-semibold font-mono">{(bin14Power * 100).toFixed(1)}% Amp</span>
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] text-slate-500 font-sans font-medium">142.5 Hz Fundamental Ribbing</span>
          <span className={isRibbingResonant ? "text-amber-400 font-bold" : "text-sky-400 font-semibold"}>
            {(bin142Power * 100).toFixed(1)}% (λ = 17.54mm)
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] text-slate-500 font-sans font-medium">285.0 Hz 2nd Harmonic</span>
          <span className="text-slate-400 font-semibold">
            {spectrumData && spectrumData.length > 285 ? (spectrumData[285] * 30).toFixed(1) : "12.4"} dB
          </span>
        </div>
      </div>
    </div>
  );
};
