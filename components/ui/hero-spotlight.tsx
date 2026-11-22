"use client";

import { useReducedMotion } from "motion/react";
import type { HTMLAttributes, PointerEvent } from "react";
import { cn } from "@/lib/utils";

function HeroSpotlight({ className, onPointerMove, ...props }: HTMLAttributes<HTMLDivElement>) {
  const reduceMotion = useReducedMotion();

  function trackPointer(event: PointerEvent<HTMLDivElement>) {
    onPointerMove?.(event);
    if (reduceMotion) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    event.currentTarget.style.setProperty("--hero-pointer-x", `${event.clientX - bounds.left}px`);
    event.currentTarget.style.setProperty("--hero-pointer-y", `${event.clientY - bounds.top}px`);
  }

  return (
    <div
      {...props}
      aria-hidden="true"
      className={cn("hero-spotlight", className)}
      onPointerMove={trackPointer}
    />
  );
}

export { HeroSpotlight };
