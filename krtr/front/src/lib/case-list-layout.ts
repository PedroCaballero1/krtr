/** How each case row is laid out: one line (wide columns) or stacked (narrow columns). */
export const CaseListLayout = {
  Row: "row",
  Stacked: "stacked",
} as const;

export type CaseListLayout = (typeof CaseListLayout)[keyof typeof CaseListLayout];
