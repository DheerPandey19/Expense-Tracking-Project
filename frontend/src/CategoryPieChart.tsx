import type { CategoryTotal } from "./api";
import { wobblySm } from "./ui/tokens";

type Props = {
  categories: CategoryTotal[];
  total?: number;
};

function formatMoney(n: number) {
  return n.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return {
    x: cx + r * Math.cos(rad),
    y: cy + r * Math.sin(rad),
  };
}

function describeSlice(
  cx: number,
  cy: number,
  r: number,
  startAngle: number,
  endAngle: number,
) {
  const start = polarToCartesian(cx, cy, r, startAngle);
  const end = polarToCartesian(cx, cy, r, endAngle);
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  return [
    `M ${cx} ${cy}`,
    `L ${start.x} ${start.y}`,
    `A ${r} ${r} 0 ${largeArc} 1 ${end.x} ${end.y}`,
    "Z",
  ].join(" ");
}

export default function CategoryPieChart({ categories, total }: Props) {
  const slices = categories
    .filter((c) => c.total > 0)
    .map((c) => ({
      ...c,
      color: c.color ?? "#888888",
    }));

  const spendTotal =
    total !== undefined
      ? total
      : slices.reduce((sum, c) => sum + c.total, 0);

  if (slices.length === 0 || spendTotal <= 0) {
    return <p className="text-ink/70">No spending in this range to chart.</p>;
  }

  const size = 180;
  const cx = size / 2;
  const cy = size / 2;
  const r = 80;

  let angle = 0;
  const paths =
    slices.length === 1 ? (
      <circle
        key={slices[0].category_id}
        cx={cx}
        cy={cy}
        r={r}
        fill={slices[0].color}
        stroke="#2d2d2d"
        strokeWidth="3"
      />
    ) : (
      slices.map((slice) => {
        const sweep = (slice.total / spendTotal) * 360;
        const startAngle = angle;
        const endAngle = angle + sweep;
        angle = endAngle;
        return (
          <path
            key={slice.category_id}
            d={describeSlice(cx, cy, r, startAngle, endAngle)}
            fill={slice.color}
            stroke="#2d2d2d"
            strokeWidth="2"
          />
        );
      })
    );

  return (
    <div className="flex flex-wrap items-center gap-4 md:gap-6">
      <svg
        className="shrink-0 rotate-[-2deg]"
        viewBox={`0 0 ${size} ${size}`}
        width={size}
        height={size}
        role="img"
        aria-label="Spending by category"
      >
        {paths}
      </svg>
      <ul className="min-w-0 flex-1 basis-40 space-y-2">
        {slices.map((slice) => {
          const pct = (slice.total / spendTotal) * 100;
          return (
            <li key={slice.category_id} className="flex items-start gap-2 text-base md:text-lg">
              <span
                className="mt-1 inline-block h-3 w-3 shrink-0 border-2 border-ink"
                style={{ background: slice.color, borderRadius: wobblySm }}
                aria-hidden
              />
              <span>
                {slice.name}{" "}
                <span className="text-ink/60">
                  {formatMoney(slice.total)} · {pct.toFixed(0)}%
                </span>
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
