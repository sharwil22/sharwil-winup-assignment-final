// Small inline icon set (stroke icons, 24px grid). Decorative unless given a title.

interface IconProps {
  size?: number
  className?: string
}

function Svg({ size = 18, className, children }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  )
}

export const LogoMark = ({ size = 28 }: IconProps) => (
  <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
    <rect width="32" height="32" rx="8" fill="var(--brand-mark)" />
    <path d="M10 8h8l5 5v11a2 2 0 0 1-2 2H10a2 2 0 0 1-2-2V10a2 2 0 0 1 2-2z" fill="#fff" opacity="0.95" />
    <path d="M18 8v5h5" fill="none" stroke="var(--brand-mark)" strokeWidth="1.6" />
    <path d="M11.5 18.5l2.2 2.2 4.8-4.8" fill="none" stroke="var(--brand-mark)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)

export const PencilIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 20h9" />
    <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
  </Svg>
)

export const DownloadIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <path d="M7 10l5 5 5-5" />
    <path d="M12 15V3" />
  </Svg>
)

export const RefreshIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3 12a9 9 0 0 1 15.5-6.3L21 8" />
    <path d="M21 3v5h-5" />
    <path d="M21 12a9 9 0 0 1-15.5 6.3L3 16" />
    <path d="M3 21v-5h5" />
  </Svg>
)

export const ShieldIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
  </Svg>
)

export const InfoIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="10" />
    <path d="M12 16v-4" />
    <path d="M12 8h.01" />
  </Svg>
)

export const AlertIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
    <path d="M12 9v4" />
    <path d="M12 17h.01" />
  </Svg>
)

export const FileIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <path d="M14 2v6h6" />
    <path d="M8 13h8M8 17h5" />
  </Svg>
)

export const ListIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M9 6h11M9 12h11M9 18h11" />
    <path d="M4 6h.01M4 12h.01M4 18h.01" />
  </Svg>
)

export const ArrowUpIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 19V5" />
    <path d="M5 12l7-7 7 7" />
  </Svg>
)

export const QuoteIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3 21c3 0 7-1 7-8V5H3v7h4c0 4-2 6-4 6z" />
    <path d="M14 21c3 0 7-1 7-8V5h-7v7h4c0 4-2 6-4 6z" />
  </Svg>
)
