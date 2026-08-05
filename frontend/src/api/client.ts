import type { AuthToken, Conversation, ConversationMode, InterviewReview, Message, RealtimeEvent, User } from '../types'

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

async function streamRequest(
  path: string,
  payload: object,
  token: string,
  onEvent: (event: RealtimeEvent) => void,
): Promise<void> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new ApiError(response.status, body.detail ?? 'Request failed')
  }
  if (response.body === null) throw new ApiError(502, 'Stream response body is unavailable')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const dispatch = (block: string) => {
    const data = block.split('\n').find((line) => line.startsWith('data: '))
    if (data) onEvent(JSON.parse(data.slice(6)) as RealtimeEvent)
  }

  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value, { stream: !done }).replaceAll('\r\n', '\n')
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() ?? ''
    blocks.forEach(dispatch)
    if (done) break
  }
  if (buffer.trim()) dispatch(buffer)
}

export const api = {
  register: (payload: { email: string; user_name: string; password: string }) =>
    request<User>('/auth/register', { method: 'POST', body: JSON.stringify(payload) }),
  login: (payload: { email: string; password: string }) =>
    request<AuthToken>('/auth/login', { method: 'POST', body: JSON.stringify(payload) }),
  getMe: (token: string) => request<User>('/auth/me', {}, token),
  listConversations: (token: string) => request<Conversation[]>('/conversations/', {}, token),
  createConversation: (token: string, title: string, mode: ConversationMode = 'general', learningDay?: number) =>
    request<Conversation>('/conversations/', { method: 'POST', body: JSON.stringify({ title, mode, learning_day: learningDay }) }, token),
  updateLearningDay: (token: string, conversationId: string, learningDay: number) =>
    request<Conversation>(`/conversations/${conversationId}/learning-context`, { method: 'PATCH', body: JSON.stringify({ learning_day: learningDay }) }, token),
  listMessages: (token: string, conversationId: string) =>
    request<Message[]>(`/conversations/${conversationId}/messages`, {}, token),
  sendMessage: (token: string, conversationId: string, content: string) =>
    request<Message>(
      `/conversations/${conversationId}/messages`,
      { method: 'POST', body: JSON.stringify({ content }) },
      token,
    ),
  streamMessage: (
    token: string,
    conversationId: string,
    content: string,
    onEvent: (event: RealtimeEvent) => void,
  ) => streamRequest(
    `/conversations/${conversationId}/messages/stream`,
    { content },
    token,
    onEvent,
  ),
  createInterviewReview: (token: string, conversationId: string) =>
    request<InterviewReview>(`/interview-reviews/conversations/${conversationId}`, { method: 'POST', body: JSON.stringify({}) }, token),
  getInterviewReview: (token: string, taskId: string) =>
    request<InterviewReview>(`/interview-reviews/${taskId}`, {}, token),
}

export { ApiError }
