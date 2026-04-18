import * as React from "react";
import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-md", className)}
      style={{ background: "rgba(255,255,255,0.06)" }}
      {...props}
    />
  );
}

export { Skeleton };
