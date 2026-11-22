"use client";

import { useReducedMotion } from "motion/react";
import type { HTMLAttributes, PointerEvent } from "react";
import { cn } from "@/lib/utils";

function MagicCard({ children, className, onPointerMove, onPointerLeave, ...props }: HTMLAttributes<HTMLDivElement>) {
  const reduceMotion = useReducedMotion();

  function trackPointer(event: PointerEvent<HTMLDivElement>) {
    onPointerMove?.(event);
    if (reduceMotion) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    event.currentTarget.style.setProperty("--pointer-x", `${event.clientX - bounds.left}px`);
    event.currentTarget.style.setProperty("--pointer-y", `${event.clientY - bounds.top}px`);
  }

  function clearPointer(event: PointerEvent<HTMLDivElement>) {
    onPointerLeave?.(event);
    event.currentTarget.style.removeProperty("--pointer-x");
    event.currentTarget.style.removeProperty("--pointer-y");
  }

  return (
    <div
      {...props}
      className={cn("magic-card", className)}
      onPointerMove={trackPointer}
      onPointerLeave={clearPointer}
    >
      <span className="magic-card-glow" aria-hidden="true" />
      {children}
    </div>
  );
}

export { MagicCard };
