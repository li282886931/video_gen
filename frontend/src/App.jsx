import React, { useState, useRef } from 'react'

export default function App() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: '你好！这是 VideoGen 的聊天演示（Vite + React）。' }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const controllerRef = useRef(null)

  const send = async () => {
    if (!input.trim()) return
    const userMsg = { role: 'user', content: input }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    // Abort existing stream if any
    if (controllerRef.current) {
      controllerRef.current.abort()
    }
    const controller = new AbortController()
    controllerRef.current = controller

    try {
      const history = messages.map(m => ({ role: m.role, content: m.content }))
      const resp = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: input, history }),
        signal: controller.signal,
      })

      if (!resp.body) {
        const json = await resp.json()
        setMessages(prev => [...prev, { role: 'assistant', content: json.detail || '无响应' }])
        setLoading(false)
        return
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let assistantText = ''
      setMessages(prev => [...prev, { role: 'assistant', content: '' }])
      let assistantIndex = messages.length

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        assistantText += chunk
        setMessages(prev => {
          // replace last assistant placeholder
          const copy = prev.slice()
          copy[assistantIndex] = { role: 'assistant', content: assistantText }
          return copy
        })
      }

    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: '调用接口出错: ' + err.message }])
    } finally {
      setLoading(false)
      controllerRef.current = null
    }
  }

  const onKey = (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) send()
  }

  return (
    <div className="chat-wrap">
      <div className="chat-window">
        {messages.map((m, i) => (
          <div key={i} className={`message ${m.role}`}>
            {m.content}
          </div>
        ))}
      </div>
      <div className="chat-input">
        <textarea value={input} onChange={e => setInput(e.target.value)} onKeyDown={onKey} placeholder="输入问题，按 Ctrl+Enter 发送" />
        <div className="controls">
          <button onClick={send} disabled={loading}>{loading ? '发送中…' : '发送'}</button>
        </div>
      </div>
    </div>
  )
}
