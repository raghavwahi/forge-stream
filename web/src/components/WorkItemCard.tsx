'use client'

import { useState } from 'react'
import { ChevronDown, ChevronRight, Sparkles, Loader2 } from 'lucide-react'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { WorkItem } from '@/types/api'

const TYPE_CONFIG = {
  epic: {
    color: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
    label: 'Epic',
  },
  story: {
    color: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
    label: 'Story',
  },
  bug: {
    color: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
    label: 'Bug',
  },
  task: {
    color: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    label: 'Task',
  },
} as const

interface WorkItemCardProps {
  item: WorkItem
  depth: number
  isSelected: boolean
  onToggleSelect: (item: WorkItem) => void
  onEnhance: (original: WorkItem, enhanced: WorkItem) => void
}

export function WorkItemCard({
  item,
  depth,
  isSelected,
  onToggleSelect,
  onEnhance,
}: WorkItemCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [isEnhancing, setIsEnhancing] = useState(false)
  const [currentItem, setCurrentItem] = useState<WorkItem>(item)

  const config = TYPE_CONFIG[currentItem.type]
  const indentPx = depth * 24

  const handleEnhance = async () => {
    setIsEnhancing(true)
    try {
      const response = await fetch('/api/v1/work-items/enhance-item', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item: currentItem }),
      })
      if (response.ok) {
        const enhanced: WorkItem = await response.json()
        setCurrentItem(enhanced)
        onEnhance(item, enhanced)
      }
    } catch {
      // silently fail — toast shown at page level
    } finally {
      setIsEnhancing(false)
    }
  }

  return (
    <div
      className="border rounded-lg p-3 bg-card"
      style={{ marginLeft: `${indentPx}px` }}
    >
      <div className="flex items-start gap-3">
        <Checkbox
          checked={isSelected}
          onCheckedChange={() => onToggleSelect(currentItem)}
          className="mt-0.5 shrink-0"
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={`text-xs font-medium px-2 py-0.5 rounded-full ${config.color}`}
            >
              {config.label}
            </span>
            <span className="font-medium text-sm">{currentItem.title}</span>
          </div>

          <p
            className={`text-xs text-muted-foreground mt-1 ${
              isExpanded ? '' : 'line-clamp-2'
            }`}
          >
            {currentItem.description}
          </p>

          {currentItem.description.length > 100 && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="text-xs text-primary mt-1 flex items-center gap-1"
            >
              {isExpanded ? (
                <ChevronDown className="w-3 h-3" />
              ) : (
                <ChevronRight className="w-3 h-3" />
              )}
              {isExpanded ? 'Show less' : 'Show more'}
            </button>
          )}

          {currentItem.labels.length > 0 && (
            <div className="flex gap-1 flex-wrap mt-2">
              {currentItem.labels.map((label) => (
                <Badge key={label} variant="outline" className="text-xs py-0">
                  {label}
                </Badge>
              ))}
            </div>
          )}

          {currentItem.children.length > 0 && (
            <span className="text-xs text-muted-foreground mt-1 inline-block">
              {currentItem.children.length} child item
              {currentItem.children.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>

        <Button
          variant="ghost"
          size="sm"
          onClick={handleEnhance}
          disabled={isEnhancing}
          className="shrink-0 h-7 px-2 text-xs"
        >
          {isEnhancing ? (
            <Loader2 className="w-3 h-3 animate-spin" />
          ) : (
            <Sparkles className="w-3 h-3" />
          )}
          <span className="ml-1">{isEnhancing ? 'Enhancing…' : 'Enhance'}</span>
        </Button>
      </div>
    </div>
  )
}
