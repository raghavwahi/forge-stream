'use client'

interface ModelBadgeProps {
  model: string
}

function getModelProvider(model: string): 'openai' | 'anthropic' | 'gemini' | 'ollama' {
  if (model.startsWith('gpt-') || model.startsWith('o1') || model.startsWith('o3')) {
    return 'openai'
  }
  if (model.startsWith('claude-')) {
    return 'anthropic'
  }
  if (model.startsWith('gemini-')) {
    return 'gemini'
  }
  return 'ollama'
}

const providerDotColor: Record<string, string> = {
  openai: 'bg-green-500',
  anthropic: 'bg-orange-500',
  gemini: 'bg-blue-500',
  ollama: 'bg-gray-400',
}

const providerLabel: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  gemini: 'Gemini',
  ollama: 'Ollama',
}

export function ModelBadge({ model }: ModelBadgeProps) {
  const provider = getModelProvider(model)
  const dotColor = providerDotColor[provider]
  const label = providerLabel[provider]

  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-secondary px-2.5 py-0.5 text-xs font-medium text-secondary-foreground">
      <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} aria-hidden="true" />
      <span className="sr-only">{label}:</span>
      {model}
    </span>
  )
}
