import * as React from "react"
import { Input as InputPrimitive } from "@base-ui/react/input"

import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <InputPrimitive
      type={type}
      data-slot="input"
      className={cn(
        "h-10 w-full min-w-0 rounded-xl border border-slate-700/70 bg-slate-950/60 px-3 py-2 text-base text-slate-100 transition-all duration-300 outline-none placeholder:text-slate-500 file:inline-flex file:h-6 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-slate-100 focus-visible:border-cyan-400/50 focus-visible:ring-3 focus-visible:ring-cyan-400/25 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-red-400/60 aria-invalid:ring-3 aria-invalid:ring-red-400/20 md:text-sm",
        className
      )}
      {...props}
    />
  )
}

export { Input }
