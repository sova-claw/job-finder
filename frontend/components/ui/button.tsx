import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-full text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/40 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-[var(--accent)] text-white hover:bg-[var(--accent-strong)]",
        secondary: "bg-white/10 text-[var(--text-primary)] hover:bg-white/15",
        ghost: "text-[var(--text-secondary)] hover:bg-white/8 hover:text-[var(--text-primary)]",
        outline: "border border-white/10 bg-black/10 text-[var(--text-primary)] hover:bg-white/6",
        destructive: "bg-[var(--signal-red)]/14 text-[var(--signal-red)] hover:bg-[var(--signal-red)]/20",
        link: "text-[var(--accent-strong)] underline-offset-4 hover:underline"
      },
      size: {
        default: "h-10 px-4",
        xs: "h-7 px-2.5 text-xs",
        sm: "h-8 px-3 text-xs uppercase tracking-[0.16em]",
        lg: "h-11 px-5",
        icon: "size-10 rounded-full",
        "icon-sm": "size-8 rounded-full",
        "icon-lg": "size-11 rounded-full"
      }
    },
    defaultVariants: {
      variant: "default",
      size: "default"
    }
  }
);

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
  }) {
  const Comp = asChild ? Slot.Root : "button";

  return <Comp className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}

export { Button, buttonVariants };
