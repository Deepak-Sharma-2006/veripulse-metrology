import React, { useEffect, useRef, useState } from "react";
import { Eye, Crosshair, ZoomIn, AlertTriangle, ShieldCheck } from "lucide-react";

export interface TelemetryData {
  line_speed_mps: number;
  tension_newtons: number;
  dryer_temp_c: number;
  pump_rpm: number;
  dancer_damping_gain: number;
}

export interface ActiveAlert {
  detected: boolean;
  defect_type: string;
  severity: string;
  bounding_box: { x: number; y: number; width: number; height: number } | null;
}

interface VideoInspectionFeedProps {
  telemetryRef: React.MutableRefObject<TelemetryData>;
  alertRef: React.MutableRefObject<ActiveAlert | null>;
  fps?: number;
}

export const VideoInspectionFeed: React.FC<VideoInspectionFeedProps> = ({
  telemetryRef,
  alertRef,
  fps = 120.0,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [viewMode, setViewMode] = useState<"optical" | "sobel" | "thermal">("optical");
  const [zoomLevel, setZoomLevel] = useState<number>(1.0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) return;

    let animationFrameId: number;
    let offset = 0;
    let lastTime = performance.now();
    let frameCounter = 0;
    let actualFps = fps;
    let lastFpsUpdate = performance.now();

    const renderLoop = (time: number) => {
      const dt = (time - lastTime) / 1000;
      lastTime = time;

      // Update actual FPS metric once every 500ms
      frameCounter++;
      if (time - lastFpsUpdate >= 500) {
        actualFps = Math.round((frameCounter * 1000) / (time - lastFpsUpdate));
        frameCounter = 0;
        lastFpsUpdate = time;
      }

      const speed = telemetryRef.current.line_speed_mps || 2.50;
      const activeAlert = alertRef.current;
      const hasAlert = activeAlert?.detected;

      // Substrate translation speed proportional to line speed
      offset = (offset + speed * 120 * dt) % 100;

      const w = canvas.width;
      const h = canvas.height;

      // Direct Canvas Painting (Zero React State Jitter)
      ctx.fillStyle = viewMode === "thermal" ? "#1e0b24" : "#0d131a";
      ctx.fillRect(0, 0, w, h);

      // Render Lithium Anode Carbon Slurry / Copper Substrate
      const stripeSpacing = 24 * zoomLevel;
      ctx.lineWidth = 1;

      for (let x = -stripeSpacing + (offset % stripeSpacing); x < w + stripeSpacing; x += stripeSpacing) {
        if (viewMode === "thermal") {
          ctx.strokeStyle = "rgba(236, 72, 153, 0.15)";
        } else if (viewMode === "sobel") {
          ctx.strokeStyle = "rgba(34, 211, 238, 0.20)";
        } else {
          ctx.strokeStyle = "rgba(71, 85, 105, 0.25)";
        }
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }

      // Slot-die coating texture grain
      const grainCount = 35;
      for (let i = 0; i < grainCount; i++) {
        const seedX = ((i * 137.5 + offset * 2.5) % (w - 20)) + 10;
        const seedY = (i * 31.7) % (h - 20) + 10;
        ctx.fillStyle = viewMode === "thermal" ? "rgba(244, 63, 94, 0.35)" : "rgba(148, 163, 184, 0.25)";
        ctx.fillRect(seedX, seedY, 3 * zoomLevel, 1);
      }

      // 142.5 Hz slot-die ribbing visual waves if ribbing alert active
      if (hasAlert && activeAlert?.defect_type?.includes("ribbing")) {
        ctx.strokeStyle = "rgba(245, 158, 11, 0.65)";
        ctx.lineWidth = 2;
        const waveStep = 18;
        for (let x = 0; x < w; x += waveStep) {
          ctx.beginPath();
          for (let y = 0; y < h; y += 10) {
            const waveOffset = Math.sin((y * 0.08) + (time * 0.015)) * 6;
            if (y === 0) ctx.moveTo(x + waveOffset, y);
            else ctx.lineTo(x + waveOffset, y);
          }
          ctx.stroke();
        }
      }

      // Specular copper foil glare patch
      if (hasAlert && activeAlert?.defect_type?.includes("reflectance")) {
        const grad = ctx.createRadialGradient(w * 0.45, h * 0.4, 10, w * 0.45, h * 0.4, 90);
        grad.addColorStop(0, "rgba(255, 237, 213, 0.85)");
        grad.addColorStop(0.5, "rgba(251, 146, 60, 0.45)");
        grad.addColorStop(1, "rgba(251, 146, 60, 0)");
        ctx.fillStyle = grad;
        ctx.fillRect(w * 0.25, h * 0.2, w * 0.4, h * 0.4);
      }

      // Sub-Pixel Laser Inspection Scanning Line (Green Neon)
      const laserX = (w * 0.5) + Math.sin(time * 0.003) * (w * 0.42);
      ctx.strokeStyle = "#10b981";
      ctx.lineWidth = 1.5;
      ctx.shadowColor = "#10b981";
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.moveTo(laserX, 0);
      ctx.lineTo(laserX, h);
      ctx.stroke();
      ctx.shadowBlur = 0; // Reset shadow

      // Defect Micro-Bounding Box Overlay
      if (hasAlert && activeAlert?.bounding_box) {
        const boxX = w * 0.38;
        const boxY = h * 0.32;
        const boxW = 140 * zoomLevel;
        const boxH = 65 * zoomLevel;

        ctx.strokeStyle = activeAlert.severity === "CRITICAL" ? "#ef4444" : "#f59e0b";
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 4]);
        ctx.strokeRect(boxX, boxY, boxW, boxH);
        ctx.setLineDash([]);

        // Defect Tag Label
        ctx.fillStyle = activeAlert.severity === "CRITICAL" ? "rgba(239, 68, 68, 0.85)" : "rgba(245, 158, 11, 0.85)";
        ctx.fillRect(boxX, boxY - 20, boxW, 18);
        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 9px monospace";
        ctx.fillText(
          `${activeAlert.defect_type.substring(0, 18)} [+-2.44um]`,
          boxX + 4,
          boxY - 7
        );
      }

      // High-Precision Edge Sub-Pixel Crosshairs
      ctx.strokeStyle = "rgba(6, 182, 212, 0.4)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(w / 2 - 15, h / 2);
      ctx.lineTo(w / 2 + 15, h / 2);
      ctx.moveTo(w / 2, h / 2 - 15);
      ctx.lineTo(w / 2, h / 2 + 15);
      ctx.stroke();

      // Top-Left Optical HUD Metrics
      ctx.fillStyle = "rgba(10, 13, 20, 0.75)";
      ctx.fillRect(8, 8, 210, 68);
      ctx.strokeStyle = "rgba(30, 41, 59, 0.8)";
      ctx.strokeRect(8, 8, 210, 68);

      ctx.fillStyle = "#22d3ee";
      ctx.font = "bold 11px monospace";
      ctx.fillText(`SENSOR: 2048x2048 @ ${actualFps} FPS`, 14, 24);

      ctx.fillStyle = "#94a3b8";
      ctx.font = "10px monospace";
      ctx.fillText(`RES: 24.414 um/px | FOV: 50.0mm`, 14, 39);
      ctx.fillText(`SUBPIXEL: +-2.44 um (Scharr G-API)`, 14, 53);
      ctx.fillText(`WEB VEL: ${speed.toFixed(2)} m/s (150 m/min)`, 14, 67);

      animationFrameId = requestAnimationFrame(renderLoop);
    };

    animationFrameId = requestAnimationFrame(renderLoop);
    return () => cancelAnimationFrame(animationFrameId);
  }, [viewMode, zoomLevel, fps]);

  return (
    <div className="flex flex-col bg-industrial-850 border border-industrial-700 rounded-lg overflow-hidden shadow-xl">
      {/* Header Bar */}
      <div className="flex items-center justify-between px-3 py-2 bg-industrial-900 border-b border-industrial-700">
        <div className="flex items-center space-x-2">
          <Eye className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-mono font-bold tracking-wider text-slate-200 uppercase">
            Optical High-Speed Ingestion (120 FPS Direct Canvas)
          </span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="flex items-center bg-industrial-800 rounded p-0.5 border border-industrial-700 text-[10px] font-mono">
            <button
              onClick={() => setViewMode("optical")}
              className={`px-2 py-0.5 rounded transition ${
                viewMode === "optical" ? "bg-cyan-500 text-slate-950 font-bold" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Optical
            </button>
            <button
              onClick={() => setViewMode("sobel")}
              className={`px-2 py-0.5 rounded transition ${
                viewMode === "sobel" ? "bg-cyan-500 text-slate-950 font-bold" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Sobel
            </button>
            <button
              onClick={() => setViewMode("thermal")}
              className={`px-2 py-0.5 rounded transition ${
                viewMode === "thermal" ? "bg-pink-500 text-slate-950 font-bold" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              IR Thermal
            </button>
          </div>
          <button
            onClick={() => setZoomLevel((z) => (z >= 2.0 ? 1.0 : z + 0.5))}
            className="flex items-center space-x-1 px-2 py-0.5 bg-industrial-800 hover:bg-industrial-700 text-slate-300 rounded border border-industrial-700 text-[10px] font-mono"
            title="Toggle Inspection Zoom"
          >
            <ZoomIn className="w-3 h-3 text-cyan-400" />
            <span>{zoomLevel.toFixed(1)}x</span>
          </button>
        </div>
      </div>

      {/* Main Canvas Viewport */}
      <div className="relative w-full aspect-[16/10] bg-black overflow-hidden flex items-center justify-center">
        <canvas
          ref={canvasRef}
          width={640}
          height={400}
          className="w-full h-full object-cover"
        />

        {/* Scanline CRT FX */}
        <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_center,transparent_0%,rgba(0,0,0,0.4)_100%)]" />

        {/* Live Status Pill */}
        <div className="absolute bottom-2 right-2 flex items-center space-x-1.5 px-2 py-0.5 bg-industrial-900/90 border border-industrial-700/80 rounded backdrop-blur text-[10px] font-mono">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
          <span className="text-emerald-400 font-bold">120 FPS G-API SYNC</span>
        </div>
      </div>
    </div>
  );
};

export default VideoInspectionFeed;
