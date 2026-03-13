'use client'

import { useEffect, useState } from 'react'
import { X, Clock } from 'lucide-react'
import { Button } from '@/components/ui/button'

const STORAGE_KEY = 'forge-stream:recent-prompts'
const MAX_PROMPTS = 5

interface RecentPromptsProps {
  onSelect: (prompt: string) => void
}

function readPromptsFromStorage(): string[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter((item): item is string => typeof item === 'string')
  } catch {
    return []
  }
}

export function useRecentPrompts() {
  function addPrompt(prompt: string): void {
    const trimmed = prompt.trim()
    if (!trimmed) return
    const existing = readPromptsFromStorage()
    const deduplicated = existing.filter((p) => p !== trimmed)
    const updated = [trimmed, ...deduplicated].slice(0, MAX_PROMPTS)
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
  }

  function clearPrompts(): void {
    window.localStorage.removeItem(STORAGE_KEY)
  }

  return { addPrompt, clearPrompts }
}

export function RecentPrompts({ onSelect }: RecentPromptsProps) {
  const [prompts, setPrompts] = useState<string[]>([])
  const { clearPrompts } = useRecentPrompts()

  useEffect(() => {
    setPrompts(readPromptsFromStorage())
  }, [])

  if (prompts.length === 0) return null

  function handleClear() {
    clearPrompts()
    setPrompts([])
  }

  function truncate(text: string, maxLength = 60): string {
    if (text.length <= maxLength) return text
    return text.slice(0, maxLength).trimEnd() + '…'
  }

  return (
    <div className="mt-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <Clock className="h-3 w-3" aria-hidden="true" />
          Recent prompts
        </span>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
          onClick={handleClear}
          aria-label="Clear recent prompts"
        >
          Clear
        </Button>
      </div>
      <div className="flex flex-wrap gap-2">
        {prompts.map((prompt, index) => (
          <button
            key={index}
            type="button"
            onClick={() => onSelect(prompt)}
            className="inline-flex items-center gap-1 rounded-full border border-border bg-secondary px-3 py-1 text-xs text-secondary-foreground transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            title={prompt}
          >
            {truncate(prompt)}
            <X className="h-3 w-3 opacity-50" aria-hidden="true" />
          </button>
        ))}
      </div>
    </div>
  )
}
