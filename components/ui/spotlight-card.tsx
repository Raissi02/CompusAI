"use client";

import { useReducedMotion } from "motion/react";
import type { HTMLAttributes, PointerEvent } from "react";
import { cn } from "@/lib/utils";

function SpotlightCard({
  children,
  className,
  onPointerMove,
  onPointerLeave,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  const reduceMotion = useReducedMotion();

  function trackPointer(event: PointerEvent<HTMLDivElement>) {
    onPointerMove?.(event);
    if (reduceMotion) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    event.currentTarget.style.setProperty("--spotlight-x", `${event.clientX - bounds.left}px`);
    event.currentTarget.style.setProperty("--spotlight-y", `${event.clientY - bounds.top}px`);
  }

  function clearPointer(event: PointerEvent<HTMLDivElement>) {
    onPointerLeave?.(event);
    event.currentTarget.style.removeProperty("--spotlight-x");
    event.currentTarget.style.removeProperty("--spotlight-y");
  }

  return (
    <div
      {...props}
      className={cn("program-spotlight", className)}
      onPointerMove={trackPointer}
      onPointerLeave={clearPointer}
    >
      {children}
    </div>
  );
}

export { SpotlightCard };
