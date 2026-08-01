import { type FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  ArrowUp,
  Bot,
  ChevronDown,
  Command,
  LoaderCircle,
  LogOut,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Sparkles,
} from 'lucide-react'
import { ApiError, api } from './api/client'
import type { Conversation, Message, User } from './types'
import './App.css'

const TOKEN_KEY = 'agentlab.access-token'

function initials(name: string) {
  return name.slice(0, 2).toUpperCase()
}

function conversationTitle(content: string) {
  const compact = content.trim().replace(/\s+/g, ' ')
  return compact.length > 28 ? `${compact.slice(0, 28)}…` : compact || 'New conversation'
}

function AuthScreen({ onAuthenticated }: { onAuthenticated: (token: string, user: User) => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [userName, setUserName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    try {
      if (mode === 'register') {
        await api.register({ email, user_name: userName, password })
      }
      const token = await api.login({ email, password })
      const user = await api.getMe(token.access_token)
      onAuthenticated(token.access_token, user)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to authenticate')
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-panel" aria-labelledby="auth-title">
        <div className="brand-mark" aria-hidden="true"><Sparkles size={18} /></div>
        <p className="eyebrow">AGENT WORKSPACE</p>
        <h1 id="auth-title">Build a thread<br />worth returning to.</h1>
        <p className="auth-intro">A focused space for your conversations, model output, and the next useful question.</p>
        <form onSubmit={submit} className="auth-form">
          {mode === 'register' && (
            <label>
              <span>Display name</span>
              <input value={userName} onChange={(event) => setUserName(event.target.value)} required minLength={2} maxLength={50} placeholder="Your name" />
            </label>
          )}
          <label>
            <span>Email</span>
            <input value={email} onChange={(event) => setEmail(event.target.value)} required type="email" placeholder="you@example.com" />
          </label>
          <label>
            <span>Password</span>
            <input value={password} onChange={(event) => setPassword(event.target.value)} required type="password" minLength={8} placeholder="At least 8 characters" />
          </label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="auth-submit" type="submit">
            {mode === 'login' ? 'Enter workspace' : 'Create workspace'} <ArrowUp size={16} />
          </button>
        </form>
        <button className="mode-toggle" type="button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>
          {mode === 'login' ? 'New here? Create an account' : 'Already have an account? Sign in'}
        </button>
      </section>
      <aside className="auth-aside" aria-hidden="true">
        <span className="auth-aside-label">01 / CONTEXT</span>
        <p>Quiet interface.<br />Clear thinking.</p>
        <div className="auth-grid" />
      </aside>
    </main>
  )
}

function App() {
  const queryClient = useQueryClient()
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) ?? '')
  const [currentUser, setCurrentUser] = useState<User | null>(null)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(
    () => !window.matchMedia('(max-width: 40rem)').matches,
  )
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const conversationsQuery = useQuery({
    queryKey: ['conversations', token],
    queryFn: () => api.listConversations(token),
    enabled: Boolean(token),
  })

  const messagesQuery = useQuery({
    queryKey: ['messages', token, activeId],
    queryFn: () => api.listMessages(token, activeId!),
    enabled: Boolean(token && activeId),
  })

  useEffect(() => {
    if (!token || currentUser) return
    api.getMe(token).then(setCurrentUser).catch(() => {
      localStorage.removeItem(TOKEN_KEY)
      setToken('')
    })
  }, [token, currentUser])

  useEffect(() => {
    if (!activeId && conversationsQuery.data?.length) setActiveId(conversationsQuery.data[0].id)
  }, [activeId, conversationsQuery.data])

  const activeConversation = useMemo(
    () => conversationsQuery.data?.find((conversation) => conversation.id === activeId) ?? null,
    [activeId, conversationsQuery.data],
  )

  const sendMutation = useMutation({
    mutationFn: async ({ conversationId, content }: { conversationId: string | null; content: string }) => {
      let targetId = conversationId
      if (!targetId) {
        const conversation = await api.createConversation(token, conversationTitle(content))
        targetId = conversation.id
        setActiveId(targetId)
        await queryClient.invalidateQueries({ queryKey: ['conversations', token] })
      }
      const message = await api.sendMessage(token, targetId, content)
      return { message, conversationId: targetId }
    },
    onSuccess: async ({ conversationId }) => {
      setActiveId(conversationId)
      await queryClient.invalidateQueries({ queryKey: ['conversations', token] })
      await queryClient.invalidateQueries({ queryKey: ['messages', token, conversationId] })
      setPendingUserMessage(null)
      textareaRef.current?.focus()
    },
    onError: async (_error, { conversationId }) => {
      if (conversationId) {
        await queryClient.invalidateQueries({ queryKey: ['messages', token, conversationId] })
      }
      setPendingUserMessage(null)
    },
  })

  const createConversationMutation = useMutation({
    mutationFn: () => api.createConversation(token, 'New conversation'),
    onSuccess: async (conversation) => {
      setActiveId(conversation.id)
      setDraft('')
      if (window.matchMedia('(max-width: 40rem)').matches) setSidebarOpen(false)
      await queryClient.invalidateQueries({ queryKey: ['conversations', token] })
      await queryClient.invalidateQueries({ queryKey: ['messages', token, conversation.id] })
      textareaRef.current?.focus()
    },
  })

  const startNewConversation = () => {
    if (createConversationMutation.isPending) return
    createConversationMutation.mutate()
  }

  const submitDraft = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const content = draft.trim()
    if (!content || sendMutation.isPending) return
    setPendingUserMessage(content)
    setDraft('')
    sendMutation.mutate({ conversationId: activeId, content })
  }

  const authenticate = (nextToken: string, user: User) => {
    localStorage.setItem(TOKEN_KEY, nextToken)
    setCurrentUser(user)
    setToken(nextToken)
  }

  const signOut = () => {
    localStorage.removeItem(TOKEN_KEY)
    queryClient.clear()
    setCurrentUser(null)
    setActiveId(null)
    setToken('')
  }

  if (!token || !currentUser) return <AuthScreen onAuthenticated={authenticate} />

  const errorMessage = sendMutation.error instanceof ApiError
    ? sendMutation.error.message
    : createConversationMutation.error instanceof ApiError
      ? createConversationMutation.error.message
      : null

  return (
    <div className={`workspace ${sidebarOpen ? '' : 'workspace--collapsed'}`}>
      {sidebarOpen && <button className="sidebar-scrim" type="button" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />}
      <aside className="sidebar" aria-label="Conversation navigation">
        <header className="sidebar-head">
          <button className="wordmark" type="button" onClick={startNewConversation}>
            <span className="wordmark-icon"><Command size={15} /></span>
            Agent Workspace
          </button>
          <button className="icon-button" type="button" aria-label="Collapse sidebar" onClick={() => setSidebarOpen(false)}><PanelLeftClose size={18} /></button>
        </header>
        <button className="new-thread" type="button" onClick={startNewConversation} disabled={createConversationMutation.isPending}>
          <Plus size={17} /> {createConversationMutation.isPending ? 'Creating…' : 'New thread'}
        </button>
        <div className="sidebar-section">
          <p>CONVERSATIONS</p>
          <nav className="conversation-list">
            {conversationsQuery.isLoading && <span className="sidebar-note">Loading threads…</span>}
            {conversationsQuery.data?.map((conversation: Conversation) => (
              <button key={conversation.id} type="button" className={conversation.id === activeId ? 'conversation-row conversation-row--active' : 'conversation-row'} onClick={() => setActiveId(conversation.id)}>
                <MessageSquare size={15} /><span>{conversation.title}</span>
              </button>
            ))}
            {!conversationsQuery.isLoading && !conversationsQuery.data?.length && <span className="sidebar-note">Your first thread starts here.</span>}
          </nav>
        </div>
        <footer className="account-block">
          <div className="avatar">{initials(currentUser.user_name)}</div>
          <div className="account-copy"><strong>{currentUser.user_name}</strong><span>{currentUser.email}</span></div>
          <button className="icon-button" type="button" aria-label="Sign out" onClick={signOut}><LogOut size={17} /></button>
        </footer>
      </aside>

      <main className="chat-stage">
        <header className="stage-topbar">
          {!sidebarOpen && <button className="icon-button" type="button" aria-label="Open sidebar" onClick={() => setSidebarOpen(true)}><PanelLeftOpen size={18} /></button>}
          <div className="thread-identity"><span className="status-dot" /> <span>{activeConversation?.title ?? 'New conversation'}</span><ChevronDown size={15} /></div>
          <div className="model-badge"><Bot size={15} /> DeepSeek</div>
        </header>

        <section className="message-rail" aria-live="polite">
          {!activeId && (
            <div className="welcome-state">
              <div className="welcome-kicker"><Sparkles size={16} /> DAY 03 COMPLETE</div>
              <h1>What should we work through?</h1>
              <p>Create a thread with a question, a design decision, or a backend problem. Your context stays with the conversation.</p>
              <div className="prompt-suggestions">
                {['Plan a Redis memory strategy', 'Review an API contract', 'Explain this async error'].map((suggestion) => (
                  <button type="button" key={suggestion} onClick={() => setDraft(suggestion)}>{suggestion}</button>
                ))}
              </div>
            </div>
          )}
          {messagesQuery.isLoading && activeId && <div className="loading-state"><LoaderCircle size={18} /> Retrieving conversation…</div>}
          {messagesQuery.data?.map((message: Message) => (
            <article className={`message message--${message.role}`} key={message.id}>
              <div className="message-label">{message.role === 'assistant' ? 'AGENT' : currentUser.user_name.toUpperCase()}</div>
              <div className="message-content">
                {message.role === 'assistant'
                  ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                  : message.content}
              </div>
            </article>
          ))}
          {pendingUserMessage && (
            <article className="message message--user message--optimistic">
              <div className="message-label">{currentUser.user_name.toUpperCase()}</div>
              <div className="message-content">{pendingUserMessage}</div>
            </article>
          )}
          {sendMutation.isPending && (
            <article className="message message--assistant message--pending">
              <div className="message-label">AGENT</div>
              <div className="thinking"><span /><span /><span /> Thinking through it</div>
            </article>
          )}
        </section>

        <footer className="composer-area">
          {errorMessage && <p className="composer-error" role="alert">{errorMessage}. Your message was saved; you can try again.</p>}
          <form className="composer" onSubmit={submitDraft}>
            <textarea ref={textareaRef} value={draft} aria-busy={sendMutation.isPending} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit() } }} placeholder="Message your agent…" aria-label="Message your agent" rows={1} />
            <div className="composer-bottom">
              <span><span className="composer-key">↵</span> Send · <span className="composer-key">⇧↵</span> New line</span>
              <button className="send-button" type="submit" disabled={!draft.trim() || sendMutation.isPending} aria-label="Send message">{sendMutation.isPending ? <LoaderCircle size={17} /> : <ArrowUp size={18} />}</button>
            </div>
          </form>
          <p className="footer-note">Agent Workspace can make mistakes. Verify important information.</p>
        </footer>
      </main>
    </div>
  )
}

export default App
