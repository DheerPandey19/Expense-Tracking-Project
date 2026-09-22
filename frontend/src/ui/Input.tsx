import type { InputHTMLAttributes, ReactNode } from "react";
import { wobblySm } from "./tokens";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  label?: ReactNode;
};

export default function Input({
  label,
  className = "",
  id,
  style,
  ...props
}: Props) {
  const input = (
    <input
      id={id}
      className={[
        "w-full min-h-12 border-2 border-ink bg-white px-3 py-2 text-ink",
        "placeholder:text-ink/40",
        "focus:border-pen focus:outline-none focus:ring-2 focus:ring-pen/20",
        className,
      ].join(" ")}
      style={{ borderRadius: wobblySm, ...style }}
      {...props}
    />
  );

  if (!label) return input;

  return (
    <label className="grid gap-1 font-body text-lg" htmlFor={id}>
      <span>{label}</span>
      {input}
    </label>
  );
}
