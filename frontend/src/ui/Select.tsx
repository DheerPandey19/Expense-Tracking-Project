import type { ReactNode, SelectHTMLAttributes } from "react";
import { wobblySm } from "./tokens";

type Props = SelectHTMLAttributes<HTMLSelectElement> & {
  label?: ReactNode;
};

export default function Select({
  label,
  className = "",
  id,
  style,
  children,
  ...props
}: Props) {
  const select = (
    <select
      id={id}
      className={[
        "w-full min-h-12 border-2 border-ink bg-white px-3 py-2 text-ink",
        "focus:border-pen focus:outline-none focus:ring-2 focus:ring-pen/20",
        className,
      ].join(" ")}
      style={{ borderRadius: wobblySm, ...style }}
      {...props}
    >
      {children}
    </select>
  );

  if (!label) return select;

  return (
    <label className="grid gap-1 font-body text-lg" htmlFor={id}>
      <span>{label}</span>
      {select}
    </label>
  );
}
