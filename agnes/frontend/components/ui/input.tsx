import * as React from "react";
import { cn } from "@/lib/utils";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      ref={ref}
      className={cn(
        "flex w-full rounded-lg border border-[var(--border)] bg-transparent px-3 py-2 text-sm",
        "text-[var(--foreground)] placeholder:text-[var(--foreground-muted)]",
        "outline-none focus:border-cyan-500/60 focus:ring-1 focus:ring-cyan-500/30 transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";

export { Input };
