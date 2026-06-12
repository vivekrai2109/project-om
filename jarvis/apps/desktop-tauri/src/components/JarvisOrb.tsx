import { Canvas, useFrame } from "@react-three/fiber";
import type { Group, Mesh, MeshStandardMaterial } from "three";
import { useMemo, useRef } from "react";

import type { JarvisFaceState } from "../types/jarvis";
import { resolveFaceVisual } from "../state/faceStateMachine";

type JarvisOrbProps = {
  state: JarvisFaceState;
};

function OrbCore({ state }: JarvisOrbProps) {
  const groupRef = useRef<Group | null>(null);
  const coreRef = useRef<Mesh | null>(null);
  const ringRef = useRef<Mesh | null>(null);
  const auraRef = useRef<Mesh | null>(null);
  const rippleRef = useRef<Mesh | null>(null);
  const sweepRef = useRef<Mesh | null>(null);
  const visual = resolveFaceVisual(state);
  const phaseOffset = useMemo(() => Math.random() * Math.PI, []);

  useFrame(({ clock }, delta) => {
    const elapsed = clock.getElapsedTime() + phaseOffset;
    if (groupRef.current) {
      groupRef.current.rotation.y += delta * visual.orbitSpeed * 0.35;
      groupRef.current.rotation.z = Math.sin(elapsed * 0.25) * 0.08;
    }
    if (ringRef.current) {
      ringRef.current.rotation.z += delta * visual.orbitSpeed;
      ringRef.current.scale.setScalar(1 + Math.sin(elapsed * visual.pulseSpeed) * 0.06);
    }
    if (coreRef.current) {
      const scale = visual.shellScale + Math.sin(elapsed * visual.pulseSpeed * 1.6) * 0.08;
      coreRef.current.scale.setScalar(scale);
      const material = coreRef.current.material as MeshStandardMaterial;
      material.emissiveIntensity = visual.intensity + Math.sin(elapsed * visual.pulseSpeed) * 0.25;
    }
    if (auraRef.current) {
      auraRef.current.rotation.x += delta * visual.orbitSpeed * 0.3;
      auraRef.current.rotation.y -= delta * visual.orbitSpeed * 0.45;
    }
    if (rippleRef.current) {
      rippleRef.current.scale.setScalar(1.1 + Math.abs(Math.sin(elapsed * visual.pulseSpeed)) * visual.rippleStrength);
      rippleRef.current.rotation.z -= delta * (visual.orbitSpeed * 0.2 + visual.rippleStrength);
    }
    if (sweepRef.current) {
      sweepRef.current.rotation.z += delta * (visual.orbitSpeed * 0.4 + visual.sweepStrength * 2.2);
      sweepRef.current.scale.y = 1 + Math.abs(Math.sin(elapsed * 0.7)) * visual.sweepStrength;
    }
  });

  return (
    <group ref={groupRef}>
      <mesh ref={coreRef}>
        <icosahedronGeometry args={[1.06, 20]} />
        <meshStandardMaterial color={visual.accent} emissive={visual.glow} emissiveIntensity={visual.intensity} metalness={0.4} roughness={0.15} />
      </mesh>
      <mesh ref={ringRef} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[1.72, 0.04, 24, 160]} />
        <meshStandardMaterial color={visual.ring} emissive={visual.ring} emissiveIntensity={0.9} />
      </mesh>
      <mesh ref={auraRef} rotation={[0.8, 0.4, 0]}>
        <torusGeometry args={[2.2, 0.015, 16, 128]} />
        <meshStandardMaterial color={visual.glow} emissive={visual.glow} emissiveIntensity={0.55} transparent opacity={0.75} />
      </mesh>
      <mesh ref={rippleRef} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[2.6, 0.01, 12, 128]} />
        <meshStandardMaterial color={visual.accent} emissive={visual.accent} emissiveIntensity={0.35} transparent opacity={0.45} />
      </mesh>
      <mesh ref={sweepRef} rotation={[0, 0, 0.6]}>
        <ringGeometry args={[1.1, 2.45, 48, 1, 0, Math.PI / 3]} />
        <meshStandardMaterial color={visual.ring} emissive={visual.glow} emissiveIntensity={0.28} transparent opacity={0.2} side={2} />
      </mesh>
    </group>
  );
}

export function JarvisOrb({ state }: JarvisOrbProps) {
  return (
    <div className="orb-canvas-shell">
      <Canvas camera={{ position: [0, 0, 5.4], fov: 42 }} gl={{ antialias: true, alpha: true }}>
        <ambientLight intensity={0.7} />
        <pointLight position={[4, 6, 6]} intensity={12} color="#84f8ff" />
        <pointLight position={[-4, -3, 4]} intensity={6} color="#5a73ff" />
        <OrbCore state={state} />
      </Canvas>
    </div>
  );
}