import type { JSX, ReactNode } from "react";
import { cn } from "cn";

interface LabeledValueProps {
  label: ReactNode;
  children: ReactNode;
  className?: string;
}

/**
 * A tiny uppercase caption stacked over a bold value (e.g. "N.º de
 * cliente" over "048213").
 *
 * Exists because the design uses this pairing for every at-a-glance fact:
 * the header's customer number and session timer, and the chat's case id.
 *
 * @param props.label - The caption above the value.
 * @param props.children - The value itself.
 * @param props.className - Extra classes for the wrapper (e.g. a divider).
 * @returns The stacked caption and value.
 */
export function LabeledValue({ label, children, className }: LabeledValueProps): JSX.Element {
  return (
    <div className={cn("flex flex-col leading-tight", className)}>
      <span className="text-[11px] tracking-[0.08em] text-neutral-700 uppercase">{label}</span>
      <strong className="text-base tabular-nums">{children}</strong>
    </div>
  );
}
