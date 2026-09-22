import type { ButtonHTMLAttributes } from "react";
import { wobblySm } from "./tokens";

type Variant = "primary" | "secondary" | "danger" | "ghost";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
};

const variants: Record<Variant, string> = {
  primary:
    "bg-white text-ink border-ink hover:bg-accent hover:text-white active:shadow-none",
  secondary:
    "bg-muted text-ink border-ink hover:bg-pen hover:text-white active:shadow-none",
  danger:
    "bg-white text-ink border-ink hover:bg-accent hover:text-white active:shadow-none",
  ghost:
    "bg-transparent text-ink border-dashed border-ink shadow-none hover:bg-muted active:translate-x-0.5 active:translate-y-0.5",
};

export default function Button({
  variant = "primary",
  className = "",
  style,
  type = "button",
  ...props
}: Props) {
  return (
    <button
      type={type}
      className={[
        "inline-flex min-h-12 items-center justify-center gap-2 border-[3px] px-4 py-2",
        "font-body text-lg transition-transform duration-100",
        "shadow-[4px_4px_0px_0px_#2d2d2d]",
        "hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_#2d2d2d]",
        "active:translate-x-[4px] active:translate-y-[4px]",
        "disabled:pointer-events-none disabled:opacity-50",
        variants[variant],
        className,
      ].join(" ")}
      style={{ borderRadius: wobblySm, ...style }}
      {...props}
    />
  );
}
