'use client'

import { Button } from '@/components/ui/button'
import { WorkItemCard } from '@/components/WorkItemCard'
import type { WorkItem } from '@/types/api'

interface WorkItemNodeProps {
  item: WorkItem
  depth: number
  selectedItems: Set<string>
  onToggleSelect: (item: WorkItem) => void
  onEnhance: (original: WorkItem, enhanced: WorkItem) => void
}

function WorkItemNode({
  item,
  depth,
  selectedItems,
  onToggleSelect,
  onEnhance,
}: WorkItemNodeProps) {
  return (
    <div className="space-y-2">
      <WorkItemCard
        item={item}
        depth={depth}
        isSelected={selectedItems.has(item.title)}
        onToggleSelect={onToggleSelect}
        onEnhance={onEnhance}
      />
      {item.children.map((child) => (
        <WorkItemNode
          key={child.title}
          item={child}
          depth={depth + 1}
          selectedItems={selectedItems}
          onToggleSelect={onToggleSelect}
          onEnhance={onEnhance}
        />
      ))}
    </div>
  )
}

interface WorkItemTreeProps {
  items: WorkItem[]
  selectedItems: Set<string>
  onToggleSelect: (item: WorkItem) => void
  onEnhance: (original: WorkItem, enhanced: WorkItem) => void
  onSelectAll: () => void
  onDeselectAll: () => void
  totalCount: number
}

export function WorkItemTree({
  items,
  selectedItems,
  onToggleSelect,
  onEnhance,
  onSelectAll,
  onDeselectAll,
  totalCount,
}: WorkItemTreeProps) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {selectedItems.size} of {totalCount} items selected
        </p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onSelectAll}>
            Select all
          </Button>
          <Button variant="outline" size="sm" onClick={onDeselectAll}>
            Deselect all
          </Button>
        </div>
      </div>

      <div className="space-y-3">
        {items.map((item) => (
          <WorkItemNode
            key={item.title}
            item={item}
            depth={0}
            selectedItems={selectedItems}
            onToggleSelect={onToggleSelect}
            onEnhance={onEnhance}
          />
        ))}
      </div>
    </div>
  )
}
