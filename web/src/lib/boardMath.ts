// Coordinate math for the canvas board.

export const BOARD_SIZE = 15;

export interface BoardGeom {
  cssSize: number;     // canvas CSS size (square)
  margin: number;      // outer margin in CSS px
  cellPx: number;      // distance between adjacent grid lines in CSS px
  stoneRadius: number; // stone radius in CSS px
}

export function computeGeom(cssSize: number): BoardGeom {
  // Reserve margin for coordinate labels.
  const margin = Math.round(cssSize * 0.06);
  const inner = cssSize - margin * 2;
  const cellPx = inner / (BOARD_SIZE - 1);
  const stoneRadius = Math.min(cellPx * 0.45, cellPx / 2 - 1);
  return { cssSize, margin, cellPx, stoneRadius };
}

// Translate grid (r, c) → CSS pixel center.
export function cellToPx(geom: BoardGeom, r: number, c: number): { x: number; y: number } {
  return {
    x: geom.margin + c * geom.cellPx,
    y: geom.margin + r * geom.cellPx,
  };
}

// Translate a CSS pixel coord on the canvas into the nearest grid (r, c).
// Returns null if outside the board.
export function pxToCell(geom: BoardGeom, x: number, y: number): { r: number; c: number } | null {
  const c = Math.round((x - geom.margin) / geom.cellPx);
  const r = Math.round((y - geom.margin) / geom.cellPx);
  if (r < 0 || r >= BOARD_SIZE || c < 0 || c >= BOARD_SIZE) return null;
  // Reject if click is too far from intersection (more than half a cell).
  const cell = cellToPx(geom, r, c);
  const dx = cell.x - x;
  const dy = cell.y - y;
  if (Math.hypot(dx, dy) > geom.cellPx * 0.5) return null;
  return { r, c };
}

// Standard 15x15 star points.
export const STAR_POINTS: [number, number][] = [
  [3, 3], [3, 7], [3, 11],
  [7, 3], [7, 7], [7, 11],
  [11, 3], [11, 7], [11, 11],
];

export const COL_LABELS = "ABCDEFGHJKLMNOP".slice(0, BOARD_SIZE).split("");
// Skips 'I' is a Go convention; we keep all 15 letters straight for omok since it's typical for omok displays.
// We'll use A..O for 15.
