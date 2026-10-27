import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { Box, Layers, RefreshCw, Eye } from "lucide-react";
import { TelemetryData } from "./VideoInspectionFeed";

interface DigitalTwinCanvasProps {
  telemetry: TelemetryData;
  isRibbingActive?: boolean;
}

export const DigitalTwinCanvas: React.FC<DigitalTwinCanvasProps> = ({
  telemetry,
  isRibbingActive = false,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [cameraAngle, setCameraAngle] = useState<"iso" | "side" | "top">("iso");

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // 1. Scene, Camera, Renderer
    const width = container.clientWidth || 640;
    const height = container.clientHeight || 360;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0d14);
    scene.fog = new THREE.FogExp2(0x0a0d14, 0.035);

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.set(9.5, 6.2, 11.5);
    camera.lookAt(0, 0.5, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    container.appendChild(renderer.domElement);

    // 2. Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0x38bdf8, 1.6);
    dirLight.position.set(10, 15, 8);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.width = 1024;
    dirLight.shadow.mapSize.height = 1024;
    scene.add(dirLight);

    const accentLight = new THREE.PointLight(0x10b981, 2.0, 12);
    accentLight.position.set(3, 2.5, 0);
    scene.add(accentLight);

    // IR Dryer Glowing Heating Elements
    const dryerLight = new THREE.PointLight(0xf97316, 3.5, 8);
    dryerLight.position.set(0.5, 1.8, 0);
    scene.add(dryerLight);

    // 3. Ground Plant-Floor Grid
    const gridHelper = new THREE.GridHelper(24, 24, 0x0ea5e9, 0x1e293b);
    gridHelper.position.y = -0.01;
    scene.add(gridHelper);

    // 4. Machinery Base Platform
    const baseGeo = new THREE.BoxGeometry(14, 0.3, 3.2);
    const baseMat = new THREE.MeshStandardMaterial({
      color: 0x1e2638,
      metalness: 0.85,
      roughness: 0.3,
    });
    const baseMesh = new THREE.Mesh(baseGeo, baseMat);
    baseMesh.position.y = 0.15;
    baseMesh.receiveShadow = true;
    scene.add(baseMesh);

    // 5. Continuous Moving Web (Electrode Foil)
    const webGeo = new THREE.PlaneGeometry(12.5, 2.2, 32, 1);
    const webMat = new THREE.MeshStandardMaterial({
      color: 0xb45309, // Copper / Carbon composite sheen
      metalness: 0.9,
      roughness: 0.25,
      side: THREE.DoubleSide,
    });
    const webMesh = new THREE.Mesh(webGeo, webMat);
    webMesh.rotation.x = -Math.PI / 2;
    webMesh.position.set(0, 1.2, 0);
    scene.add(webMesh);

    // 6. Rollers: Unwind, Dancer, Guide Rollers, Rewind
    const rollerMat = new THREE.MeshStandardMaterial({
      color: 0x94a3b8,
      metalness: 0.95,
      roughness: 0.15,
    });
    const rubberRollerMat = new THREE.MeshStandardMaterial({
      color: 0x334155,
      metalness: 0.1,
      roughness: 0.8,
    });

    // Unwind Reel
    const unwindGeo = new THREE.CylinderGeometry(0.8, 0.8, 2.4, 24);
    const unwindMesh = new THREE.Mesh(unwindGeo, rollerMat);
    unwindMesh.rotation.x = Math.PI / 2;
    unwindMesh.position.set(-5.5, 1.2, 0);
    scene.add(unwindMesh);

    // Active Dancer Tension Roller (moves vertically on tension changes)
    const dancerGeo = new THREE.CylinderGeometry(0.35, 0.35, 2.4, 24);
    const dancerMesh = new THREE.Mesh(dancerGeo, rubberRollerMat);
    dancerMesh.rotation.x = Math.PI / 2;
    dancerMesh.position.set(-3.8, 0.8, 0);
    scene.add(dancerMesh);

    // Slot-Die Coating Head
    const slotDieGroup = new THREE.Group();
    const dieHeadGeo = new THREE.BoxGeometry(0.5, 0.8, 2.6);
    const dieHeadMat = new THREE.MeshStandardMaterial({
      color: 0x475569,
      metalness: 0.8,
      roughness: 0.2,
    });
    const dieHeadMesh = new THREE.Mesh(dieHeadGeo, dieHeadMat);
    dieHeadMesh.position.set(-2.2, 1.8, 0);
    slotDieGroup.add(dieHeadMesh);

    // Slurry Feed Tube
    const pipeGeo = new THREE.CylinderGeometry(0.08, 0.08, 1.2);
    const pipeMat = new THREE.MeshStandardMaterial({ color: 0x06b6d4, metalness: 0.6 });
    const pipeMesh = new THREE.Mesh(pipeGeo, pipeMat);
    pipeMesh.position.set(-2.2, 2.5, 0);
    slotDieGroup.add(pipeMesh);
    scene.add(slotDieGroup);

    // 7. IR Drying Tunnel (Glowing Enclosure)
    const dryerGroup = new THREE.Group();
    const dryerTunnelGeo = new THREE.BoxGeometry(3.6, 1.4, 2.6);
    const dryerTunnelMat = new THREE.MeshStandardMaterial({
      color: 0x1f2937,
      metalness: 0.7,
      roughness: 0.4,
      transparent: true,
      opacity: 0.85,
    });
    const dryerTunnelMesh = new THREE.Mesh(dryerTunnelGeo, dryerTunnelMat);
    dryerTunnelMesh.position.set(0.6, 1.6, 0);
    dryerGroup.add(dryerTunnelMesh);

    // Glowing heating quartz elements inside
    const quartzGeo = new THREE.BoxGeometry(3.2, 0.08, 0.15);
    const quartzMat = new THREE.MeshStandardMaterial({
      color: 0xf97316,
      emissive: 0xf97316,
      emissiveIntensity: 1.8,
    });
    for (let z = -0.8; z <= 0.8; z += 0.4) {
      const qMesh = new THREE.Mesh(quartzGeo, quartzMat);
      qMesh.position.set(0.6, 2.05, z);
      dryerGroup.add(qMesh);
    }
    scene.add(dryerGroup);

    // 8. OpenCV G-API Camera Metrology Gantry
    const gantryGroup = new THREE.Group();
    const gantryFrameGeo = new THREE.BoxGeometry(0.3, 2.2, 2.8);
    const gantryFrameMat = new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.6 });
    const gantryFrameMesh = new THREE.Mesh(gantryFrameGeo, gantryFrameMat);
    gantryFrameMesh.position.set(3.4, 1.6, 0);
    gantryGroup.add(gantryFrameMesh);

    // Optical Camera Head
    const camHousingGeo = new THREE.BoxGeometry(0.5, 0.4, 0.5);
    const camHousingMat = new THREE.MeshStandardMaterial({ color: 0x0284c7 });
    const camHousingMesh = new THREE.Mesh(camHousingGeo, camHousingMat);
    camHousingMesh.position.set(3.4, 2.5, 0);
    gantryGroup.add(camHousingMesh);

    // Laser Sheet Scanner Plane
    const laserPlaneGeo = new THREE.PlaneGeometry(0.04, 2.2);
    const laserPlaneMat = new THREE.MeshBasicMaterial({
      color: 0x10b981,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.7,
    });
    const laserPlaneMesh = new THREE.Mesh(laserPlaneGeo, laserPlaneMat);
    laserPlaneMesh.rotation.x = Math.PI / 2;
    laserPlaneMesh.position.set(3.4, 1.25, 0);
    gantryGroup.add(laserPlaneMesh);
    scene.add(gantryGroup);

    // 9. Rewind Reel
    const rewindGeo = new THREE.CylinderGeometry(0.7, 0.7, 2.4, 24);
    const rewindMesh = new THREE.Mesh(rewindGeo, rollerMat);
    rewindMesh.rotation.x = Math.PI / 2;
    rewindMesh.position.set(5.5, 1.2, 0);
    scene.add(rewindMesh);

    // Mouse Interaction / Orbit Drag Simulation
    let isDragging = false;
    let prevMouseX = 0;
    let prevMouseY = 0;
    let sphericalTheta = 0.85;
    let sphericalPhi = 0.55;
    let radius = 16.0;

    const onMouseDown = (e: MouseEvent) => {
      isDragging = true;
      prevMouseX = e.clientX;
      prevMouseY = e.clientY;
    };

    const onMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;
      const dx = e.clientX - prevMouseX;
      const dy = e.clientY - prevMouseY;
      prevMouseX = e.clientX;
      prevMouseY = e.clientY;

      sphericalTheta -= dx * 0.008;
      sphericalPhi = Math.max(0.1, Math.min(Math.PI / 2 - 0.05, sphericalPhi + dy * 0.008));
    };

    const onMouseUp = () => {
      isDragging = false;
    };

    const onWheel = (e: WheelEvent) => {
      radius = Math.max(8.0, Math.min(24.0, radius + e.deltaY * 0.015));
    };

    const dom = renderer.domElement;
    dom.addEventListener("mousedown", onMouseDown);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    dom.addEventListener("wheel", onWheel);

    // Animation Loop
    let animId: number;
    let clock = new THREE.Clock();

    const animate = () => {
      animId = requestAnimationFrame(animate);
      const delta = clock.getDelta();
      const elapsed = clock.getElapsedTime();

      const speed = telemetry.line_speed_mps || 2.50;
      const rotDelta = speed * 1.8 * delta;

      // Roller rotations
      unwindMesh.rotation.y += rotDelta;
      rewindMesh.rotation.y += rotDelta;
      dancerMesh.rotation.y += rotDelta;

      // Dancer vertical oscillation coupled to tension variance
      const nominalTension = 150.0;
      const tensionDelta = (telemetry.tension_newtons - nominalTension) * 0.02;
      dancerMesh.position.y = 0.8 - tensionDelta + Math.sin(elapsed * 4.0) * 0.02;

      // Slot-die micro-chatter vibration on 142.5 Hz ribbing
      if (isRibbingActive) {
        slotDieGroup.position.y = Math.sin(elapsed * 45.0) * 0.04;
      } else {
        slotDieGroup.position.y = 0;
      }

      // IR Dryer Heat Pulse
      const tempNormalized = (telemetry.dryer_temp_c - 100.0) / 40.0;
      const pulse = Math.sin(elapsed * 3.0) * 0.2 + 0.8;
      quartzMat.emissiveIntensity = THREE.MathUtils.clamp(tempNormalized * 2.2 * pulse, 0.8, 3.5);
      dryerLight.intensity = quartzMat.emissiveIntensity * 1.5;

      // Laser Scanner line sweep
      laserPlaneMesh.position.z = Math.sin(elapsed * 5.0) * 0.8;

      // Camera Orbit updates
      if (!isDragging) {
        sphericalTheta += 0.05 * delta; // Slow subtle turntable drift
      }

      camera.position.x = radius * Math.sin(sphericalPhi) * Math.sin(sphericalTheta);
      camera.position.y = radius * Math.cos(sphericalPhi);
      camera.position.z = radius * Math.sin(sphericalPhi) * Math.cos(sphericalTheta);
      camera.lookAt(0, 1.2, 0);

      renderer.render(scene, camera);
    };

    animate();

    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };

    window.addEventListener("resize", handleResize);

    return () => {
      cancelAnimationFrame(animId);
      dom.removeEventListener("mousedown", onMouseDown);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      dom.removeEventListener("wheel", onWheel);
      window.removeEventListener("resize", handleResize);
      if (dom && dom.parentNode) {
        dom.parentNode.removeChild(dom);
      }
      renderer.dispose();
    };
  }, [telemetry.line_speed_mps, telemetry.tension_newtons, telemetry.dryer_temp_c, isRibbingActive]);

  return (
    <div className="flex flex-col bg-industrial-850 border border-industrial-700 rounded-lg overflow-hidden shadow-xl">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-industrial-900 border-b border-industrial-700">
        <div className="flex items-center space-x-2">
          <Box className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-mono font-bold tracking-wider text-slate-200 uppercase">
            3D Mechanical Digital Twin (Three.js Roll-to-Roll Line)
          </span>
        </div>
        <div className="flex items-center space-x-2 text-[10px] font-mono text-slate-400">
          <span>Drag: Orbit | Scroll: Zoom</span>
          <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
        </div>
      </div>

      {/* WebGL Viewport */}
      <div
        ref={containerRef}
        className="relative w-full aspect-[16/9] bg-[#0a0d14] cursor-grab active:cursor-grabbing overflow-hidden"
      >
        {/* Overlay Badges */}
        <div className="absolute top-2 left-2 flex flex-col space-y-1 pointer-events-none">
          <div className="flex items-center space-x-1.5 px-2 py-0.5 bg-industrial-900/80 border border-industrial-700/80 rounded backdrop-blur text-[10px] font-mono text-cyan-300">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
            <span>UNWIND ➔ DANCER ➔ SLOT-DIE ➔ IR DRYER ➔ G-API GANTRY ➔ REWIND</span>
          </div>
          {isRibbingActive && (
            <div className="flex items-center space-x-1 px-2 py-0.5 bg-amber-500/20 border border-amber-500/50 rounded backdrop-blur text-[10px] font-mono text-amber-300 animate-pulse">
              <span>ACTIVE DIE CHATTER RESONANCE (142.5 Hz)</span>
            </div>
          )}
        </div>

        <div className="absolute bottom-2 left-2 flex items-center space-x-2 pointer-events-none">
          <div className="px-2 py-0.5 bg-industrial-900/90 border border-industrial-700 rounded text-[9px] font-mono text-slate-300">
            SPEED: {telemetry.line_speed_mps?.toFixed(2)} m/s
          </div>
          <div className="px-2 py-0.5 bg-industrial-900/90 border border-industrial-700 rounded text-[9px] font-mono text-slate-300">
            TENSION: {telemetry.tension_newtons?.toFixed(1)} N
          </div>
          <div className="px-2 py-0.5 bg-industrial-900/90 border border-industrial-700 rounded text-[9px] font-mono text-orange-400">
            DRYER: {telemetry.dryer_temp_c?.toFixed(1)} °C
          </div>
        </div>
      </div>
    </div>
  );
};

export default DigitalTwinCanvas;
