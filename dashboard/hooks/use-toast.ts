import * as React from "react"

type ToastProps = {
  title?: string
  description?: string
  variant?: "default" | "destructive"
}

function toast({ title, description, variant = "default" }: ToastProps) {
  const message = title ? `${title}${description ? `: ${description}` : ""}` : description || ""

  if (typeof window !== "undefined") {
    if (variant === "destructive") {
      console.error(message)
      alert(`Error: ${message}`)
    } else {
      console.log(message)
      // For now, just log to console. In a real app, you'd show a toast notification
    }
  }

  return {
    id: Math.random().toString(),
    dismiss: () => {},
    update: () => {},
  }
}

function useToast() {
  return {
    toast,
    toasts: [],
    dismiss: () => {},
  }
}

export { useToast, toast }