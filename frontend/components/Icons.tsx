/**
 * Small inline SVG icon set.
 *
 * Inline rather than an icon package: no dependency, no extra request, and
 * they inherit the surrounding text colour.
 */

type IconProps = { className?: string };

const base = "h-5 w-5";

export function GitHubIcon({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <path d="M12 .5C5.73.5.5 5.73.5 12a11.5 11.5 0 0 0 7.86 10.92c.58.1.79-.25.79-.55v-1.94c-3.2.7-3.88-1.54-3.88-1.54-.53-1.34-1.29-1.7-1.29-1.7-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.7 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.46.11-3.05 0 0 .96-.3 3.15 1.18a10.9 10.9 0 0 1 5.74 0c2.18-1.48 3.14-1.18 3.14-1.18.63 1.59.23 2.76.12 3.05.74.81 1.18 1.84 1.18 3.1 0 4.43-2.69 5.41-5.25 5.69.41.36.78 1.06.78 2.14v3.17c0 .3.2.66.8.55A11.5 11.5 0 0 0 23.5 12C23.5 5.73 18.27.5 12 .5Z" />
    </svg>
  );
}

export function TargetIcon({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"
         strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="4.5" />
      <circle cx="12" cy="12" r="1" fill="currentColor" />
    </svg>
  );
}

export function CubeIcon({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"
         strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <path d="M12 2.8 20.5 7v10L12 21.2 3.5 17V7L12 2.8Z" />
      <path d="M3.5 7 12 11.4 20.5 7" />
      <path d="M12 11.4v9.8" />
    </svg>
  );
}

export function ShieldIcon({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"
         strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <path d="M12 2.8l7.5 3v6c0 4.3-3.1 8.1-7.5 9.4-4.4-1.3-7.5-5.1-7.5-9.4v-6l7.5-3Z" />
      <path d="M9.2 12.2l2 2 3.6-3.9" />
    </svg>
  );
}

export function DatabaseIcon({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"
         strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <ellipse cx="12" cy="6" rx="7.5" ry="3.2" />
      <path d="M4.5 6v6c0 1.8 3.4 3.2 7.5 3.2s7.5-1.4 7.5-3.2V6" />
      <path d="M4.5 12v6c0 1.8 3.4 3.2 7.5 3.2s7.5-1.4 7.5-3.2v-6" />
    </svg>
  );
}

export function UsersIcon({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"
         strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <circle cx="9" cy="8" r="3.3" />
      <path d="M2.8 20c0-3.2 2.8-5.5 6.2-5.5s6.2 2.3 6.2 5.5" />
      <path d="M16.5 5.2a3.3 3.3 0 0 1 0 6.1M18 14.9c2.1.7 3.5 2.4 3.5 4.6" />
    </svg>
  );
}

export function ForgeIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
         strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <path d="M4 20h16" />
      <path d="M7 20V9.5a5 5 0 0 1 10 0V20" />
      <path d="M12 4.5V2.8" />
      <path d="M9.5 13.5h5" />
    </svg>
  );
}

export function ArrowIcon({ className = "h-4 w-4" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
         strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <path d="M5 12h13M13 6l6 6-6 6" />
    </svg>
  );
}
