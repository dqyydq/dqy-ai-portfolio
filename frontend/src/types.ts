export type Role = 'user' | 'assistant'

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
  created_at: string
}

export interface Message {
  id: string
  conversation_id: string
  role: Role
  content: string
  created_at: string
}
