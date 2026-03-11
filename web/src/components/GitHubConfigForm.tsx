'use client'

import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface GitHubConfigFormProps {
  value: { token: string; owner: string; repo: string }
  onChange: (config: { token: string; owner: string; repo: string }) => void
  isLoading?: boolean
}

export function GitHubConfigForm({
  value,
  onChange,
  isLoading,
}: GitHubConfigFormProps) {
  const update = (key: keyof typeof value, val: string) =>
    onChange({ ...value, [key]: val })

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="github-token">
          GitHub Personal Access Token{' '}
          <a
            href="https://github.com/settings/tokens/new?scopes=repo"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-primary underline"
          >
            Generate token
          </a>
        </Label>
        <Input
          id="github-token"
          type="password"
          placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
          value={value.token}
          onChange={(e) => update('token', e.target.value)}
          disabled={isLoading}
          required
        />
        <p className="text-xs text-muted-foreground">
          Requires <code>repo</code> scope to create issues.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="github-owner">Repository Owner</Label>
          <Input
            id="github-owner"
            placeholder="your-username"
            value={value.owner}
            onChange={(e) => update('owner', e.target.value)}
            disabled={isLoading}
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="github-repo">Repository Name</Label>
          <Input
            id="github-repo"
            placeholder="my-project"
            value={value.repo}
            onChange={(e) => update('repo', e.target.value)}
            disabled={isLoading}
            required
          />
        </div>
      </div>
    </div>
  )
}
