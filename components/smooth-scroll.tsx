"use client";

import { useEffect, type ReactNode } from "react";
import Lenis from "lenis";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

export function SmoothScroll({ children }: { children: ReactNode }) {
  useEffect(() => {
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    let lenis: Lenis | null = null;

    function tick(time: number) {
      lenis?.raf(time * 1000);
    }

    function stop() {
      gsap.ticker.remove(tick);
      lenis?.destroy();
      lenis = null;
    }

    function start() {
      if (preference.matches || lenis) return;
      lenis = new Lenis({
        anchors: true,
        autoRaf: false,
        lerp: 0.1,
        prevent: (node) => Boolean(node.closest(".chat-messages, .candidate-detail, .candidate-table-section")),
        respectReducedMotion: true,
        smoothWheel: true,
      });
      lenis.on("scroll", ScrollTrigger.update);
      gsap.ticker.add(tick);
      gsap.ticker.lagSmoothing(0);
    }

    function onPreferenceChange() {
      if (preference.matches) stop();
      else start();
    }

    start();
    preference.addEventListener("change", onPreferenceChange);
    return () => {
      preference.removeEventListener("change", onPreferenceChange);
      stop();
    };
  }, []);

  return children;
}
