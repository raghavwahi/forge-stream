'use client'

import { useRef, useState, useCallback } from 'react'
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
import { apiFetch } from '@/lib/api'
import type { RawWorkItem, WorkItem, CreatedIssue } from '@/types/api'

type Step = 'review' | 'github' | 'success'

/** Recursively assign a stable client-side UUID to every item. */
function assignIds(items: RawWorkItem[]): WorkItem[] {
  return items.map((item) => ({
    ...item,
    id: crypto.randomUUID(),
    children: assignIds(item.children),
  }))
}

function readSessionItems(): WorkItem[] {
  if (typeof window === 'undefined') return []
  const raw = sessionStorage.getItem('forgestream_items')
  if (!raw) return []
  try {
    return assignIds(JSON.parse(raw) as RawWorkItem[])
  } catch {
    sessionStorage.removeItem('forgestream_items')
    return []
  }
}

function countItems(items: WorkItem[]): number {
  return items.reduce((acc, item) => acc + 1 + countItems(item.children), 0)
}

function collectIds(items: WorkItem[]): Set<string> {
  const ids = new Set<string>()
  const visit = (item: WorkItem) => {
    ids.add(item.id)
    item.children.forEach(visit)
  }
  items.forEach(visit)
  return ids
}

/** Return only the items (and children) whose ids are in the set. */
function filterByIds(items: WorkItem[], ids: Set<string>): WorkItem[] {
  return items
    .filter((item) => ids.has(item.id))
    .map((item) => ({ ...item, children: filterByIds(item.children, ids) }))
}

export default function ReviewPage() {
  const router = useRouter()

  // Initialise items once; share the same array for the selectedIds initializer
  // so both states reference the same set of UUIDs.
  const initItemsRef = useRef<WorkItem[] | null>(null)

  const [step, setStep] = useState<Step>('review')
  const [items, setItems] = useState<WorkItem[]>(() => {
    initItemsRef.current = readSessionItems()
    return initItemsRef.current
  })
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() =>
    collectIds(initItemsRef.current ?? []),
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
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(item.id)) {
        next.delete(item.id)
      } else {
        next.add(item.id)
      }
      return next
    })
  }, [])

  const handleEnhance = useCallback(
    (original: WorkItem, enhanced: WorkItem) => {
      // The enhanced item preserves the original id, so selection is unaffected.
      const replace = (list: WorkItem[]): WorkItem[] =>
        list.map((i) =>
          i.id === original.id
            ? { ...enhanced, children: replace(i.children) }
            : { ...i, children: replace(i.children) },
        )
      setItems((prev) => replace(prev))
    },
    [],
  )

  const handleSelectAll = useCallback(() => {
    setSelectedIds(collectIds(items))
  }, [items])

  const handleDeselectAll = useCallback(() => {
    setSelectedIds(new Set())
  }, [])

  const handleSubmitIssues = async () => {
    if (!githubConfig.token || !githubConfig.owner || !githubConfig.repo) {
      toast.error('Please fill in all GitHub fields.')
      return
    }
    setIsSubmitting(true)
    try {
      const selectedItems = filterByIds(items, selectedIds)
      const data = await apiFetch<{ created: CreatedIssue[] }>(
        '/work-items/create-issues',
        {
          method: 'POST',
          body: JSON.stringify({
            github: {
              token: githubConfig.token,
              owner: githubConfig.owner,
              repo: githubConfig.repo,
            },
            items: selectedItems,
          }),
        },
      )
      setCreatedIssues(data.created ?? [])
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
              aria-label="Back to review"
              onClick={() => setStep('review')}
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <div>
              <h1 className="text-2xl font-bold">GitHub Configuration</h1>
              <p className="text-sm text-muted-foreground">
                Connect to your repository to create {selectedIds.size} issue
                {selectedIds.size !== 1 ? 's' : ''}
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
            aria-label="Back to dashboard"
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
              selectedItems={selectedIds}
              onToggleSelect={handleToggleSelect}
              onEnhance={handleEnhance}
              onSelectAll={handleSelectAll}
              onDeselectAll={handleDeselectAll}
              totalCount={totalCount}
            />

            <div className="mt-6 flex justify-end">
              <Button
                onClick={() => setStep('github')}
                disabled={selectedIds.size === 0}
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

