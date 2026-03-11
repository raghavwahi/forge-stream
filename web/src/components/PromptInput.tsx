'use client'

import { useRef, useState, useCallback, useEffect, KeyboardEvent } from 'react'
import { Loader2, Sparkles, ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useEnhancePrompt } from '@/hooks/use-api'
import { toast } from 'sonner'

const MAX_CHARS = 5000

const MODELS = [
  { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
  { value: 'gpt-4o', label: 'GPT-4o' },
  { value: 'claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet' },
  { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash' },
] as const

type ModelValue = (typeof MODELS)[number]['value']

export interface PromptInputProps {
  onSubmit: (prompt: string, model: string) => void
  isLoading: boolean
  /** Optional prompt string to prefill — when this changes the textarea is updated */
  prefilledPrompt?: string
}

export function PromptInput({ onSubmit, isLoading, prefilledPrompt }: PromptInputProps) {
  const [prompt, setPrompt] = useState('')
  const [model, setModel] = useState<ModelValue>('gpt-4o-mini')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  // Track the last prompt value we applied from prefilledPrompt to avoid re-applying on re-renders
  const lastAppliedPrefilledRef = useRef<string | undefined>(undefined)
  const enhancePrompt = useEnhancePrompt()

  // When a recent prompt is selected, update the textarea
  useEffect(() => {
    if (
      prefilledPrompt !== undefined &&
      prefilledPrompt !== lastAppliedPrefilledRef.current
    ) {
      lastAppliedPrefilledRef.current = prefilledPrompt
      setPrompt(prefilledPrompt)
      textareaRef.current?.focus()
    }
  }, [prefilledPrompt])

  // Auto-resize textarea on content change
  const resizeTextarea = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 400)}px`
  }, [])

  useEffect(() => {
    resizeTextarea()
  }, [prompt, resizeTextarea])

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const value = e.target.value
    if (value.length <= MAX_CHARS) {
      setPrompt(value)
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      handleSubmit()
    }
  }

  function handleSubmit() {
    const trimmed = prompt.trim()
    if (!trimmed) {
      toast.error('Please enter a prompt before generating.')
      return
    }
    onSubmit(trimmed, model)
  }

  function handleEnhance() {
    const trimmed = prompt.trim()
    if (!trimmed) {
      toast.error('Please enter a prompt to enhance.')
      return
    }
    enhancePrompt.mutate(
      { prompt: trimmed, model },
      {
        onSuccess: (data) => {
          setPrompt(data.enhanced_prompt)
          toast.success('Prompt enhanced!')
        },
        onError: () => {
          toast.error('Failed to enhance prompt. Please try again.')
        },
      }
    )
  }

  const charCount = prompt.length
  const charPercent = (charCount / MAX_CHARS) * 100
  const isNearLimit = charPercent >= 80
  const isAtLimit = charCount >= MAX_CHARS

  const [isMac] = useState<boolean>(() => {
    if (typeof navigator === 'undefined') return false
    const platform =
      (navigator as Navigator & { userAgentData?: { platform?: string } }).userAgentData?.platform ??
      navigator.platform
    return /Mac/i.test(platform)
  })

  return (
    <div className="flex flex-col gap-2">
      {/* Textarea */}
      <div className="relative rounded-lg border border-input bg-background shadow-sm focus-within:ring-1 focus-within:ring-ring transition-shadow">
        <textarea
          ref={textareaRef}
          value={prompt}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Describe the feature you want to build..."
          disabled={isLoading || enhancePrompt.isPending}
          rows={4}
          aria-label="Feature description prompt"
          className="block w-full resize-none rounded-t-lg bg-transparent px-4 pt-4 pb-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
          style={{ minHeight: '120px', maxHeight: '400px' }}
        />

        {/* Bottom toolbar */}
        <div className="flex items-center justify-between rounded-b-lg px-3 pb-2 pt-1">
          {/* Left: Model selector + Enhance button */}
          <div className="flex items-center gap-2">
            {/* Model selector */}
            <div className="relative">
              <select
                value={model}
                onChange={(e) => setModel(e.target.value as ModelValue)}
                disabled={isLoading || enhancePrompt.isPending}
                aria-label="Select AI model"
                className="appearance-none rounded-md border border-input bg-background py-1 pl-2.5 pr-7 text-xs text-foreground shadow-sm transition-colors hover:bg-accent focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              >
                {MODELS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
              <ChevronDown
                className="pointer-events-none absolute right-2 top-1/2 h-3 w-3 -translate-y-1/2 text-muted-foreground"
                aria-hidden="true"
              />
            </div>

            {/* Enhance button */}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleEnhance}
              disabled={isLoading || enhancePrompt.isPending || !prompt.trim()}
              className="h-7 gap-1.5 px-2.5 text-xs"
              aria-label="Enhance prompt with AI"
            >
              {enhancePrompt.isPending ? (
                <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
              ) : (
                <Sparkles className="h-3 w-3" aria-hidden="true" />
              )}
              {enhancePrompt.isPending ? 'Enhancing…' : 'Enhance'}
            </Button>
          </div>

          {/* Right: char counter */}
          <span
            className={`text-xs tabular-nums transition-colors ${
              isAtLimit
                ? 'text-destructive font-medium'
                : isNearLimit
                  ? 'text-orange-500'
                  : 'text-muted-foreground'
            }`}
            aria-live="polite"
            aria-label={`${charCount} of ${MAX_CHARS} characters used`}
          >
            {charCount.toLocaleString()}&nbsp;/&nbsp;{MAX_CHARS.toLocaleString()}
          </span>
        </div>
      </div>

      {/* Submit button */}
      <Button
        type="button"
        onClick={handleSubmit}
        disabled={isLoading || enhancePrompt.isPending || !prompt.trim()}
        className="w-full gap-2"
        size="lg"
        aria-label={isLoading ? 'Generating work items…' : 'Generate work items'}
      >
        {isLoading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
        {isLoading ? 'Generating…' : 'Generate'}
        {!isLoading && (
          <kbd className="ml-auto hidden rounded border border-primary-foreground/20 bg-primary-foreground/10 px-1.5 text-[10px] font-mono text-primary-foreground/70 sm:inline-block">
            {isMac ? '⌘' : 'Ctrl'} Enter
          </kbd>
        )}
      </Button>
    </div>
  )
}

export type { ModelValue }
