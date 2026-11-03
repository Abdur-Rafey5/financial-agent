"use client";

import { useMemo } from "react";

/**
 * Lightweight dependency-free SVG/CSS charts.
 */

export interface Series {
  name: string;
  color: string;
  data: number[];
}

export function LineChart({
  series,
  labels,
  height = 240,
  formatValue,
}: {
  series: Series[];
  labels: string[];
  height?: number;
  formatValue?: (value: number) => string;
}) {
  const width = 640;
  const padding = { top: 16, right: 16, bottom: 30, left: 56 };

  const { maxValue, minValue, paths, points, yTicks, xTicks } = useMemo(() => {
    const all = series.flatMap((s) => s.data);
    if (!all.length) {
      return {
        maxValue: 1,
        minValue: 0,
        paths: [] as { color: string; d: string }[],
        points: [] as { x: number; y: number; values: number[] }[],
        yTicks: [] as { y: number; value: number }[],
        xTicks: [] as { x: number; label: string }[],
      };
    }
    const maxValue = Math.max(...all, 0);
    const minValue = Math.min(...all, 0);
    const span = maxValue - minValue || 1;
    const innerWidth = width - padding.left - padding.right;
    const innerHeight = height - padding.top - padding.bottom;

    const xFor = (index: number) =>
      padding.left +
      (labels.length <= 1 ? innerWidth / 2 : (index / (labels.length - 1)) * innerWidth);
    const yFor = (value: number) =>
      padding.top + innerHeight - ((value - minValue) / span) * innerHeight;

    const paths = series.map((s) => {
      const coords = s.data.map((value, index) => `${xFor(index)},${yFor(value)}`);
      return { color: s.color, d: `M ${coords.join(" L ")}` };
    });

    const points = labels.map((_, index) => ({
      x: xFor(index),
      y: yFor(0),
      values: series.map((s) => s.data[index] ?? 0),
    }));

    const yTicks = [0, 1, 2, 3, 4].map((step) => {
      const value = minValue + (span / 4) * step;
      return { y: yFor(value), value };
    });

    const xTicks = labels.map((label, index) => {
      if (labels.length <= 6 || index % Math.ceil(labels.length / 6) === 0) {
        return { x: xFor(index), label };
      }
      return null;
    });

    return {
      maxValue,
      minValue,
      paths,
      points,
      yTicks: yTicks.filter((t) => Number.isFinite(t.y)),
      xTicks: xTicks.filter(
        (t): t is { x: number; label: string } => t !== null
      ),
    };
  }, [series, labels, height, padding.bottom, padding.left, padding.right, padding.top]);

  if (!labels.length) return null;

  const fmt = formatValue ?? ((v: number) => v.toLocaleString("en-US"));

  return (
    <div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img">
        {/* Grid */}
        {yTicks.map((tick, index) => (
          <g key={`y-${index}`}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={tick.y}
              y2={tick.y}
              stroke="rgba(148,163,184,0.12)"
              strokeWidth={1}
            />
          </g>
        ))}
        {yTicks.map((tick, index) => (
          <text
            key={`yt-${index}`}
            x={padding.left - 8}
            y={tick.y + 4}
            textAnchor="end"
            className="fill-slate-500"
            fontSize={10}
          >
            {fmt(tick.value)}
          </text>
        ))}

        {/* Paths */}
        {paths.map((path, index) => (
          <path
            key={`p-${index}`}
            d={path.d}
            fill="none"
            stroke={path.color}
            strokeWidth={2.5}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ))}

        {/* Point markers */}
        {points.map((point, index) =>
          point.values.map((value, seriesIndex) => {
            const y =
              padding.top +
              (height - padding.top - padding.bottom) -
              ((value - minValue) / (maxValue - minValue || 1)) *
                (height - padding.top - padding.bottom);
            return (
              <circle
                key={`pt-${index}-${seriesIndex}`}
                cx={point.x}
                cy={y}
                r={3}
                fill={series[seriesIndex]?.color ?? "#6366f1"}
              />
            );
          })
        )}

        {/* X labels */}
        {xTicks.map((tick, index) => (
          <text
            key={`x-${index}`}
            x={tick.x}
            y={height - padding.bottom + 20}
            textAnchor="middle"
            className="fill-slate-500"
            fontSize={10}
          >
            {tick.label}
          </text>
        ))}
      </svg>

      <div className="mt-3 flex flex-wrap items-center justify-center gap-4">
        {series.map((s) => (
          <span key={s.name} className="flex items-center gap-2 text-xs text-slate-400">
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: s.color }}
            />
            {s.name}
          </span>
        ))}
      </div>
    </div>
  );
}

export function BarList({
  items,
  currencySymbol = "",
  emptyLabel = "No data yet",
}: {
  items: { label: string; value: number; color?: string | null }[];
  currencySymbol?: string;
  emptyLabel?: string;
}) {
  if (!items.length) {
    return <p className="py-8 text-center text-sm text-slate-500">{emptyLabel}</p>;
  }
  const max = Math.max(...items.map((item) => item.value), 1);

  return (
    <div className="space-y-4">
      {items.map((item, index) => (
        <div key={`${item.label}-${index}`}>
          <div className="mb-1.5 flex items-center justify-between text-xs">
            <span className="font-medium text-slate-300">{item.label}</span>
            <span className="font-semibold text-slate-400">
              {currencySymbol}
              {item.value.toLocaleString("en-US", { maximumFractionDigits: 2 })}
            </span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${(item.value / max) * 100}%`,
                backgroundColor: item.color || "#6366f1",
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export function DonutChart({
  items,
  size = 200,
  centerLabel,
  centerValue,
}: {
  items: { label: string; value: number; color: string }[];
  size?: number;
  centerLabel?: string;
  centerValue?: string;
}) {
  const total = items.reduce((sum, item) => sum + item.value, 0);
  const radius = size / 2 - 14;
  const inner = radius * 0.62;
  const center = size / 2;

  let angle = -Math.PI / 2;
  const arcs = items.map((item) => {
    const share = total > 0 ? item.value / total : 0;
    const large = share > 0.5 ? 1 : 0;
    const x1 = center + radius * Math.cos(angle);
    const y1 = center + radius * Math.sin(angle);
    const endAngle = angle + share * Math.PI * 2;
    const x2 = center + radius * Math.cos(endAngle);
    const y2 = center + radius * Math.sin(endAngle);
    const ix1 = center + inner * Math.cos(endAngle);
    const iy1 = center + inner * Math.sin(endAngle);
    const ix2 = center + inner * Math.cos(angle);
    const iy2 = center + inner * Math.sin(angle);
    angle = endAngle;
    const d =
      share >= 0.999
        ? `M ${center},${center - radius} A ${radius},${radius} 0 1 1 ${center - 0.01},${center - radius} M ${center},${center - inner} A ${inner},${inner} 0 1 0 ${center + 0.01},${center - inner}`
        : `M ${x1},${y1} A ${radius},${radius} 0 ${large} 1 ${x2},${y2} L ${ix1},${iy1} A ${inner},${inner} 0 ${large} 0 ${ix2},${iy2} Z`;
    return { ...item, d, share };
  });

  if (!total) {
    return <p className="py-8 text-center text-sm text-slate-500">No data yet</p>;
  }

  return (
    <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-center">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="flex-shrink-0">
        {arcs.map((arc) => (
          <path key={arc.label} d={arc.d} fill={arc.color} opacity={0.9}>
            <title>{`${arc.label}: ${arc.share.toFixed(1)}%`}</title>
          </path>
        ))}
        {centerValue && (
          <text
            x={center}
            y={centerLabel ? center + 4 : center}
            textAnchor="middle"
            className="fill-white font-bold"
            fontSize={15}
          >
            {centerValue}
          </text>
        )}
        {centerLabel && (
          <text
            x={center}
            y={center - 16}
            textAnchor="middle"
            className="fill-slate-500"
            fontSize={10}
          >
            {centerLabel}
          </text>
        )}
      </svg>
      <div className="w-full min-w-0 space-y-2">
        {arcs.map((arc) => (
          <div key={arc.label} className="flex items-center justify-between gap-3 text-xs">
            <span className="flex min-w-0 items-center gap-2">
              <span
                className="h-2.5 w-2.5 flex-shrink-0 rounded-full"
                style={{ backgroundColor: arc.color }}
              />
              <span className="truncate text-slate-300">{arc.label}</span>
            </span>
            <span className="font-semibold text-slate-400">
              {arc.share.toFixed(1)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function StackedBars({
  labels,
  bars,
  formatValue,
}: {
  labels: string[];
  bars: { name: string; color: string; data: number[] }[];
  formatValue?: (value: number) => string;
}) {
  const max = Math.max(
    1,
    ...labels.map((_, i) => bars.reduce((sum, bar) => sum + Math.max(0, bar.data[i] ?? 0), 0))
  );
  const fmt = formatValue ?? ((v: number) => v.toLocaleString("en-US"));

  return (
    <div>
      <div className="flex items-end gap-3 overflow-x-auto pb-2" style={{ height: 200 }}>
        {labels.map((label, index) => {
          const total = bars.reduce((sum, bar) => sum + Math.max(0, bar.data[index] ?? 0), 0);
          return (
            <div key={label} className="flex min-w-[46px] flex-1 flex-col items-center gap-2">
              <div className="flex h-full w-full max-w-[42px] flex-col justify-end rounded-lg overflow-hidden">
                {bars.map((bar) => {
                  const value = Math.max(0, bar.data[index] ?? 0);
                  if (value <= 0) return null;
                  return (
                    <div
                      key={bar.name}
                      title={`${bar.name}: ${fmt(value)}`}
                      style={{
                        height: `${(value / max) * 170}px`,
                        backgroundColor: bar.color,
                      }}
                    />
                  );
                })}
              </div>
              <span className="text-[10px] text-slate-500">{label}</span>
              <span className="text-[10px] font-semibold text-slate-400">{fmt(total)}</span>
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-center gap-4">
        {bars.map((bar) => (
          <span key={bar.name} className="flex items-center gap-2 text-xs text-slate-400">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: bar.color }} />
            {bar.name}
          </span>
        ))}
      </div>
    </div>
  );
}
