/**
 * Icons.
 *
 * Inline SVG rather than an icon package: there are a dozen of them, they all
 * inherit `currentColor`, and a dependency for that is not worth the install.
 * Every icon is on a 24-unit grid with a 1.75 stroke so they sit together.
 */

type IconProps = { className?: string };

const base = "h-4 w-4";

function Svg({
  className,
  children,
}: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      className={className ?? base}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export function LogoMark({ className }: IconProps) {
  return (
    <svg
      className={className ?? "h-7 w-7"}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
    >
      <rect
        x="2.5"
        y="2.5"
        width="27"
        height="27"
        rx="8"
        fill="var(--accent-soft)"
        stroke="var(--accent)"
        strokeWidth="1.5"
      />
      {/* An anvil: the "forge" half of the name. */}
      <path
        d="M9 13h9a4 4 0 0 1 4 4h1M9 13v6M9 19h11M12 19v3.5M17 19v3.5M10 22.5h9"
        stroke="var(--accent)"
        strokeWidth="1.9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function GitHubIcon({ className }: IconProps) {
  return (
    <svg
      className={className ?? base}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M12 .5A11.5 11.5 0 0 0 .5 12a11.5 11.5 0 0 0 7.86 10.92c.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.37-3.88-1.37-.53-1.35-1.29-1.71-1.29-1.71-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.2 1.77 1.2 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.7 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11 11 0 0 1 5.79 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.12 3.05.74.81 1.19 1.84 1.19 3.1 0 4.43-2.7 5.4-5.27 5.69.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56A11.5 11.5 0 0 0 23.5 12 11.5 11.5 0 0 0 12 .5Z" />
    </svg>
  );
}

export function DockerIcon({ className }: IconProps) {
  return (
    <svg
      className={className ?? base}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M13.5 9.5h2.4v2.2h-2.4zm-3 0h2.4v2.2h-2.4zm-3 0h2.4v2.2H7.5zm-3 0h2.4v2.2H4.5zm3-2.9h2.4v2.2H7.5zm3 0h2.4v2.2h-2.4zm3 0h2.4v2.2h-2.4zm-3-2.9h2.4v2.2h-2.4zM23 11.2c-.5-.35-1.7-.48-2.6-.3-.12-.87-.6-1.63-1.45-2.3l-.5-.33-.33.5c-.42.63-.6 1.5-.54 2.32.03.3.13.82.44 1.28-.3.17-.9.4-1.7.38H1.32l-.05.28c-.15.87-.15 3.57 1.6 5.65C4.2 20.3 6.55 21.1 9.8 21.1c7.03 0 12.24-3.24 14.68-9.12l.14-.35-.3-.2z" />
    </svg>
  );
}

export function BoxIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M21 8 12 3 3 8v8l9 5 9-5V8Z" />
      <path d="m3 8 9 5 9-5M12 13v8" />
    </Svg>
  );
}

export function RocketIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09Z" />
      <path d="M12 15 9 12a11 11 0 0 1 2-7.5C12.8 2.2 15.5 2 19 2c0 3.5-.2 6.2-2.5 8A11 11 0 0 1 9 12" />
      <path d="M9 12H5s.55-3.03 2-4h4M12 15v4s3.03-.55 4-2v-4" />
    </Svg>
  );
}

export function PlayIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="m6 3 14 9-14 9V3Z" fill="currentColor" strokeWidth="1" />
    </Svg>
  );
}

export function StopIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" strokeWidth="1" />
    </Svg>
  );
}

export function RestartIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M3 12a9 9 0 0 1 15.5-6.2L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-15.5 6.2L3 16" />
      <path d="M3 21v-5h5" />
    </Svg>
  );
}

export function TrashIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v5M14 11v5" />
    </Svg>
  );
}

export function ExternalIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M14 3h7v7M21 3l-9 9M19 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h5" />
    </Svg>
  );
}

export function CheckIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="m20 6-11 11-5-5" />
    </Svg>
  );
}

export function AlertIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M12 9v4M12 17h.01" />
      <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
    </Svg>
  );
}

export function ClockIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </Svg>
  );
}

export function ShieldIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />
    </Svg>
  );
}

export function UsersIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
    </Svg>
  );
}

export function TerminalIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="m4 17 6-5-6-5M12 19h8" />
    </Svg>
  );
}

export function SearchIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </Svg>
  );
}

export function ChevronRight({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="m9 18 6-6-6-6" />
    </Svg>
  );
}

export function ArrowLeft({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M19 12H5M12 19l-7-7 7-7" />
    </Svg>
  );
}

export function FolderIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.7-.9L9.9 3.9A2 2 0 0 0 8.2 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" />
    </Svg>
  );
}

export function KeyIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <circle cx="7.5" cy="15.5" r="4.5" />
      <path d="m10.7 12.3 8.8-8.8M17 6l2.5 2.5M14.5 8.5 17 11" />
    </Svg>
  );
}

export function ServerIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <rect x="2" y="3" width="20" height="7" rx="2" />
      <rect x="2" y="14" width="20" height="7" rx="2" />
      <path d="M6 6.5h.01M6 17.5h.01" />
    </Svg>
  );
}
