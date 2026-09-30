import type { JSX, ReactNode } from "react";

/**
 * The small red uppercase label the design places above every page title
 * ("Soporte al cliente", "Inicio", "Soporte", "Sesión").
 *
 * Exists so that eyebrow style is defined once instead of repeated as a
 * class string on each screen.
 *
 * @param props.children - The label text.
 * @returns The styled label.
 */
export function Kicker({ children }: { children: ReactNode }): JSX.Element {
  return (
    <span className="text-xs font-bold tracking-[0.12em] text-brand-700 uppercase">{children}</span>
  );
}
