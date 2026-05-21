import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        // accent = signal #FF6A3D (оранжевый), --brand-ink даёт контраст ~6.5 vs ~3.0 у white
        default:
          "border-transparent bg-[var(--accent)] text-[var(--brand-ink,#15161a)]",
        secondary:
          "border-transparent bg-[var(--bg-elevated)] text-[var(--fg)] border-[var(--border)]",
        // destructive — семантический --error, работает в обеих темах
        destructive:
          "border-transparent bg-[var(--error-20)] text-[var(--error)]",
        outline:
          "text-[var(--fg)] border-[var(--border)]",
      },
    },
    defaultVariants: {
      variant: "secondary",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
