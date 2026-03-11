'use client'

import { useEffect, useState } from 'react'
import { X, Clock } from 'lucide-react'
import { Button } from '@/components/ui/button'

const STORAGE_KEY = 'forge-stream:recent-prompts'
const MAX_PROMPTS = 5

interface RecentPromptsProps {
  prompts: string[]
  onSelect: (prompt: string) => void
  onRemove: (prompt: string) => void
  onClear: () => void
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
  const [prompts, setPrompts] = useState<string[]>([])

  useEffect(() => {
    setPrompts(readPromptsFromStorage())
  }, [])

  function addPrompt(prompt: string): void {
    const trimmed = prompt.trim()
    if (!trimmed) return
    const existing = readPromptsFromStorage()
    const deduplicated = existing.filter((p) => p !== trimmed)
    const updated = [trimmed, ...deduplicated].slice(0, MAX_PROMPTS)
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
    setPrompts(updated)
  }

  function removePrompt(prompt: string): void {
    const existing = readPromptsFromStorage()
    const updated = existing.filter((p) => p !== prompt)
    if (updated.length === 0) {
      window.localStorage.removeItem(STORAGE_KEY)
    } else {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
    }
    setPrompts(updated)
  }

  function clearPrompts(): void {
    window.localStorage.removeItem(STORAGE_KEY)
    setPrompts([])
  }

  return { prompts, addPrompt, removePrompt, clearPrompts }
}

export function RecentPrompts({ prompts, onSelect, onRemove, onClear }: RecentPromptsProps) {
  if (prompts.length === 0) return null

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
          onClick={onClear}
          aria-label="Clear recent prompts"
        >
          Clear
        </Button>
      </div>
      <div className="flex flex-wrap gap-2">
        {prompts.map((prompt) => (
          <span
            key={prompt}
            className="inline-flex items-center gap-1 rounded-full border border-border bg-secondary text-xs text-secondary-foreground"
            title={prompt}
          >
            <button
              type="button"
              onClick={() => onSelect(prompt)}
              className="rounded-l-full py-1 pl-3 pr-1 transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              {truncate(prompt)}
            </button>
            <button
              type="button"
              onClick={() => onRemove(prompt)}
              aria-label={`Remove prompt: ${truncate(prompt)}`}
              className="rounded-r-full py-1 pl-1 pr-2.5 transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <X className="h-3 w-3 opacity-50" aria-hidden="true" />
            </button>
          </span>
        ))}
      </div>
    </div>
  )
}
