import { useEffect, useRef, type ReactNode } from "react";

/** Inline, non-modal review: focus the scope, allow Escape, restore the initiating control. */
export function ReviewDialog({ label, onCancel, children, returnFocus }: {
  label: string; onCancel: () => void; children: ReactNode; returnFocus?: HTMLElement | null;
}) {
  const element = useRef<HTMLElement>(null);
  useEffect(() => {
    const trigger = returnFocus ?? (document.activeElement instanceof HTMLElement ? document.activeElement : null);
    element.current?.focus();
    return () => { if (trigger?.isConnected) trigger.focus({ preventScroll: true }); };
  }, [returnFocus]);
  return <aside ref={element} role="alertdialog" aria-label={label} aria-modal="false" tabIndex={-1}
    onKeyDown={event => {
      if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); onCancel(); }
    }}>{children}</aside>;
}
