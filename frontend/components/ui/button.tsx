import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "group/button btn-shimmer inline-flex shrink-0 items-center justify-center rounded-xl border border-transparent bg-clip-padding text-sm font-medium whitespace-nowrap outline-none select-none transition-all duration-300 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 hover:scale-[1.02] active:scale-[0.97] disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default:
          "accent-gradient text-slate-950 shadow-[0_0_24px_rgba(6,182,212,0.28)] hover:brightness-110 hover:shadow-[0_0_32px_rgba(16,185,129,0.35)]",
        outline:
          "border-slate-600/80 bg-slate-900/55 text-slate-100 hover:border-cyan-400/45 hover:bg-slate-800/75 hover:text-slate-50 hover:shadow-[0_0_20px_rgba(6,182,212,0.18)]",
        secondary:
          "border-slate-600/60 bg-slate-800/75 text-slate-100 hover:bg-slate-700/80 hover:border-emerald-400/30",
        ghost:
          "text-slate-300 hover:bg-slate-800/70 hover:text-slate-50",
        destructive:
          "bg-red-500/15 text-red-300 hover:bg-red-500/25 focus-visible:ring-red-400/30",
        link: "text-cyan-300 underline-offset-4 hover:underline",
      },
      size: {
        default:
          "h-9 gap-1.5 px-3 has-data-[icon=inline-end]:pr-2.5 has-data-[icon=inline-start]:pl-2.5",
        xs: "h-6 gap-1 rounded-lg px-2 text-xs [&_svg:not([class*='size-'])]:size-3",
        sm: "h-8 gap-1 rounded-lg px-2.5 text-[0.8rem] [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-10 gap-1.5 px-4",
        icon: "size-9",
        "icon-xs": "size-6 rounded-lg [&_svg:not([class*='size-'])]:size-3",
        "icon-sm": "size-8 rounded-lg",
        "icon-lg": "size-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
