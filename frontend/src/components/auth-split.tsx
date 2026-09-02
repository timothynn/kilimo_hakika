import Image from "next/image";
import Link from "next/link";

/**
 * Full-screen split auth layout: photograph on the left, form panel on the
 * right, stacked on small screens.
 *
 * The photo is decorative — it carries no information, so it is marked
 * aria-hidden and the panel works fine if the image never loads. On mobile it
 * shrinks to a short banner rather than pushing the form below the fold: the
 * point of this screen is the form.
 */
export function AuthSplit({
  image,
  imageAlt,
  eyebrow,
  headline,
  tagline,
  children,
}: {
  image: string;
  imageAlt: string;
  eyebrow: string;
  headline: string;
  tagline: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      {/* ------------------------------------------------------------ Photo */}
      <div className="relative h-44 overflow-hidden sm:h-56 lg:h-auto">
        <Image
          src={image}
          alt={imageAlt}
          fill
          priority
          sizes="(max-width: 1024px) 100vw, 50vw"
          className="animate-slow-zoom object-cover"
        />

        {/* Deep-forest wash so white type stays legible over any part of the
            photograph, rather than hoping the crop happens to be dark. */}
        <div
          aria-hidden
          className="absolute inset-0 bg-gradient-to-t from-[#052118]/95 via-[#052118]/60 to-[#052118]/30"
        />

        <div className="absolute inset-0 flex flex-col justify-end gap-3 p-6 sm:p-10 lg:justify-center lg:p-14">
          <span className="animate-fade-up font-heading text-sm tracking-[0.2em] text-[#83f675] uppercase">
            {eyebrow}
          </span>
          <h1
            className="animate-fade-up font-heading text-3xl leading-tight tracking-wide text-white sm:text-4xl lg:text-5xl"
            style={{ animationDelay: "90ms" }}
          >
            {headline}
          </h1>
          <p
            className="animate-fade-up max-w-md text-sm text-white/80 sm:text-base"
            style={{ animationDelay: "180ms" }}
          >
            {tagline}
          </p>
        </div>
      </div>

      {/* ------------------------------------------------------------ Panel */}
      <div className="bg-card flex items-center justify-center px-4 py-10 sm:px-10">
        <div className="animate-fade-up w-full max-w-md" style={{ animationDelay: "120ms" }}>
          <Link
            href="/"
            className="font-heading text-muted-foreground hover:text-foreground mb-8 inline-block text-lg tracking-wide"
          >
            KILIMO HAKIKA
          </Link>
          {children}
        </div>
      </div>
    </div>
  );
}

/**
 * Input wrapped with a leading icon and a label notched into the border, as
 * in the reference. The label sits on the border rather than above the field
 * so a stack of these reads as one block.
 */
export function IconField({
  id,
  label,
  icon,
  hint,
  children,
}: {
  id: string;
  label: string;
  icon: React.ReactNode;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="relative">
        <label
          htmlFor={id}
          className="bg-card text-muted-foreground absolute -top-2 left-3 z-10 px-1.5 text-xs font-medium"
        >
          {label}
        </label>
        <span
          aria-hidden
          className="text-muted-foreground pointer-events-none absolute top-1/2 left-4 z-10 -translate-y-1/2"
        >
          {icon}
        </span>
        {children}
      </div>
      {hint && <p className="text-muted-foreground pl-1 text-xs">{hint}</p>}
    </div>
  );
}
