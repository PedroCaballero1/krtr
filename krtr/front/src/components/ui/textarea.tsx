import * as React from "react";
import { cn } from "cn";

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex min-h-22 w-full resize-y border-2 border-border bg-surface px-3 py-2 text-base text-foreground caret-primary transition-colors outline-none placeholder:text-muted-foreground hover:border-foreground/45 focus-visible:border-primary focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

export { Textarea };
