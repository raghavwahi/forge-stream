'use client'

import { useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { toast } from 'sonner'
import { ArrowLeft, ArrowRight, CheckCircle2, ExternalLink } from 'lucide-react'
import { WorkItemTree } from '@/components/WorkItemTree'
import { GitHubConfigForm } from '@/components/GitHubConfigForm'
import type { WorkItem } from '@/types/api'

type Step = 'review' | 'github' | 'success'

interface CreatedIssue {
  title: string
  url: string
  number: number
}

function readSessionItems(): WorkItem[] {
  if (typeof window === 'undefined') return []
  const raw = sessionStorage.getItem('forgestream_items')
  if (!raw) return []
  try {
    return JSON.parse(raw) as WorkItem[]
  } catch {
    sessionStorage.removeItem('forgestream_items')
    return []
  }
}

function countItems(items: WorkItem[]): number {
  return items.reduce((acc, item) => acc + 1 + countItems(item.children), 0)
}

function collectTitles(items: WorkItem[]): Set<string> {
  const titles = new Set<string>()
  const visit = (item: WorkItem) => {
    titles.add(item.title)
    item.children.forEach(visit)
  }
  items.forEach(visit)
  return titles
}

export default function ReviewPage() {
  const router = useRouter()
  const [step, setStep] = useState<Step>('review')
  const [items, setItems] = useState<WorkItem[]>(() => readSessionItems())
  const [selectedTitles, setSelectedTitles] = useState<Set<string>>(
    () => collectTitles(readSessionItems()),
  )
  const [githubConfig, setGithubConfig] = useState({
    token: '',
    owner: '',
    repo: '',
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [createdIssues, setCreatedIssues] = useState<CreatedIssue[]>([])

  const totalCount = countItems(items)

  const handleToggleSelect = useCallback((item: WorkItem) => {
    setSelectedTitles((prev) => {
      const next = new Set(prev)
      if (next.has(item.title)) {
        next.delete(item.title)
      } else {
        next.add(item.title)
      }
      return next
    })
  }, [])

  const handleEnhance = useCallback(
    (original: WorkItem, enhanced: WorkItem) => {
      const replace = (list: WorkItem[]): WorkItem[] =>
        list.map((i) =>
          i.title === original.title
            ? { ...enhanced, children: replace(i.children) }
            : { ...i, children: replace(i.children) },
        )
      setItems((prev) => replace(prev))
      setSelectedTitles((prev) => {
        const next = new Set(prev)
        if (next.has(original.title)) {
          next.delete(original.title)
          next.add(enhanced.title)
        }
        return next
      })
    },
    [],
  )

  const handleSelectAll = useCallback(() => {
    setSelectedTitles(collectTitles(items))
  }, [items])

  const handleDeselectAll = useCallback(() => {
    setSelectedTitles(new Set())
  }, [])

  const handleSubmitIssues = async () => {
    if (!githubConfig.token || !githubConfig.owner || !githubConfig.repo) {
      toast.error('Please fill in all GitHub fields.')
      return
    }
    setIsSubmitting(true)
    try {
      const response = await fetch('/api/v1/github-app/create-issues', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token: githubConfig.token,
          owner: githubConfig.owner,
          repo: githubConfig.repo,
          titles: Array.from(selectedTitles),
        }),
      })
      if (!response.ok) throw new Error('Failed to create issues')
      const data = await response.json()
      setCreatedIssues(data.issues ?? [])
      setStep('success')
    } catch {
      toast.error(
        'Failed to create GitHub issues. Check your token and try again.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  // ─── Step: Success ──────────────────────────────────────────────────────────

  if (step === 'success') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-4">
        <Card className="w-full max-w-lg">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-green-500" />
              Issues Created!
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              {createdIssues.length} issue
              {createdIssues.length !== 1 ? 's' : ''} created in{' '}
              <strong>
                {githubConfig.owner}/{githubConfig.repo}
              </strong>
              .
            </p>
            <div className="max-h-64 space-y-2 overflow-y-auto">
              {createdIssues.map((issue) => (
                <a
                  key={issue.number}
                  href={issue.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 text-sm text-primary underline"
                >
                  <ExternalLink className="h-3 w-3 shrink-0" />
                  #{issue.number} {issue.title}
                </a>
              ))}
            </div>
          </CardContent>
          <CardFooter>
            <Button variant="outline" onClick={() => router.push('/')}>
              Back to Dashboard
            </Button>
          </CardFooter>
        </Card>
      </div>
    )
  }

  // ─── Step: GitHub Config ────────────────────────────────────────────────────

  if (step === 'github') {
    return (
      <div className="flex min-h-screen justify-center bg-background p-4">
        <div className="w-full max-w-lg py-10">
          <div className="mb-6 flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setStep('review')}
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <div>
              <h1 className="text-2xl font-bold">GitHub Configuration</h1>
              <p className="text-sm text-muted-foreground">
                Connect to your repository to create {selectedTitles.size} issue
                {selectedTitles.size !== 1 ? 's' : ''}
              </p>
            </div>
          </div>

          <Card>
            <CardContent className="pt-6">
              <GitHubConfigForm
                value={githubConfig}
                onChange={setGithubConfig}
                isLoading={isSubmitting}
              />
            </CardContent>
            <CardFooter className="flex justify-end">
              <Button onClick={handleSubmitIssues} disabled={isSubmitting}>
                {isSubmitting ? 'Creating Issues…' : 'Create Issues'}
                {!isSubmitting && <ArrowRight className="ml-2 h-4 w-4" />}
              </Button>
            </CardFooter>
          </Card>
        </div>
      </div>
    )
  }

  // ─── Step: Review ───────────────────────────────────────────────────────────

  return (
    <div className="flex min-h-screen justify-center bg-background p-4">
      <div className="w-full max-w-3xl py-10">
        <div className="mb-6 flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push('/')}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">Review Work Items</h1>
            <p className="text-sm text-muted-foreground">
              Enhance or deselect items before creating GitHub issues
            </p>
          </div>
        </div>

        {items.length === 0 ? (
          <Card>
            <CardContent className="p-8 text-center text-muted-foreground">
              No items to review. Go back and generate a plan first.
            </CardContent>
          </Card>
        ) : (
          <>
            <WorkItemTree
              items={items}
              selectedItems={selectedTitles}
              onToggleSelect={handleToggleSelect}
              onEnhance={handleEnhance}
              onSelectAll={handleSelectAll}
              onDeselectAll={handleDeselectAll}
              totalCount={totalCount}
            />

            <div className="mt-6 flex justify-end">
              <Button
                onClick={() => setStep('github')}
                disabled={selectedTitles.size === 0}
              >
                Continue to GitHub
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
