import React from "react";

/**
 * Minimal line-icon set (Lucide-style, 24×24, currentColor stroke).
 * Keeps the UI emoji-free and consistent. Pass `name`, optional `size`.
 */
const PATHS = {
  beaker: (
    <>
      <path d="M9 3h6" />
      <path d="M10 3v5.5L4.8 17A2 2 0 0 0 6.6 20h10.8a2 2 0 0 0 1.8-3L14 8.5V3" />
      <path d="M7.5 14.5h9" />
    </>
  ),
  shield: <path d="M12 3l7 3v5c0 4.6-3 7.5-7 8.6C8 18.5 5 15.6 5 11V6l7-3z" />,
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.35-4.35" />
    </>
  ),
  folder: (
    <path d="M3 7a2 2 0 0 1 2-2h3.4l2 2H19a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
  ),
  sparkles: (
    <>
      <path d="M12 4l1.7 4.3L18 10l-4.3 1.7L12 16l-1.7-4.3L6 10l4.3-1.7z" />
      <path d="M18.5 15l.6 1.6 1.6.6-1.6.6-.6 1.6-.6-1.6-1.6-.6 1.6-.6z" />
    </>
  ),
  lineage: (
    <>
      <circle cx="12" cy="12" r="3.2" />
      <path d="M3 12h5.6" />
      <path d="M15.4 12H21" />
    </>
  ),
  logout: (
    <>
      <path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3" />
      <path d="M10 17l-5-5 5-5" />
      <path d="M5 12h11" />
    </>
  ),
  arrowRight: <path d="M5 12h14M13 6l6 6-6 6" />,
  chart: (
    <>
      <path d="M4 20V10" />
      <path d="M10 20V4" />
      <path d="M16 20v-7" />
      <path d="M3 20h18" />
    </>
  ),
  graph: (
    <>
      <circle cx="6" cy="6" r="2.2" />
      <circle cx="18" cy="7" r="2.2" />
      <circle cx="12" cy="17" r="2.2" />
      <path d="M7.8 7.3l2.6 8M16.4 8.6L13.4 15.4M8 6.4l7.8.4" />
    </>
  ),
};

export default function Icon({ name, size = 20, className = "", strokeWidth = 1.75 }) {
  const body = PATHS[name];
  if (!body) return null;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {body}
    </svg>
  );
}
