/** Mirrors api/app/schemas/work_items.py */

export type WorkItemType = "epic" | "story" | "bug" | "task"

/** Raw work-item shape returned by the backend (no client-side id). */
export interface RawWorkItem {
  type: WorkItemType
  title: string
  description: string
  labels: string[]
  children: RawWorkItem[]
}

/** Client-side work item with a stable id for React keys and selection. */
export interface WorkItem extends Omit<RawWorkItem, "children"> {
  /** UUID assigned on the client when items are loaded; not sent by the API. */
  id: string
  children: WorkItem[]
}

export interface CreatedIssue {
  number: number
  title: string
  url: string
  item_type: WorkItemType
  children: CreatedIssue[]
}
