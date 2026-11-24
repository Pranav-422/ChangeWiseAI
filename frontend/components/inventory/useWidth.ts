"use client";
import { useEffect, useRef, useState } from "react";

/** Width of an element, so a drawing can be laid out in real pixels and its text never scales. */
export function useWidth<T extends HTMLElement>(initial = 800) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(initial);
  useEffect(() => {
    if (!ref.current || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => entry && setWidth(Math.max(280, Math.round(entry.contentRect.width))));
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);
  return [ref, width] as const;
}
