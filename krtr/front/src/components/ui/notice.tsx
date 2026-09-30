import type { ComponentProps, JSX } from "react";
import { cn } from "cn";

/**
 * The red-tinted message box the design uses for every inline notice:
 * errors, "Caso no encontrado", microphone denied, the logout reason.
 *
 * Exists so those messages share one look; callers pass `role="alert"`
 * when the message must be announced.
 *
 * @param props - Standard `div` props; `className` is merged last.
 * @returns The styled notice.
 */
export function Notice({ className, ...props }: ComponentProps<"div">): JSX.Element {
  return (
    <div className={cn("bg-brand-100 px-4 py-3 text-sm text-brand-800", className)} {...props} />
  );
}
