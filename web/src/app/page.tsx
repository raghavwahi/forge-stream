'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useGenerate } from '@/hooks/use-api'
import { PromptInput } from '@/components/PromptInput'
import { RecentPrompts, useRecentPrompts } from '@/components/RecentPrompts'
import { toast } from 'sonner'
import { Zap, GitBranch, LayoutList } from 'lucide-react'

const FEATURES = [
  {
    icon: Zap,
    title: 'AI-Powered Decomposition',
    description:
      'Describe your feature in plain English. Our AI breaks it down into epics, stories, and tasks automatically.',
  },
  {
    icon: GitBranch,
    title: 'GitHub-Ready Output',
    description:
      'Generated work items are structured to be pushed directly to your GitHub repository as issues.',
  },
  {
    icon: LayoutList,
    title: 'Hierarchical Planning',
    description:
      'Work items are organized in a clean hierarchy — epics contain stories, stories contain tasks.',
  },
]

export default function DashboardPage() {
  const router = useRouter()
  const generate = useGenerate()
  const { prompts: recentPrompts, addPrompt, removePrompt, clearPrompts } = useRecentPrompts()
  const [selectedPrompt, setSelectedPrompt] = useState<string | undefined>(undefined)

  function handleSubmit(prompt: string, model: string) {
    // Persist to recent prompts before generating
    addPrompt(prompt)

    generate.mutate(
      { prompt, model },
      {
        onSuccess: (data) => {
          sessionStorage.setItem('forgestream_items', JSON.stringify(data.items))
          router.push('/review')
        },
        onError: (err) => {
          const message =
            err instanceof Error ? err.message : 'Generation failed. Please try again.'
          toast.error(message)
        },
      }
    )
  }

  function handleSelectRecent(prompt: string) {
    setSelectedPrompt(prompt)
  }

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Hero / main content */}
      <main className="flex flex-1 flex-col items-center justify-center px-4 py-16">
        <div className="w-full max-w-2xl">
          {/* Header */}
          <div className="mb-10 text-center">
            <h1 className="mb-3 text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
              ForgeStream
            </h1>
            <p className="text-base text-muted-foreground sm:text-lg">
              Transform requirements into GitHub issues
            </p>
          </div>

          {/* Prompt input card */}
          <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
            <PromptInput
              onSubmit={handleSubmit}
              isLoading={generate.isPending}
              prefilledPrompt={selectedPrompt}
            />

            {/* Recent prompts */}
            <RecentPrompts
              prompts={recentPrompts}
              onSelect={handleSelectRecent}
              onRemove={removePrompt}
              onClear={clearPrompts}
            />
          </div>

          {/* Loading state hint */}
          {generate.isPending && (
            <p className="mt-4 text-center text-sm text-muted-foreground" aria-live="polite">
              Analysing your requirements and generating work items&hellip;
            </p>
          )}
        </div>
      </main>

      {/* Feature cards */}
      <section aria-label="Features" className="border-t border-border bg-muted/30 px-4 py-12">
        <div className="mx-auto max-w-2xl">
          <h2 className="mb-6 text-center text-sm font-semibold uppercase tracking-widest text-muted-foreground">
            How it works
          </h2>
          <div className="grid gap-4 sm:grid-cols-3">
            {FEATURES.map(({ icon: Icon, title, description }) => (
              <div
                key={title}
                className="rounded-lg border border-border bg-card p-4 shadow-sm"
              >
                <div className="mb-3 flex h-8 w-8 items-center justify-center rounded-md bg-primary/10">
                  <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
                </div>
                <h3 className="mb-1 text-sm font-semibold text-foreground">{title}</h3>
                <p className="text-xs leading-relaxed text-muted-foreground">{description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
