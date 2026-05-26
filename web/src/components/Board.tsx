import { useEffect, useRef, useState } from "react";

import {
  BOARD_SIZE,
  STAR_POINTS,
  cellToPx,
  computeGeom,
  pxToCell,
} from "@/lib/boardMath";
import type { ColorStr, Stone } from "@/types/protocol";

interface BoardProps {
  stones: Stone[];
  lastMove?: Stone | null;
  forbiddenSquares?: [number, number][];
  toMove?: ColorStr;
  hoverColor?: ColorStr | null;  // null = no ghost
  disabled?: boolean;
  onPlay?: (r: number, c: number) => void;
}

export default function Board({
  stones,
  lastMove,
  forbiddenSquares = [],
  toMove = "BLACK",
  hoverColor = null,
  disabled = false,
  onPlay,
}: BoardProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const [cssSize, setCssSize] = useState(560);
  const [hover, setHover] = useState<{ r: number; c: number } | null>(null);

  // Resize observer: keep the canvas square and matching its wrapper width.
  useEffect(() => {
    if (!wrapperRef.current) return;
    const obs = new ResizeObserver((entries) => {
      for (const e of entries) {
        const w = Math.floor(e.contentRect.width);
        if (w > 50) setCssSize(w);
      }
    });
    obs.observe(wrapperRef.current);
    return () => obs.disconnect();
  }, []);

  // Render whenever any input changes.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(cssSize * dpr);
    canvas.height = Math.round(cssSize * dpr);
    canvas.style.width = `${cssSize}px`;
    canvas.style.height = `${cssSize}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const geom = computeGeom(cssSize);

    // Background.
    ctx.fillStyle = "#dcb35c";
    ctx.fillRect(0, 0, cssSize, cssSize);

    // Grid.
    ctx.strokeStyle = "#2b1d0e";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i < BOARD_SIZE; i++) {
      const start = cellToPx(geom, i, 0);
      const end = cellToPx(geom, i, BOARD_SIZE - 1);
      ctx.moveTo(start.x, start.y);
      ctx.lineTo(end.x, end.y);
      const startC = cellToPx(geom, 0, i);
      const endC = cellToPx(geom, BOARD_SIZE - 1, i);
      ctx.moveTo(startC.x, startC.y);
      ctx.lineTo(endC.x, endC.y);
    }
    ctx.stroke();

    // Star points.
    ctx.fillStyle = "#2b1d0e";
    for (const [r, c] of STAR_POINTS) {
      const p = cellToPx(geom, r, c);
      ctx.beginPath();
      ctx.arc(p.x, p.y, Math.max(2, geom.cellPx * 0.07), 0, Math.PI * 2);
      ctx.fill();
    }

    // Coordinate labels.
    ctx.fillStyle = "#3a2e1a";
    ctx.font = `${Math.round(geom.cellPx * 0.35)}px ui-sans-serif, system-ui, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (let i = 0; i < BOARD_SIZE; i++) {
      const colLabel = String.fromCharCode("A".charCodeAt(0) + i);
      const p = cellToPx(geom, 0, i);
      ctx.fillText(colLabel, p.x, geom.margin / 2);
      const rowLabel = `${BOARD_SIZE - i}`;
      const p2 = cellToPx(geom, i, 0);
      ctx.fillText(rowLabel, geom.margin / 2, p2.y);
    }

    // Stones.
    for (const s of stones) {
      drawStone(ctx, geom, s.r, s.c, s.color, 1);
    }

    // Last move highlight.
    if (lastMove) {
      const p = cellToPx(geom, lastMove.r, lastMove.c);
      ctx.fillStyle = "#e23b3b";
      ctx.beginPath();
      ctx.arc(p.x, p.y, Math.max(2, geom.stoneRadius * 0.22), 0, Math.PI * 2);
      ctx.fill();
    }

    // Forbidden squares (only meaningful when toMove === BLACK).
    if (toMove === "BLACK" && forbiddenSquares.length) {
      ctx.strokeStyle = "#d23535";
      ctx.lineWidth = Math.max(1.5, geom.cellPx * 0.06);
      for (const [r, c] of forbiddenSquares) {
        const p = cellToPx(geom, r, c);
        const k = geom.stoneRadius * 0.55;
        ctx.beginPath();
        ctx.moveTo(p.x - k, p.y - k);
        ctx.lineTo(p.x + k, p.y + k);
        ctx.moveTo(p.x + k, p.y - k);
        ctx.lineTo(p.x - k, p.y + k);
        ctx.stroke();
      }
    }

    // Hover ghost.
    if (!disabled && hover && hoverColor) {
      const occupied = stones.some((s) => s.r === hover.r && s.c === hover.c);
      if (!occupied) drawStone(ctx, geom, hover.r, hover.c, hoverColor, 0.4);
    }
  }, [stones, lastMove, forbiddenSquares, toMove, hover, hoverColor, disabled, cssSize]);

  const handleMouseMove = (ev: React.MouseEvent<HTMLCanvasElement>) => {
    if (disabled) return;
    const rect = ev.currentTarget.getBoundingClientRect();
    const x = ev.clientX - rect.left;
    const y = ev.clientY - rect.top;
    const cell = pxToCell(computeGeom(cssSize), x, y);
    setHover(cell);
  };

  const handleMouseLeave = () => setHover(null);

  const handleClick = (ev: React.MouseEvent<HTMLCanvasElement>) => {
    if (disabled) return;
    const rect = ev.currentTarget.getBoundingClientRect();
    const x = ev.clientX - rect.left;
    const y = ev.clientY - rect.top;
    const cell = pxToCell(computeGeom(cssSize), x, y);
    if (!cell) return;
    onPlay?.(cell.r, cell.c);
  };

  return (
    <div ref={wrapperRef} className="w-full max-w-[700px] aspect-square">
      <canvas
        ref={canvasRef}
        onClick={handleClick}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        className="rounded-md shadow-lg cursor-pointer"
      />
    </div>
  );
}

function drawStone(
  ctx: CanvasRenderingContext2D,
  geom: { cellPx: number; stoneRadius: number; margin: number; cssSize: number },
  r: number,
  c: number,
  color: ColorStr,
  alpha = 1,
) {
  const p = cellToPx(geom as any, r, c);
  const radius = geom.stoneRadius;
  ctx.save();
  ctx.globalAlpha = alpha;

  // Shadow.
  ctx.fillStyle = "rgba(0,0,0,0.25)";
  ctx.beginPath();
  ctx.arc(p.x + radius * 0.12, p.y + radius * 0.18, radius, 0, Math.PI * 2);
  ctx.fill();

  // Radial gradient body.
  const grad = ctx.createRadialGradient(
    p.x - radius * 0.4,
    p.y - radius * 0.45,
    radius * 0.1,
    p.x,
    p.y,
    radius,
  );
  if (color === "BLACK") {
    grad.addColorStop(0, "#5a5a5a");
    grad.addColorStop(0.5, "#1a1a1a");
    grad.addColorStop(1, "#000000");
  } else {
    grad.addColorStop(0, "#ffffff");
    grad.addColorStop(0.6, "#f0eee8");
    grad.addColorStop(1, "#cfc9bb");
  }
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(p.x, p.y, radius, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = color === "BLACK" ? "#000" : "#888";
  ctx.lineWidth = 1;
  ctx.stroke();

  ctx.restore();
}
