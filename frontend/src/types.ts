export type Role = 'user' | 'assistant'

export interface User {
  id: string
  email: string
  user_name: string
  is_email_verified: boolean
  has_deepseek_api_key: boolean
  deepseek_api_key_hint: string | null
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

