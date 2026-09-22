import type { HTMLAttributes, ReactNode } from "react";
import { wobblyMd } from "./tokens";

type Decoration = "none" | "tape" | "tack";

type Props = Omit<HTMLAttributes<HTMLElement>, "title"> & {
  as?: "section" | "div" | "article";
  decoration?: Decoration;
  title?: string;
  children: ReactNode;
  rotate?: "none" | "left" | "right";
};

const rotateClass = {
  none: "",
  left: "-rotate-1",
  right: "rotate-1",
};

export default function Card({
  as: Tag = "section",
  decoration = "none",
  title,
  children,
  rotate = "none",
  className = "",
  style,
  ...props
}: Props) {
  return (
    <Tag
      className={[
        "relative bg-card border-[3px] border-ink p-5 md:p-6",
        "shadow-[4px_4px_0px_0px_#2d2d2d]",
        "transition-transform duration-100 hover:rotate-1",
        rotateClass[rotate],
        className,
      ].join(" ")}
      style={{ borderRadius: wobblyMd, ...style }}
      {...props}
    >
      {decoration === "tape" && (
        <span
          aria-hidden
          className="pointer-events-none absolute -top-3 left-1/2 h-5 w-16 -translate-x-1/2 rotate-2 bg-[#9ca3af]/45"
        />
      )}
      {decoration === "tack" && (
        <span
          aria-hidden
          className="pointer-events-none absolute -top-2 left-1/2 h-4 w-4 -translate-x-1/2 rounded-full bg-accent border-2 border-ink"
        />
      )}
      {title ? (
        <h2 className="mb-3 font-heading text-2xl md:text-3xl">{title}</h2>
      ) : null}
      {children}
    </Tag>
  );
}
