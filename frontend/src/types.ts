export type Role = 'user' | 'assistant'
export type ConversationMode = 'general' | 'project_interview'
export type InterviewReviewStatus = 'queued' | 'running' | 'completed' | 'failed'

export interface User {
  id: string
  email: string
  user_name: string
  created_at: string
}

export interface AuthToken {
  access_token: string
  token_type: 'bearer'
}

export interface Conversation {
  id: string
  user_id: string
  title: string
  mode: ConversationMode
  learning_day: number | null
  created_at: string
}

export interface InterviewReview {
  id: string
  conversation_id: string
  session_id: string
  learning_day: number
  status: InterviewReviewStatus
  result: string | null
  error_message: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface Message {
  id: string
  conversation_id: string
  role: Role
  content: string
  created_at: string
}

export type RealtimeEventType =
  | 'message.started'
  | 'message.delta'
  | 'message.completed'
  | 'message.failed'
  | 'review.status'
  | 'review.completed'
  | 'review.failed'
  | 'error'

export interface RealtimeEvent {
  version: number
  type: RealtimeEventType
  conversation_id: string | null
  task_id: string | null
  data: Record<string, unknown>
  occurred_at: string
}
