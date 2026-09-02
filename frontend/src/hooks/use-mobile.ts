import * as React from "react"

const MOBILE_BREAKPOINT = 768
const QUERY = `(max-width: ${MOBILE_BREAKPOINT - 1}px)`

/**
 * Rewritten from the shadcn default, which set state inside an effect and so
 * fails `react-hooks/set-state-in-effect` under this project's lint config.
 * useSyncExternalStore reads the media query during render instead, which also
 * removes the first-paint frame where the value was undefined.
 *
 * The server snapshot is false: SSR has no viewport, and the desktop sidebar
 * is the correct thing to render into before hydration.
 */
function subscribe(onChange: () => void) {
  const mql = window.matchMedia(QUERY)
  mql.addEventListener("change", onChange)
  return () => mql.removeEventListener("change", onChange)
}

export function useIsMobile() {
  return React.useSyncExternalStore(
    subscribe,
    () => window.matchMedia(QUERY).matches,
    () => false
  )
}
