import React, { useRef, useEffect, useCallback } from 'react';

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  color: string;
  baseX: number;
  baseY: number;
}

interface MouseState {
  x: number;
  y: number;
  active: boolean;
}

const COLORS = ['#00ff88', '#00d4ff', '#ff6b35'];
const COLOR_WEIGHTS = [0.6, 0.3, 0.1];

function getRandomColor(): string {
  const rand = Math.random();
  let cumulative = 0;
  for (let i = 0; i < COLOR_WEIGHTS.length; i++) {
    cumulative += COLOR_WEIGHTS[i];
    if (rand < cumulative) return COLORS[i];
  }
  return COLORS[0];
}

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result
    ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16),
      }
    : { r: 0, g: 255, b: 136 };
}

function blendColors(color1: string, color2: string, ratio: number): string {
  const c1 = hexToRgb(color1);
  const c2 = hexToRgb(color2);
  const r = Math.round(c1.r + (c2.r - c1.r) * ratio);
  const g = Math.round(c1.g + (c2.g - c1.g) * ratio);
  const b = Math.round(c1.b + (c2.b - c1.b) * ratio);
  return `rgb(${r}, ${g}, ${b})`;
}

interface ParticleConstellationProps {
  className?: string;
}

const ParticleConstellation: React.FC<ParticleConstellationProps> = ({ className }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<Particle[]>([]);
  const mouseRef = useRef<MouseState>({ x: 0, y: 0, active: false });
  const rafRef = useRef<number>(0);
  const dimensionsRef = useRef({ width: 0, height: 0 });

  const getParticleCount = useCallback(() => {
    if (typeof window === 'undefined') return 80;
    return window.innerWidth < 768 ? 40 : 80;
  }, []);

  const createParticles = useCallback((width: number, height: number) => {
    const count = getParticleCount();
    const particles: Particle[] = [];
    const centerX = width / 2;
    const centerY = height / 2;
    const centerRadius = Math.min(width, height) * 0.25;

    for (let i = 0; i < count; i++) {
      let x: number;
      let y: number;
      let attempts = 0;

      do {
        x = Math.random() * width;
        y = Math.random() * height;
        attempts++;
      } while (
        attempts < 50 &&
        Math.sqrt((x - centerX) ** 2 + (y - centerY) ** 2) < centerRadius
      );

      const particle: Particle = {
        x,
        y,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
        radius: 2 + Math.random() * 2,
        color: getRandomColor(),
        baseX: x,
        baseY: y,
      };
      particles.push(particle);
    }
    return particles;
  }, [getParticleCount]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const handleResize = () => {
      const dpr = window.devicePixelRatio || 1;
      const width = window.innerWidth;
      const height = window.innerHeight;

      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;

      ctx.scale(dpr, dpr);
      dimensionsRef.current = { width, height };

      particlesRef.current = createParticles(width, height);
    };

    const handleMouseMove = (e: MouseEvent) => {
      mouseRef.current = {
        x: e.clientX,
        y: e.clientY,
        active: true,
      };
    };

    const handleMouseLeave = () => {
      mouseRef.current.active = false;
    };

    handleResize();

    window.addEventListener('resize', handleResize);
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseleave', handleMouseLeave);

    const animate = () => {
      const { width, height } = dimensionsRef.current;
      const particles = particlesRef.current;
      const mouse = mouseRef.current;

      ctx.clearRect(0, 0, width, height);

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];

        p.x += p.vx;
        p.y += p.vy;

        if (p.x < 0 || p.x > width) {
          p.vx *= -1;
          p.x = Math.max(0, Math.min(width, p.x));
        }
        if (p.y < 0 || p.y > height) {
          p.vy *= -1;
          p.y = Math.max(0, Math.min(height, p.y));
        }

        if (mouse.active) {
          const dx = mouse.x - p.x;
          const dy = mouse.y - p.y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < 200 && dist > 0) {
            const force = (200 - dist) / 200;
            p.vx += (dx / dist) * force * 0.02;
            p.vy += (dy / dist) * force * 0.02;
          }
        }

        const speed = Math.sqrt(p.vx * p.vx + p.vy * p.vy);
        const maxSpeed = 1.2;
        if (speed > maxSpeed) {
          p.vx = (p.vx / speed) * maxSpeed;
          p.vy = (p.vy / speed) * maxSpeed;
        }

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.fill();
      }

      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const p1 = particles[i];
          const p2 = particles[j];
          const dx = p1.x - p2.x;
          const dy = p1.y - p2.y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < 150) {
            const opacity = (1 - dist / 150) * 0.3;
            const blendedColor = blendColors(p1.color, p2.color, 0.5);

            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.strokeStyle = blendedColor.replace('rgb', 'rgba').replace(')', `, ${opacity})`);
            ctx.lineWidth = 0.8;
            ctx.stroke();
          }
        }
      }

      const gradient = ctx.createRadialGradient(
        width / 2,
        height,
        0,
        width / 2,
        height,
        height * 0.6
      );
      gradient.addColorStop(0, 'rgba(10, 10, 15, 0)');
      gradient.addColorStop(1, 'rgba(10, 10, 15, 0.9)');

      ctx.fillStyle = gradient;
      ctx.fillRect(0, height * 0.4, width, height * 0.6);

      rafRef.current = requestAnimationFrame(animate);
    };

    rafRef.current = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, [createParticles]);

  return (
    <canvas
      ref={canvasRef}
      className={className}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        backgroundColor: '#0a0a0f',
        willChange: 'transform',
        pointerEvents: 'none',
      }}
    />
  );
};

export default ParticleConstellation;
