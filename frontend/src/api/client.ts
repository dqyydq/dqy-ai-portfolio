import type { AuthToken, Conversation, Message, User } from '../types'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  })

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new ApiError(response.status, body.detail ?? 'Request failed')
  }

  return response.json() as Promise<T>
}

export const api = {
  register: (payload: { email: string; user_name: string; password: string }) =>
    request<User>('/auth/register', { method: 'POST', body: JSON.stringify(payload) }),
  login: (payload: { email: string; password: string }) =>
    request<AuthToken>('/auth/login', { method: 'POST', body: JSON.stringify(payload) }),
  getMe: (token: string) => request<User>('/auth/me', {}, token),
  listConversations: (token: string) => request<Conversation[]>('/conversations/', {}, token),
  createConversation: (token: string, title: string) =>
    request<Conversation>('/conversations/', { method: 'POST', body: JSON.stringify({ title }) }, token),
  listMessages: (token: string, conversationId: string) =>
    request<Message[]>(`/conversations/${conversationId}/messages`, {}, token),
  sendMessage: (token: string, conversationId: string, content: string) =>
    request<Message>(
      `/conversations/${conversationId}/messages`,
      { method: 'POST', body: JSON.stringify({ content }) },
      token,
    ),
}

export { ApiError }
