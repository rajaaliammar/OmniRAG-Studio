"use client";

import { motion, useReducedMotion } from "motion/react";
import { useEffect, useRef } from "react";

type Particle = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  hue: number;
  alpha: number;
};

/**
 * Lightweight cinematic ambient background: soft neon orbs + particle mesh.
 * Pauses when the tab is hidden and respects prefers-reduced-motion.
 */
export function AmbientBackground() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    if (reduceMotion) {
      return;
    }

    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }

    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) {
      return;
    }

    let frameId = 0;
    let running = true;
    let width = 0;
    let height = 0;
    let dpr = 1;
    let particles: Particle[] = [];

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const count = Math.min(56, Math.max(28, Math.floor((width * height) / 38000)));
      particles = Array.from({ length: count }, () => createParticle(width, height));
    };

    const createParticle = (w: number, h: number): Particle => ({
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.22,
      vy: (Math.random() - 0.5) * 0.22,
      r: 0.8 + Math.random() * 1.8,
      hue: Math.random() > 0.55 ? 168 : Math.random() > 0.4 ? 198 : 152,
      alpha: 0.18 + Math.random() * 0.35,
    });

    const draw = () => {
      if (!running) {
        return;
      }

      ctx.clearRect(0, 0, width, height);

      // Soft vignette mesh lines (sparse, low cost).
      ctx.strokeStyle = "rgba(51, 65, 85, 0.18)";
      ctx.lineWidth = 1;
      const step = 96;
      ctx.beginPath();
      for (let x = 0; x <= width; x += step) {
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
      }
      for (let y = 0; y <= height; y += step) {
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
      }
      ctx.stroke();

      const linkDist = 120;
      for (let i = 0; i < particles.length; i += 1) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;

        if (p.x < -20) p.x = width + 20;
        if (p.x > width + 20) p.x = -20;
        if (p.y < -20) p.y = height + 20;
        if (p.y > height + 20) p.y = -20;

        for (let j = i + 1; j < particles.length; j += 1) {
          const q = particles[j];
          const dx = p.x - q.x;
          const dy = p.y - q.y;
          const dist = Math.hypot(dx, dy);
          if (dist < linkDist) {
            const fade = 1 - dist / linkDist;
            ctx.strokeStyle = `rgba(34, 211, 238, ${0.08 * fade})`;
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(q.x, q.y);
            ctx.stroke();
          }
        }

        ctx.beginPath();
        ctx.fillStyle = `hsla(${p.hue}, 90%, 62%, ${p.alpha})`;
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      }

      frameId = window.requestAnimationFrame(draw);
    };

    const onVisibility = () => {
      if (document.hidden) {
        running = false;
        window.cancelAnimationFrame(frameId);
      } else if (!running) {
        running = true;
        frameId = window.requestAnimationFrame(draw);
      }
    };

    resize();
    frameId = window.requestAnimationFrame(draw);
    window.addEventListener("resize", resize, { passive: true });
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      running = false;
      window.cancelAnimationFrame(frameId);
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [reduceMotion]);

  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 z-0 overflow-hidden"
    >
      <div className="absolute inset-0 bg-slate-950" />

      {/* Soft drifting neon orbs (GPU-friendly transforms). */}
      {!reduceMotion ? (
        <>
          <motion.div
            className="absolute -left-24 top-10 size-[28rem] rounded-full bg-cyan-500/15 blur-3xl will-change-transform"
            animate={{ x: [0, 40, -20, 0], y: [0, 30, 10, 0] }}
            transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }}
          />
          <motion.div
            className="absolute -right-20 top-1/3 size-[26rem] rounded-full bg-emerald-500/12 blur-3xl will-change-transform"
            animate={{ x: [0, -35, 15, 0], y: [0, -25, 20, 0] }}
            transition={{ duration: 26, repeat: Infinity, ease: "easeInOut" }}
          />
          <motion.div
            className="absolute bottom-[-8rem] left-1/3 size-[30rem] rounded-full bg-blue-500/10 blur-3xl will-change-transform"
            animate={{ x: [0, 25, -30, 0], y: [0, -20, 15, 0] }}
            transition={{ duration: 30, repeat: Infinity, ease: "easeInOut" }}
          />
        </>
      ) : (
        <>
          <div className="absolute -left-24 top-10 size-[28rem] rounded-full bg-cyan-500/12 blur-3xl" />
          <div className="absolute -right-20 top-1/3 size-[26rem] rounded-full bg-emerald-500/10 blur-3xl" />
        </>
      )}

      <canvas
        ref={canvasRef}
        className="absolute inset-0 h-full w-full will-change-transform opacity-80"
      />

      {/* Subtle top/bottom vignette so UI stays readable. */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_35%,rgba(2,6,23,0.55)_100%)]" />
    </div>
  );
}
