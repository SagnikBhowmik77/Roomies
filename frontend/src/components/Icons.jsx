// Inline SVG icon set — UI chrome never uses emoji (emoji is reserved for
// content: gifts and reactions). 1.5px strokes, currentColor throughout.

const base = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

function I({ size = 16, children, ...rest }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base} {...rest}>
      {children}
    </svg>
  );
}

export const MicIcon = (p) => (
  <I {...p}>
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M5 11a7 7 0 0 0 14 0" />
    <path d="M12 18v3" />
  </I>
);

export const MicOffIcon = (p) => (
  <I {...p}>
    <path d="M9 6a3 3 0 0 1 6 0v5" />
    <path d="M5 11a7 7 0 0 0 11.4 5.4M19 11a6.9 6.9 0 0 1-.4 2.4" />
    <path d="M12 18v3" />
    <path d="M3 3l18 18" />
  </I>
);

export const UsersIcon = (p) => (
  <I {...p}>
    <circle cx="9" cy="8" r="3.2" />
    <path d="M3.5 20c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5" />
    <path d="M15.5 5.6a3.2 3.2 0 0 1 0 4.8M17.8 15.4c1.6.8 2.5 2.3 2.7 4.6" />
  </I>
);

export const CoinIcon = (p) => (
  <I {...p}>
    <circle cx="12" cy="12" r="8.2" />
    <circle cx="12" cy="12" r="4.6" />
    <path d="M12 9.6v4.8" />
  </I>
);

export const BellIcon = (p) => (
  <I {...p}>
    <path d="M6 9.5a6 6 0 0 1 12 0c0 4 1.5 5.5 1.5 5.5h-15S6 13.5 6 9.5" />
    <path d="M10 18.5a2.1 2.1 0 0 0 4 0" />
  </I>
);

export const RadioIcon = (p) => (
  <I {...p}>
    <circle cx="12" cy="12" r="2" />
    <path d="M7.8 7.8a6 6 0 0 0 0 8.4M16.2 7.8a6 6 0 0 1 0 8.4" />
    <path d="M4.9 4.9a10 10 0 0 0 0 14.2M19.1 4.9a10 10 0 0 1 0 14.2" />
  </I>
);

export const SendIcon = (p) => (
  <I {...p}>
    <path d="M4 12L20 4l-4.5 16-3.9-6.5L4 12z" />
    <path d="M11.6 13.5L20 4" />
  </I>
);

export const ShareIcon = (p) => (
  <I {...p}>
    <circle cx="6" cy="12" r="2.6" />
    <circle cx="17.5" cy="5.5" r="2.6" />
    <circle cx="17.5" cy="18.5" r="2.6" />
    <path d="M8.4 10.8l6.8-4M8.4 13.2l6.8 4" />
  </I>
);

export const GiftIcon = (p) => (
  <I {...p}>
    <rect x="4" y="9" width="16" height="4" rx="1" />
    <path d="M6 13v7h12v-7M12 9v11" />
    <path d="M12 9c-4.5 0-5.5-2.3-4.3-3.9C9 3.5 11 4.5 12 9zM12 9c4.5 0 5.5-2.3 4.3-3.9C15 3.5 13 4.5 12 9z" />
  </I>
);

export const CrownIcon = (p) => (
  <I {...p}>
    <path d="M4 18h16M4 18l-1-9 5 3.5L12 6l4 6.5L21 9l-1 9" />
  </I>
);

export const LogoutIcon = (p) => (
  <I {...p}>
    <path d="M14 4h-8v16h8" />
    <path d="M10 12h11M18 8.5L21.5 12 18 15.5" />
  </I>
);

export const WaveIcon = (p) => (
  <I {...p}>
    <path d="M4 10v4M8 7v10M12 4v16M16 7v10M20 10v4" />
  </I>
);

export const ArrowIcon = (p) => (
  <I {...p}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </I>
);

export const PlusIcon = (p) => (
  <I {...p}>
    <path d="M12 5v14M5 12h14" />
  </I>
);

export const CheckIcon = (p) => (
  <I {...p}>
    <path d="M4.5 12.5l5 5L19.5 7" />
  </I>
);

/** Animated equalizer bars — the "this room is alive" signature mark. */
export function Equalizer({ active = true }) {
  return (
    <span className={`eq${active ? " on" : ""}`} aria-hidden>
      <i /><i /><i /><i />
    </span>
  );
}
