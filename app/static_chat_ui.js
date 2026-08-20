const e = React.createElement;

function ChatApp() {
  const [messages, setMessages] = React.useState([]);
  const [input, setInput] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    // welcome message
    setMessages([{ role: "assistant", content: "你好！这是 VideoGen 的聊天演示。输入问题开始对话。" }]);
  }, []);

  async function send() {
    if (!input.trim()) return;
    const userMsg = { role: "user", content: input };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const history = messages.map((m) => ({ role: m.role, content: m.content }));
      const body = { message: input, history };
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await resp.json();
      const assistant = { role: 'assistant', content: data.reply || '' };
      setMessages((m) => [...m, assistant]);
    } catch (err) {
      setMessages((m) => [...m, { role: 'assistant', content: '调用接口出错: ' + err.message }]);
    } finally {
      setLoading(false);
    }
  }

  function onKey(e) {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      send();
    }
  }

  return e('div', { className: 'chat-container' },
    e('div', { className: 'chat-window' },
      messages.map((m, i) => e('div', { key: i, className: 'message ' + m.role }, m.content))
    ),
    e('div', { className: 'chat-input' },
      e('textarea', {
        value: input,
        onChange: (ev) => setInput(ev.target.value),
        onKeyDown: onKey,
        placeholder: '输入问题，按 Ctrl+Enter 发送',
      }),
      e('div', { className: 'controls' },
        e('button', { onClick: send, disabled: loading }, loading ? '发送中…' : '发送')
      )
    )
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(ChatApp));
