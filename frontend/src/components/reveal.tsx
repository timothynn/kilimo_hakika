"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Fades and lifts its children into view once, when scrolled to.
 *
 * IntersectionObserver plus a CSS transition — no animation library, because
 * the whole point of this app is that it loads on a low-end phone over a weak
 * connection.
 *
 * Reduced motion is handled in CSS via the `motion-reduce` variant rather
 * than by branching in JS: the hidden state is neutralised, so those readers
 * see the content immediately with no transition. Motion here is decoration,
 * never information.
 */
export function Reveal({
  children,
  delay = 0,
  className = "",
}: {
  children: React.ReactNode;
  /** Stagger in ms, for sequencing siblings. */
  delay?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setShown(true);
            // Reveal is one-way; stop observing so scrolling back up does
            // not re-animate content the reader has already seen.
            observer.disconnect();
          }
        }
      },
      { rootMargin: "0px 0px -10% 0px", threshold: 0.1 }
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      style={{ transitionDelay: shown ? `${delay}ms` : "0ms" }}
      className={`transition-all duration-700 ease-out motion-reduce:transition-none ${
        shown
          ? "translate-y-0 opacity-100"
          : "translate-y-6 opacity-0 motion-reduce:translate-y-0 motion-reduce:opacity-100"
      } ${className}`}
    >
      {children}
    </div>
  );
}
