import type { SVGProps } from "react";

export function Admission(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M4 19.5V4.5A2.5 2.5 0 0 1 6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5Z" />
      <path d="M8 7h6M8 11h8" />
    </svg>
  );
}

export function AiRobot(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 32 32" fill="none" aria-hidden="true" {...props}>
      <rect x="7" y="10" width="18" height="15" rx="6" fill="currentColor" opacity=".96" />
      <path d="M16 10V6" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
      <circle cx="16" cy="5" r="2.2" fill="currentColor" />
      <rect x="10.8" y="14" width="10.4" height="6.8" rx="3.4" fill="#fff" opacity=".95" />
      <circle cx="14" cy="17.4" r="1.1" fill="#0B5D4D" />
      <circle cx="18" cy="17.4" r="1.1" fill="#0B5D4D" />
      <path d="M12.8 22.1h6.4" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" opacity=".9" />
      <path d="M5 17h2M25 17h2" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
    </svg>
  );
}
