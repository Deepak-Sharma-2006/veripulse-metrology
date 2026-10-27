import React, { useEffect, useRef, useState } from "react";
import { Eye, Crosshair, ZoomIn, Layers, Camera, AlertTriangle } from "lucide-react";

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
    let scrollOffset = 0;
    let lastTime = performance.now();
    let frameCount = 0;
    let measuredFps = fps;
    let lastFpsUpdate = performance.now();

    const render = (time: number) => {
      const dt = Math.min((time - lastTime) / 1000, 0.1);
      lastTime = time;

      frameCount++;
      if (time - lastFpsUpdate >= 500) {
        measuredFps = Math.round((frameCount * 1000) / (time - lastFpsUpdate));
        frameCount = 0;
        lastFpsUpdate = time;
      }

      const speed = telemetryRef.current.line_speed_mps || 2.50;
      const activeAlert = alertRef.current;
      const hasAlert = Boolean(activeAlert?.detected);
      const isRibbing = hasAlert && Boolean(activeAlert?.defect_type?.includes("ribbing"));
      const isGlare = hasAlert && Boolean(activeAlert?.defect_type?.includes("reflectance"));
      const isPinhole = hasAlert && Boolean(activeAlert?.defect_type?.includes("pinhole"));

      // Advance web travel downwards proportional to line velocity
      scrollOffset = (scrollOffset + speed * 180 * dt) % 1000;

      const w = canvas.width;
      const h = canvas.height;

      // -------------------------------------------------------------
      // 1. Base Substrate Rendering (Roll-to-Roll Lithium Anode Foil)
      // -------------------------------------------------------------
      const marginWidth = Math.floor(w * 0.16);
      const slurryWidth = w - 2 * marginWidth;

      if (viewMode === "thermal") {
        // LWIR Radiometric False-Color Background
        const tempBase = telemetryRef.current.dryer_temp_c || 120.0;
        ctx.fillStyle = tempBase > 125 ? "#2e0854" : "#19052b";
        ctx.fillRect(0, 0, w, h);

        // Thermal central slurry thermal gradient
        const thermalGrad = ctx.createLinearGradient(marginWidth, 0, marginWidth + slurryWidth, 0);
        thermalGrad.addColorStop(0, "#4a044e");
        thermalGrad.addColorStop(0.5, isRibbing ? "#ea580c" : "#a21caf");
        thermalGrad.addColorStop(1, "#4a044e");
        ctx.fillStyle = thermalGrad;
        ctx.fillRect(marginWidth, 0, slurryWidth, h);

      } else if (viewMode === "sobel") {
        // High-pass Sobel gradient mode
        ctx.fillStyle = "#070b12";
        ctx.fillRect(0, 0, w, h);

        // Slurry boundary edges in cyan
        ctx.strokeStyle = "rgba(56, 189, 248, 0.75)";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(marginWidth, 0);
        ctx.lineTo(marginWidth, h);
        ctx.moveTo(marginWidth + slurryWidth, 0);
        ctx.lineTo(marginWidth + slurryWidth, h);
        ctx.stroke();

      } else {
        // True Optical Multi-Spectral Mode
        // Dark metallic background
        ctx.fillStyle = "#090d16";
        ctx.fillRect(0, 0, w, h);

        // Left & Right Bare Copper Foil Margins (Current Collectors)
        const copperGradLeft = ctx.createLinearGradient(0, 0, marginWidth, 0);
        copperGradLeft.addColorStop(0, "#78350f");
        copperGradLeft.addColorStop(0.7, "#9a3412");
        copperGradLeft.addColorStop(1, "#b45309");
        ctx.fillStyle = copperGradLeft;
        ctx.fillRect(0, 0, marginWidth, h);

        const copperGradRight = ctx.createLinearGradient(w - marginWidth, 0, w, 0);
        copperGradRight.addColorStop(0, "#b45309");
        copperGradRight.addColorStop(0.3, "#9a3412");
        copperGradRight.addColorStop(1, "#78350f");
        ctx.fillStyle = copperGradRight;
        ctx.fillRect(w - marginWidth, 0, marginWidth, h);

        // Central Graphite Anode Slurry Coating (Matte dark grey/charcoal)
        const slurryGrad = ctx.createLinearGradient(marginWidth, 0, marginWidth + slurryWidth, 0);
        slurryGrad.addColorStop(0, "#181d28");
        slurryGrad.addColorStop(0.1, "#1e2433");
        slurryGrad.addColorStop(0.5, "#232a3b");
        slurryGrad.addColorStop(0.9, "#1e2433");
        slurryGrad.addColorStop(1, "#181d28");
        ctx.fillStyle = slurryGrad;
        ctx.fillRect(marginWidth, 0, slurryWidth, h);

        // Slurry coating edge beads (surface tension meniscus troughs)
        ctx.fillStyle = "#0f131a";
        ctx.fillRect(marginWidth - 2, 0, 4, h);
        ctx.fillRect(marginWidth + slurryWidth - 2, 0, 4, h);
      }

      // -------------------------------------------------------------
      // 2. Micro-Texture & Substrate Flow Simulation (120 FPS travel)
      // -------------------------------------------------------------
      const grainSpacing = 28 * zoomLevel;
      ctx.fillStyle = viewMode === "thermal" ? "rgba(251, 146, 60, 0.15)" : "rgba(148, 163, 184, 0.12)";
      for (let y = (scrollOffset % grainSpacing) - grainSpacing; y < h + grainSpacing; y += grainSpacing) {
        for (let i = 0; i < 6; i++) {
          const gx = marginWidth + ((i * 73 + y * 1.7) % (slurryWidth - 20));
          ctx.fillRect(gx, y, 2.5 * zoomLevel, 1);
        }
      }

      // -------------------------------------------------------------
      // 3. Dynamic Physical Flaws & Defect Rendering
      // -------------------------------------------------------------
      // A. 142.5 Hz Meniscus Ribbing Resonant Waves
      if (isRibbing) {
        ctx.lineWidth = 2 * zoomLevel;
        const wavePeriod = 24 * zoomLevel;
        for (let y = (scrollOffset % wavePeriod) - wavePeriod; y < h + wavePeriod; y += wavePeriod) {
          ctx.beginPath();
          ctx.strokeStyle = viewMode === "thermal" ? "rgba(249, 115, 22, 0.85)" : "rgba(56, 189, 248, 0.65)";
          for (let x = marginWidth; x <= marginWidth + slurryWidth; x += 12) {
            const ripple = Math.sin((x * 0.04) + (time * 0.012) + (y * 0.05)) * (5 * zoomLevel);
            if (x === marginWidth) ctx.moveTo(x, y + ripple);
            else ctx.lineTo(x, y + ripple);
          }
          ctx.stroke();
        }
      }

      // B. Specular Copper Foil Glare
      if (isGlare) {
        const glareX = marginWidth * 0.55;
        const glareY = h * 0.42;
        const glareGrad = ctx.createRadialGradient(glareX, glareY, 6, glareX, glareY, 65 * zoomLevel);
        glareGrad.addColorStop(0, "rgba(255, 255, 255, 0.95)");
        glareGrad.addColorStop(0.35, "rgba(254, 215, 170, 0.65)");
        glareGrad.addColorStop(0.7, "rgba(251, 146, 60, 0.25)");
        glareGrad.addColorStop(1, "rgba(251, 146, 60, 0)");
        ctx.fillStyle = glareGrad;
        ctx.beginPath();
        ctx.arc(glareX, glareY, 65 * zoomLevel, 0, Math.PI * 2);
        ctx.fill();
      }

      // C. 50 µm Micro-Pinhole Defect
      if (isPinhole || (!isRibbing && !isGlare && hasAlert)) {
        const pinholeX = Math.floor(w * 0.52);
        const pinholeY = Math.floor(h * 0.48);
        const pinholeR = Math.max(2, 3.5 * zoomLevel);

        // Core void (copper exposed through slurry)
        ctx.fillStyle = "#ea580c";
        ctx.beginPath();
        ctx.arc(pinholeX, pinholeY, pinholeR, 0, Math.PI * 2);
        ctx.fill();

        // Edge gradient halo
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 1;
        ctx.stroke();

        // Sub-pixel metrology crosshairs & bounding box
        const boxSize = 36 * zoomLevel;
        ctx.strokeStyle = "#ef4444";
        ctx.lineWidth = 1.5;
        ctx.strokeRect(pinholeX - boxSize / 2, pinholeY - boxSize / 2, boxSize, boxSize);

        // Reticle ticks
        ctx.beginPath();
        ctx.moveTo(pinholeX - boxSize / 2 - 6, pinholeY);
        ctx.lineTo(pinholeX + boxSize / 2 + 6, pinholeY);
        ctx.moveTo(pinholeX, pinholeY - boxSize / 2 - 6);
        ctx.lineTo(pinholeX, pinholeY + boxSize / 2 + 6);
        ctx.stroke();

        // Metrology annotation badge
        ctx.fillStyle = "rgba(15, 23, 42, 0.90)";
        ctx.fillRect(pinholeX + boxSize / 2 + 8, pinholeY - 22, 138, 38);
        ctx.strokeStyle = "rgba(239, 68, 68, 0.60)";
        ctx.strokeRect(pinholeX + boxSize / 2 + 8, pinholeY - 22, 138, 38);

        ctx.fillStyle = "#ef4444";
        ctx.font = "bold 10px monospace";
        ctx.fillText("50 µm PINHOLE VOID", pinholeX + boxSize / 2 + 14, pinholeY - 8);
        ctx.fillStyle = "#94a3b8";
        ctx.font = "9px monospace";
        ctx.fillText("Major: 52.1µm | ±2.44µm", pinholeX + boxSize / 2 + 14, pinholeY + 8);
      }

      // -------------------------------------------------------------
      // 4. Subtle Industrial Metrology Inspection Reticle
      // -------------------------------------------------------------
      const cx = w / 2;
      const cy = h / 2;
      ctx.strokeStyle = "rgba(148, 163, 184, 0.20)";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 6]);
      ctx.beginPath();
      ctx.moveTo(cx, 0);
      ctx.lineTo(cx, h);
      ctx.moveTo(0, cy);
      ctx.lineTo(w, cy);
      ctx.stroke();
      ctx.setLineDash([]);

      animationFrameId = requestAnimationFrame(render);
    };

    animationFrameId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animationFrameId);
  }, [viewMode, zoomLevel, fps]);

  return (
    <div className="flex flex-col h-full min-h-0 bg-slate-900 border border-slate-800 rounded-lg overflow-hidden shadow-lg">
      {/* Precision Industrial Header */}
      <div className="flex items-center justify-between px-3.5 py-2 bg-slate-950/80 border-b border-slate-800 shrink-0">
        <div className="flex items-center space-x-2.5">
          <Camera className="w-4 h-4 text-sky-400" />
          <div className="flex items-center space-x-2">
            <span className="text-xs font-semibold tracking-wide text-slate-100">
              High-Speed Optical Ingestion
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-sky-950/80 text-sky-400 border border-sky-800/60 font-medium">
              120 FPS • Sub-Pixel G-API
            </span>
          </div>
        </div>

        {/* View Mode Selectors */}
        <div className="flex items-center space-x-1">
          <button
            onClick={() => setViewMode("optical")}
            className={`px-2.5 py-1 text-[11px] font-medium rounded transition ${
              viewMode === "optical"
                ? "bg-sky-600 text-white shadow-sm"
                : "bg-slate-800/80 text-slate-300 hover:bg-slate-700/80"
            }`}
          >
            Optical
          </button>
          <button
            onClick={() => setViewMode("sobel")}
            className={`px-2.5 py-1 text-[11px] font-medium rounded transition ${
              viewMode === "sobel"
                ? "bg-sky-600 text-white shadow-sm"
                : "bg-slate-800/80 text-slate-300 hover:bg-slate-700/80"
            }`}
          >
            Sobel
          </button>
          <button
            onClick={() => setViewMode("thermal")}
            className={`px-2.5 py-1 text-[11px] font-medium rounded transition ${
              viewMode === "thermal"
                ? "bg-fuchsia-600 text-white shadow-sm"
                : "bg-slate-800/80 text-slate-300 hover:bg-slate-700/80"
            }`}
          >
            Thermal LWIR
          </button>
          <button
            onClick={() => setZoomLevel((z) => (z === 1.0 ? 1.5 : z === 1.5 ? 2.0 : 1.0))}
            className="p-1 text-slate-400 hover:text-slate-200 bg-slate-800/60 rounded border border-slate-700/60 transition ml-1"
            title="Toggle Inspection Zoom"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Main Optical Viewport Canvas */}
      <div className="relative flex-1 min-h-0 bg-slate-950 flex items-center justify-center overflow-hidden">
        <canvas
          ref={canvasRef}
          width={640}
          height={380}
          className="w-full h-full object-cover block"
        />

        {/* HUD Precision Metadata Overlay */}
        <div className="absolute top-3 left-3 pointer-events-none flex flex-col space-y-1 font-mono text-[10px] text-slate-300 bg-slate-950/85 backdrop-blur-sm p-2 rounded border border-slate-800 shadow">
          <div className="flex items-center space-x-2">
            <span className="text-slate-500">SENSOR:</span>
            <span className="text-slate-200 font-semibold">2048×2048 @ 120 FPS</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="text-slate-500">RES / FOV:</span>
            <span className="text-slate-200">24.4 µm/px • 50.0 mm</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="text-slate-500">METROLOGY:</span>
            <span className="text-emerald-400 font-semibold">±2.44 µm (Scharr G-API)</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="text-slate-500">VELOCITY:</span>
            <span className="text-sky-400 font-semibold">
              {(telemetryRef.current.line_speed_mps || 2.50).toFixed(2)} m/s (150 m/min)
            </span>
          </div>
        </div>

        {/* Live Status Badge */}
        <div className="absolute bottom-3 right-3 pointer-events-none flex items-center space-x-1.5 px-2.5 py-1 rounded bg-slate-950/85 backdrop-blur-sm border border-slate-800 text-[10px] font-mono">
          <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-slate-300 font-medium">120 FPS G-API SYNC</span>
        </div>
      </div>
    </div>
  );
};
