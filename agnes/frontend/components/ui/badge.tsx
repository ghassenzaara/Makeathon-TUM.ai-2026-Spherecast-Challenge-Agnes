import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-semibold select-none transition-colors",
  {
    variants: {
      variant: {
        default:  "border-[var(--border)] bg-white/5 text-[var(--foreground-muted)]",
        emerald:  "border-emerald-500/20 bg-emerald-500/10 text-emerald-400",
        amber:    "border-amber-500/20 bg-amber-500/10 text-amber-400",
        fuchsia:  "border-fuchsia-500/20 bg-fuchsia-500/10 text-fuchsia-400",
        cyan:     "border-cyan-500/20 bg-cyan-500/10 text-cyan-400",
        violet:   "border-violet-500/20 bg-violet-500/10 text-violet-400",
        orb:      "border-[rgba(168,212,239,0.25)] bg-[rgba(168,212,239,0.10)] text-[#a8d4ef]",
        outline:  "border-[var(--border)] bg-transparent text-[var(--foreground-muted)]",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
