import Image from "next/image";
import Link from "next/link";

/**
 * Original sprout mark, drawn for this project.
 *
 * Inline SVG using currentColor, so it inherits the surrounding text colour
 * and stays crisp at any size. This is the drop-in alternative to
 * /img/logomark.png -- see the note on <Logo> below.
 */
export function SproutMark({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden
      className={className}
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Centre shoot */}
      <path
        d="M12 22V9"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
      {/* Upper leaf, curling right */}
      <path
        d="M12 9c0-3.6 2-6.4 5.2-7.4C17.7 5.2 15.6 8.4 12 9Z"
        fill="currentColor"
      />
      {/* Lower leaf, curling left */}
      <path
        d="M12 14c-3.1 0-5.6-1.9-6.5-4.9 3.4-.4 6.1 1.5 6.5 4.9Z"
        fill="currentColor"
      />
      {/* Ground line — this is a depot/land tool, not just a plant */}
      <path
        d="M6.5 22h11"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

/**
 * The brand lockup: mark on the left, wordmark on the right, linking home.
 * Used on every screen so the header is the way back out of any flow.
 *
 * `tone="dark"` is for placing over the photograph on the auth screens.
 *
 * On light surfaces the mark sits in a deep-forest badge. The supplied
 * logomark.png is lime (#83F675), which measures about 1.3:1 against the pale
 * mint page -- effectively invisible on its own. The badge is what makes it
 * legible; do not remove it and leave a bare lime mark on a light background.
 *
 * To switch to the original mark instead of the supplied PNG, set
 * USE_SUPPLIED_MARK to false. The PNG is a 22px raster and is soft above that
 * size; SproutMark is vector and recolours itself.
 */
const USE_SUPPLIED_MARK = true;

export function Logo({
  tone = "light",
  className = "",
}: {
  /** "light" = on a light surface. "dark" = over a photo or dark panel. */
  tone?: "light" | "dark";
  className?: string;
}) {
  const onDark = tone === "dark";

  return (
    <Link
      href="/"
      aria-label="Kilimo Hakika — home"
      className={`group inline-flex items-center gap-2.5 ${className}`}
    >
      <span
        className={`flex size-9 shrink-0 items-center justify-center rounded-lg transition-transform duration-300 group-hover:scale-105 motion-reduce:transition-none motion-reduce:group-hover:scale-100 ${
          onDark ? "bg-white/10 backdrop-blur-sm" : "bg-primary"
        }`}
      >
        {USE_SUPPLIED_MARK ? (
          <Image
            src="/img/logomark.png"
            alt=""
            width={22}
            height={22}
            className="size-[22px]"
          />
        ) : (
          <SproutMark
            className={`size-5 ${onDark ? "text-[#83f675]" : "text-[#83f675]"}`}
          />
        )}
      </span>

      <span
        className={`font-heading text-lg leading-none tracking-wide ${
          onDark ? "text-white" : "text-foreground"
        }`}
      >
        KILIMO HAKIKA
      </span>
    </Link>
  );
}
