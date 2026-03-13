'use client'

import { useState, useEffect, useRef } from 'react'
import { Search, ChevronDown, Loader2, GitBranch } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

interface GitHubRepo {
  id: number
  name: string
  full_name: string
  private: boolean
  description: string | null
  html_url: string
  default_branch: string
  installation_id: number
}

interface RepositorySelectorProps {
  installationId: number
  value: GitHubRepo | null
  onChange: (repo: GitHubRepo | null) => void
  disabled?: boolean
}

export function RepositorySelector({
  installationId,
  value,
  onChange,
  disabled,
}: RepositorySelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [repos, setRepos] = useState<GitHubRepo[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Fetch repos when dropdown opens or query changes
  useEffect(() => {
    if (!isOpen) return

    const controller = new AbortController()
    setIsLoading(true)
    setError(null)

    const url = query
      ? `/api/v1/repositories/search?installation_id=${installationId}&q=${encodeURIComponent(query)}`
      : `/api/v1/repositories?installation_id=${installationId}`

    fetch(url, { signal: controller.signal })
      .then((r) => {
        if (!r.ok) throw new Error('Failed to load repositories')
        return r.json()
      })
      .then((data) => setRepos(data.repos ?? []))
      .catch((err) => {
        if (err.name !== 'AbortError') setError(err.message)
      })
      .finally(() => setIsLoading(false))

    return () => controller.abort()
  }, [isOpen, query, installationId])

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleSelect = (repo: GitHubRepo) => {
    onChange(repo)
    setIsOpen(false)
    setQuery('')
  }

  return (
    <div ref={containerRef} className="relative w-full">
      {/* Trigger button */}
      <Button
        type="button"
        variant="outline"
        role="combobox"
        aria-expanded={isOpen}
        className="w-full justify-between font-normal"
        disabled={disabled}
        onClick={() => setIsOpen((prev) => !prev)}
      >
        {value ? (
          <span className="flex items-center gap-2 truncate">
            <GitBranch className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="truncate">{value.full_name}</span>
            {value.private && (
              <Badge variant="outline" className="ml-auto shrink-0 text-xs">
                Private
              </Badge>
            )}
          </span>
        ) : (
          <span className="text-muted-foreground">Select a repository…</span>
        )}
        <ChevronDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
      </Button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-md">
          {/* Search input */}
          <div className="flex items-center border-b px-3">
            <Search className="mr-2 h-4 w-4 shrink-0 text-muted-foreground" />
            <Input
              className="h-9 border-0 bg-transparent p-0 shadow-none focus-visible:ring-0"
              placeholder="Search repositories…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              autoFocus
            />
          </div>

          {/* Results */}
          <div className="max-h-64 overflow-y-auto py-1">
            {isLoading && (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              </div>
            )}

            {!isLoading && error && (
              <p className="px-3 py-2 text-sm text-destructive">{error}</p>
            )}

            {!isLoading && !error && repos.length === 0 && (
              <p className="px-3 py-2 text-sm text-muted-foreground">
                No repositories found.
              </p>
            )}

            {!isLoading &&
              repos.map((repo) => (
                <button
                  key={repo.id}
                  type="button"
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-accent focus:bg-accent focus:outline-none"
                  onClick={() => handleSelect(repo)}
                >
                  <GitBranch className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="flex-1 truncate">{repo.full_name}</span>
                  {repo.private && (
                    <Badge variant="outline" className="shrink-0 text-xs">
                      Private
                    </Badge>
                  )}
                </button>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}
