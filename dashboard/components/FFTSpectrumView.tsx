import React, { useEffect, useRef } from "react";
import { Activity, AlertOctagon, CheckCircle2 } from "lucide-react";

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

    // Background
    ctx.fillStyle = "#0a0d14";
    ctx.fillRect(0, 0, w, h);

    // Grid lines (dB power intervals: -60dB, -40dB, -20dB, 0dB)
    ctx.strokeStyle = "rgba(30, 41, 59, 0.45)";
    ctx.lineWidth = 1;
    const dbSteps = [0.2, 0.4, 0.6, 0.8];
    dbSteps.forEach((step) => {
      const y = h - step * (h - 25) - 15;
      ctx.beginPath();
      ctx.moveTo(35, y);
      ctx.lineTo(w - 10, y);
      ctx.stroke();

      ctx.fillStyle = "#64748b";
      ctx.font = "9px monospace";
      const dbVal = Math.round((step - 1.0) * 80);
      ctx.fillText(`${dbVal} dB`, 4, y + 3);
    });

    // Draw spectrum bars
    const bins = spectrumData.length > 0 ? spectrumData : new Array(512).fill(0.02);
    const visibleBins = Math.min(bins.length, 300); // Focus on 0 - 300 Hz
    const barWidth = (w - 45) / visibleBins;

    for (let i = 0; i < visibleBins; i++) {
      const val = Math.min(1.0, Math.max(0.01, bins[i]));
      const barH = val * (h - 35);
      const x = 35 + i * barWidth;
      const y = h - 20 - barH;

      // Color coding based on frequency zone
      if (Math.abs(i - 142) <= 3) {
        ctx.fillStyle = isRibbingResonant ? "#f59e0b" : "#06b6d4";
      } else if (Math.abs(i - 14) <= 2) {
        ctx.fillStyle = "#a855f7"; // 14.25 Hz runout
      } else if (Math.abs(i - 285) <= 3 && isRibbingResonant) {
        ctx.fillStyle = "#f59e0b";
      } else {
        ctx.fillStyle = "rgba(34, 211, 238, 0.45)";
      }

      ctx.fillRect(x, y, Math.max(1, barWidth - 0.5), barH);
    }

    // Callout Marker: 14.25 Hz Temporal Runout
    const x14 = 35 + 14 * barWidth;
    ctx.strokeStyle = "#c084fc";
    ctx.setLineDash([2, 2]);
    ctx.beginPath();
    ctx.moveTo(x14, 10);
    ctx.lineTo(x14, h - 20);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#c084fc";
    ctx.font = "bold 9px monospace";
    ctx.fillText("14.25Hz (Runout)", Math.max(38, x14 - 35), 22);

    // Callout Marker: 142.5 Hz Fundamental Ribbing
    const x142 = 35 + 142 * barWidth;
    ctx.strokeStyle = isRibbingResonant ? "#f59e0b" : "#22d3ee";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([3, 2]);
    ctx.beginPath();
    ctx.moveTo(x142, 8);
    ctx.lineTo(x142, h - 20);
    ctx.stroke();
    ctx.setLineDash([]);

    // Warning Badge on Ribbing Marker
    ctx.fillStyle = isRibbingResonant ? "#f59e0b" : "#22d3ee";
    ctx.font = "bold 9px monospace";
    ctx.fillText(
      `142.5Hz [${(bin142Power * 60 - 20).toFixed(1)} dB]`,
      x142 - 40,
      14
    );

    // Frequency Axis labels
    ctx.fillStyle = "#64748b";
    ctx.font = "9px monospace";
    [0, 50, 100, 150, 200, 250].forEach((hz) => {
      const x = 35 + hz * barWidth;
      ctx.fillText(`${hz}Hz`, x - 8, h - 5);
    });

  }, [spectrumData, bin14Power, bin142Power, isRibbingResonant]);

  return (
    <div className="flex flex-col bg-industrial-850 border border-industrial-700 rounded-lg overflow-hidden shadow-xl">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-industrial-900 border-b border-industrial-700">
        <div className="flex items-center space-x-2">
          <Activity className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-mono font-bold tracking-wider text-slate-200 uppercase">
            Spatial 2D-FFT Harmonics Analyzer (512 Bins)
          </span>
        </div>
        <div className="flex items-center space-x-2">
          {isRibbingResonant ? (
            <div className="flex items-center space-x-1.5 px-2 py-0.5 bg-amber-500/20 border border-amber-500/50 rounded text-[10px] font-mono text-amber-300 font-bold animate-pulse">
              <AlertOctagon className="w-3 h-3 text-amber-400" />
              <span>142.5 HZ RIBBING DETECTED</span>
            </div>
          ) : (
            <div className="flex items-center space-x-1 px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/30 rounded text-[10px] font-mono text-emerald-400">
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              <span>HARMONICS NOMINAL</span>
            </div>
          )}
        </div>
      </div>

      {/* Canvas Spectrum Display */}
      <div className="relative w-full aspect-[21/9] bg-black overflow-hidden flex items-center justify-center p-1">
        <canvas
          ref={canvasRef}
          width={600}
          height={180}
          className="w-full h-full object-contain"
        />
      </div>

      {/* Footer Metrics Breakdown */}
      <div className="grid grid-cols-3 divide-x divide-industrial-700 bg-industrial-900 border-t border-industrial-700 text-[11px] font-mono py-1.5 px-2">
        <div className="flex flex-col items-center">
          <span className="text-[9px] text-slate-400 uppercase">14.25 Hz Runout</span>
          <span className="text-purple-400 font-bold">{(bin14Power * 100).toFixed(1)}% Amp</span>
        </div>
        <div className="flex flex-col items-center">
          <span className="text-[9px] text-slate-400 uppercase">142.5 Hz Fundamental</span>
          <span className={isRibbingResonant ? "text-amber-400 font-bold" : "text-cyan-400 font-bold"}>
            {(bin142Power * 100).toFixed(1)}% (λ = 17.54mm)
          </span>
        </div>
        <div className="flex flex-col items-center">
          <span className="text-[9px] text-slate-400 uppercase">285.0 Hz 2nd Order</span>
          <span className="text-slate-300 font-bold">
            {isRibbingResonant ? "36.8 dB" : "12.4 dB"}
          </span>
        </div>
      </div>
    </div>
  );
};

export default FFTSpectrumView;
