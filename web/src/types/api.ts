export interface WorkItem {
  type: 'epic' | 'story' | 'bug' | 'task'
  title: string
  description: string
  labels: string[]
  children: WorkItem[]
}

export interface WorkItemHierarchy {
  items: WorkItem[]
}

export interface GenerateResponse {
  items: WorkItem[]
}
