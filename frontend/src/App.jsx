import { useEffect, useMemo, useState } from 'react'
import {
  BadgeDollarSign,
  Clapperboard,
  Film,
  Gauge,
  Image,
  Layers,
  Mic2,
  Scissors,
  Settings2,
  Sparkles,
  Subtitles,
  UserCircle,
  Wand2,
} from 'lucide-react'

const modules = [
  { id: 'assets', label: '素材与任务', icon: Image },
  { id: 'editing', label: '智能剪辑', icon: Scissors },
  { id: 'lens', label: '镜头控制', icon: Clapperboard },
  { id: 'material', label: '素材处理', icon: Layers },
  { id: 'screen', label: '画面处理', icon: Wand2 },
  { id: 'quality', label: '画质增强', icon: Sparkles },
  { id: 'watermark', label: '水印处理', icon: Gauge },
  { id: 'subtitles', label: '字幕', icon: Subtitles },
  { id: 'voiceover', label: '配音', icon: Mic2 },
  { id: 'account', label: '账号与会员', icon: UserCircle },
  { id: 'payment', label: '支付与后台', icon: BadgeDollarSign },
  { id: 'providers', label: '接口对接', icon: Settings2 },
]

const defaultState = {
  assets: [],
  tasks: [],
  orders: [],
  users: [],
  membership: { plan: 'trial', quota_total: 100, quota_used: 0, features: [] },
  provider_configs: [],
}

function metricValue(value, suffix = '') {
  if (value === undefined || value === null || value === '') return '-'
  return `${value}${suffix}`
}

export default function App() {
  const [activeModule, setActiveModule] = useState('assets')
  const [state, setState] = useState(defaultState)
  const [token, setToken] = useState(() => localStorage.getItem('videoGenToken') || '')
  const [currentUser, setCurrentUser] = useState(null)
  const [wallet, setWallet] = useState({ balance: 0, transactions: [] })
  const [taskTitle, setTaskTitle] = useState('新品发布短片')
  const [storyPrompt, setStoryPrompt] = useState('城市夜景中的新品发布会，展示品牌、人物情绪和产品细节')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (token) {
      loadState(token)
    }
  }, [token])

  function authHeaders(authToken = token) {
    return authToken ? { Authorization: `Bearer ${authToken}` } : {}
  }

  async function loadState(authToken = token) {
    try {
      const resp = await fetch('/api/workbench/state', { headers: authHeaders(authToken) })
      if (!resp.ok) throw new Error('工作台状态读取失败')
      const data = await resp.json()
      setState({ ...defaultState, ...data })
      setCurrentUser(data.current_user || null)
      setWallet(data.wallet || { balance: 0, transactions: [] })
    } catch (err) {
      setNotice(err.message)
      if (String(err.message).includes('读取失败')) {
        setToken('')
        localStorage.removeItem('videoGenToken')
      }
    }
  }

  async function login(username, password) {
    setLoading(true)
    setNotice('')
    try {
      const resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      if (!resp.ok) throw new Error('登录失败')
      const data = await resp.json()
      localStorage.setItem('videoGenToken', data.token)
      setToken(data.token)
      setCurrentUser(data.user)
      await loadState(data.token)
    } catch (err) {
      setNotice(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function recharge(amount) {
    setLoading(true)
    setNotice('')
    try {
      const resp = await fetch('/api/wallet/recharge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ amount, note: '账户充值' }),
      })
      if (!resp.ok) throw new Error('充值失败')
      const data = await resp.json()
      setWallet(data)
      setNotice('充值成功')
    } catch (err) {
      setNotice(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function createTask(event) {
    event.preventDefault()
    if (!taskTitle.trim() || !storyPrompt.trim()) return
    setLoading(true)
    setNotice('')
    const payload = {
      title: taskTitle.trim(),
      module: 'intelligent_editing',
      story_prompt: storyPrompt.trim(),
      asset_ids: state.assets.slice(0, 1).map((asset) => asset.id),
      edit_profile: buildEditProfile(),
      subtitle_cues: [{ start_ms: 0, end_ms: 3000, text: '开场建立视觉主题' }],
      voiceover: { voice: 'standard', speed: 1, language: 'zh-CN' },
    }
    try {
      const resp = await fetch('/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(payload),
      })
      if (!resp.ok) throw new Error('任务创建失败')
      const task = await resp.json()
      setState((prev) => ({ ...prev, tasks: [task, ...prev.tasks] }))
      setNotice('任务已创建')
    } catch (err) {
      setNotice(err.message)
    } finally {
      setLoading(false)
    }
  }

  const activeModuleMeta = modules.find((item) => item.id === activeModule)
  const quotaRatio = useMemo(() => {
    const total = state.membership?.quota_total || 1
    return Math.min(100, Math.round(((state.membership?.quota_used || 0) / total) * 100))
  }, [state.membership])

  if (!token) {
    return <LoginScreen loading={loading} notice={notice} onLogin={login} />
  }

  return (
    <div className="workspace">
      <aside className="sidebar" aria-label="工作台导航">
        <div className="brand">
          <Film size={24} aria-hidden="true" />
          <div>
            <strong>视频创作工作台</strong>
            <span>批量生成与剪辑中枢</span>
          </div>
        </div>
        <nav className="module-nav">
          {modules.map((item) => {
            const Icon = item.icon
            return (
              <button
                key={item.id}
                type="button"
                className={activeModule === item.id ? 'active' : ''}
                onClick={() => setActiveModule(item.id)}
              >
                <Icon size={17} aria-hidden="true" />
                {item.label}
              </button>
            )
          })}
        </nav>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <span className="eyebrow">Production Console</span>
            <h1>{activeModuleMeta?.label || '素材与任务'}</h1>
          </div>
          <div className="status-strip">
            <span>{currentUser?.display_name || currentUser?.username || '未登录'}</span>
            <span>余额 {metricValue(wallet.balance)}</span>
            <span>任务 {state.tasks.length}</span>
            <span>素材 {state.assets.length}</span>
            <span>用量 {quotaRatio}%</span>
          </div>
        </header>

        {notice && <div className="notice">{notice}</div>}

        <section className="content-grid">
          <div className="primary-panel">
            {activeModule === 'assets' && (
              <AssetTaskPanel
                assets={state.assets}
                tasks={state.tasks}
                taskTitle={taskTitle}
                storyPrompt={storyPrompt}
                loading={loading}
                onTaskTitleChange={setTaskTitle}
                onStoryPromptChange={setStoryPrompt}
                onCreateTask={createTask}
              />
            )}
            {activeModule === 'editing' && <FeaturePanel title="智能剪辑" items={editingItems} />}
            {activeModule === 'lens' && <FeaturePanel title="镜头控制" items={lensItems} />}
            {activeModule === 'material' && <FeaturePanel title="素材处理" items={materialItems} />}
            {activeModule === 'screen' && <FeaturePanel title="画面处理" items={screenItems} />}
            {activeModule === 'quality' && <FeaturePanel title="画质增强" items={qualityItems} />}
            {activeModule === 'watermark' && <WatermarkPanel />}
            {activeModule === 'subtitles' && <SubtitlePanel />}
            {activeModule === 'voiceover' && <VoiceoverPanel />}
            {activeModule === 'account' && (
              <AccountPanel
                membership={state.membership}
                users={state.users}
                currentUser={currentUser}
                wallet={wallet}
                loading={loading}
                onRecharge={recharge}
              />
            )}
            {activeModule === 'payment' && <PaymentPanel orders={state.orders} tasks={state.tasks} />}
            {activeModule === 'providers' && <ProviderPanel providers={state.provider_configs} />}
          </div>
          <StatusPanel
            tasks={state.tasks}
            providers={state.provider_configs}
            membership={state.membership}
            wallet={wallet}
          />
        </section>
      </main>
    </div>
  )
}

function LoginScreen({ loading, notice, onLogin }) {
  const [username, setUsername] = useState('local-user')
  const [password, setPassword] = useState('local-password')

  function submit(event) {
    event.preventDefault()
    onLogin(username, password)
  }

  return (
    <main className="login-page">
      <form className="login-panel" onSubmit={submit}>
        <div className="brand login-brand">
          <Film size={24} aria-hidden="true" />
          <div>
            <strong>视频创作工作台</strong>
            <span>登录后进入生产控制台</span>
          </div>
        </div>
        {notice && <div className="notice">{notice}</div>}
        <label>
          账号
          <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
        </label>
        <label>
          密码
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
          />
        </label>
        <button type="submit" className="primary-action" disabled={loading}>
          <UserCircle size={16} aria-hidden="true" />
          {loading ? '登录中' : '登录'}
        </button>
      </form>
    </main>
  )
}

function buildEditProfile() {
  return {
    editing: { target_duration: 30, batch: true, first_pass_plan: true },
    lens: { random_combo: true, sweep_light: { direction: 'left_to_right', intensity: 62, speed: 44 } },
    material: { crop: 'smart', speed: 1, mirror: false },
    screen: { fps: 30, resolution: '1080x1920', bitrate: '4500k', denoise: true },
    quality: { sharpen: 35, frame_interpolation: false, face_restore: false },
    watermark: { mode: 'blur', region: { x: 24, y: 24, width: 180, height: 72 } },
    export: { format: 'mp4' },
  }
}

function AssetTaskPanel({
  assets,
  tasks,
  taskTitle,
  storyPrompt,
  loading,
  onTaskTitleChange,
  onStoryPromptChange,
  onCreateTask,
}) {
  return (
    <div className="panel-stack">
      <section className="section">
        <div className="section-head">
          <h2>创作入口</h2>
          <span>素材、脚本、镜头与导出统一编排</span>
        </div>
        <form className="task-form" onSubmit={onCreateTask}>
          <label>
            任务名称
            <input value={taskTitle} onChange={(event) => onTaskTitleChange(event.target.value)} />
          </label>
          <label>
            故事主题
            <textarea value={storyPrompt} onChange={(event) => onStoryPromptChange(event.target.value)} rows={4} />
          </label>
          <button type="submit" className="primary-action" disabled={loading}>
            <Sparkles size={16} aria-hidden="true" />
            {loading ? '创建中' : '创建任务'}
          </button>
        </form>
      </section>

      <section className="two-column">
        <DataTable
          title="素材库"
          columns={['名称', '类型', '来源']}
          rows={assets.map((asset) => [asset.name, asset.type, asset.source])}
          empty="暂无素材"
        />
        <DataTable
          title="任务队列"
          columns={['名称', '模块', '状态']}
          rows={tasks.map((task) => [task.title, task.module, task.status])}
          empty="暂无任务"
        />
      </section>
    </div>
  )
}

const editingItems = [
  ['镜头切分', '按脚本段落和目标时长生成镜头列表'],
  ['拉指定时长', '将片段对齐到 15-30 秒或自定义区间'],
  ['镜头重排拼接', '按叙事节奏重排并生成拼接清单'],
  ['批量生成', '多任务队列与输出 manifest'],
  ['首期规划', '为连续内容生成第一期结构'],
  ['换镜头分析', '按帧抽样记录候选镜头与验收结果'],
]

const lensItems = [
  ['随机镜头组合', '广角、跟拍、低角度、肩后与俯拍自动组合'],
  ['镜头切换', '硬切、淡入淡出、推拉与转场参数预设'],
  ['扫光方向', '左至右、右至左、上下扫光'],
  ['强度与速度', '滑块化调节并写入任务配置'],
]

const materialItems = [
  ['镜头重组', '保留原素材顺序或按脚本重新组合'],
  ['裁剪缩放', '适配横屏、竖屏、方形输出'],
  ['变速镜像', '局部变速与水平镜像处理'],
  ['画面音轨', '音量、静音与原音保留策略'],
  ['参数随机组合', '多组配置批量派生任务'],
]

const screenItems = [
  ['抽帧', '生成关键帧验收样本'],
  ['黑白调色', '黑白、色温、对比度与饱和度'],
  ['模糊边框噪点', '统一画面包装与风格化处理'],
  ['消音', '移除原始音轨'],
  ['编码元数据', '分辨率、码率、帧率与元数据清理'],
]

const qualityItems = [
  ['锐化', '细节增强强度可配置'],
  ['降噪', '弱光与压缩噪点处理开关'],
  ['补帧', '通过 provider adapter 预留真实实现'],
  ['人像修复', '通过 provider adapter 预留真实实现'],
  ['画质增强', '统一增强配置与任务状态跟踪'],
]

function FeaturePanel({ title, items }) {
  return (
    <section className="section">
      <div className="section-head">
        <h2>{title}</h2>
        <span>配置会写入任务 profile，后端按本地能力或 provider adapter 执行</span>
      </div>
      <div className="control-grid">
        {items.map(([name, desc]) => (
          <div className="control-card" key={name}>
            <div>
              <strong>{name}</strong>
              <p>{desc}</p>
            </div>
            <label className="switch">
              <input type="checkbox" defaultChecked />
              <span />
            </label>
          </div>
        ))}
      </div>
      <div className="slider-row">
        <label>
          强度
          <input type="range" min="0" max="100" defaultValue="62" />
        </label>
        <label>
          速度
          <input type="range" min="0" max="100" defaultValue="44" />
        </label>
      </div>
    </section>
  )
}

function WatermarkPanel() {
  return (
    <section className="section">
      <div className="section-head">
        <h2>水印区域处理</h2>
        <span>按用户指定区域执行遮罩、模糊或裁剪</span>
      </div>
      <div className="region-grid">
        {['X', 'Y', '宽度', '高度'].map((label, index) => (
          <label key={label}>
            {label}
            <input type="number" defaultValue={[24, 24, 180, 72][index]} />
          </label>
        ))}
      </div>
      <div className="segmented" aria-label="水印处理方式">
        <button type="button">模糊</button>
        <button type="button">遮罩</button>
        <button type="button">裁剪</button>
      </div>
    </section>
  )
}

function SubtitlePanel() {
  return (
    <section className="section">
      <div className="section-head">
        <h2>字幕编辑</h2>
        <span>时间轴、字体、颜色、位置与 SRT 导出</span>
      </div>
      <div className="subtitle-list">
        {[
          ['00:00.000', '00:03.000', '开场建立视觉主题'],
          ['00:03.000', '00:08.000', '展示人物情绪和产品细节'],
        ].map(([start, end, text]) => (
          <div className="subtitle-row" key={text}>
            <span>{start}</span>
            <span>{end}</span>
            <input defaultValue={text} />
          </div>
        ))}
      </div>
      <button type="button" className="secondary-action">
        <Subtitles size={16} aria-hidden="true" />
        导出 SRT
      </button>
    </section>
  )
}

function VoiceoverPanel() {
  return (
    <section className="section">
      <div className="section-head">
        <h2>配音</h2>
        <span>文本输入、音色、语速、音频导出与时间同步</span>
      </div>
      <label>
        配音文本
        <textarea rows={5} defaultValue="欢迎来到新品发布现场，城市灯光映出产品的轮廓。" />
      </label>
      <div className="region-grid">
        <label>
          音色
          <select defaultValue="standard">
            <option value="standard">标准女声</option>
            <option value="warm">温和男声</option>
            <option value="news">新闻播报</option>
          </select>
        </label>
        <label>
          语速
          <input type="range" min="60" max="160" defaultValue="100" />
        </label>
      </div>
    </section>
  )
}

function AccountPanel({ membership, users, currentUser, wallet, loading, onRecharge }) {
  const [amount, setAmount] = useState('100')

  return (
    <section className="section">
      <div className="section-head">
        <h2>账号与会员</h2>
        <span>登录态、套餐、有效期、续费与权限控制</span>
      </div>
      <div className="summary-grid">
        <Metric label="当前用户" value={currentUser?.display_name || users?.[0]?.name || '本地用户'} />
        <Metric label="套餐" value={membership?.plan || 'trial'} />
        <Metric label="额度" value={`${membership?.quota_used || 0}/${membership?.quota_total || 0}`} />
        <Metric label="账户余额" value={metricValue(wallet?.balance)} />
      </div>
      <form className="wallet-form" onSubmit={(event) => { event.preventDefault(); onRecharge(Number(amount)) }}>
        <label>
          充值金额
          <input type="number" min="1" step="1" value={amount} onChange={(event) => setAmount(event.target.value)} />
        </label>
        <button type="submit" className="primary-action" disabled={loading}>
          <BadgeDollarSign size={16} aria-hidden="true" />
          充值余额
        </button>
      </form>
      <DataTable
        title="余额流水"
        columns={['类型', '金额', '余额']}
        rows={(wallet?.transactions || []).map((item) => [item.type, item.amount, item.balance_after])}
        empty="暂无流水"
      />
    </section>
  )
}

function PaymentPanel({ orders, tasks }) {
  return (
    <section className="section">
      <div className="section-head">
        <h2>支付与后台</h2>
        <span>渠道对接、订单状态、会员开通与后台配置</span>
      </div>
      <div className="summary-grid">
        <Metric label="订单数" value={orders.length} />
        <Metric label="任务数" value={tasks.length} />
        <Metric label="支付渠道" value="adapter" />
      </div>
      <DataTable
        title="订单"
        columns={['套餐', '金额', '状态']}
        rows={orders.map((order) => [order.plan, metricValue(order.amount), order.status])}
        empty="暂无订单"
      />
    </section>
  )
}

function ProviderPanel({ providers }) {
  return (
    <section className="section">
      <div className="section-head">
        <h2>接口对接</h2>
        <span>图像、视频、字幕、配音、支付与存储统一接入</span>
      </div>
      <div className="provider-list">
        {providers.map((provider) => (
          <div className="provider-row" key={`${provider.kind}-${provider.provider}`}>
            <strong>{provider.kind}</strong>
            <span>{provider.provider}</span>
            <span>{provider.enabled ? '启用' : '停用'}</span>
            <span>{provider.has_token ? '已配置密钥' : '未配置密钥'}</span>
          </div>
        ))}
      </div>
    </section>
  )
}

function StatusPanel({ tasks, providers, membership, wallet }) {
  const latest = tasks[0]
  return (
    <aside className="status-panel">
      <section>
        <h2>任务状态</h2>
        {latest ? (
          <div className="latest-task">
            <strong>{latest.title}</strong>
            <span>{latest.status}</span>
            <div className="progress"><i style={{ width: `${latest.progress || 0}%` }} /></div>
          </div>
        ) : (
          <p>暂无任务</p>
        )}
      </section>
      <section>
        <h2>运行环境</h2>
        <Metric label="会员套餐" value={membership?.plan || 'trial'} />
        <Metric label="账户余额" value={metricValue(wallet?.balance)} />
        <Metric label="接口数量" value={providers.length} />
        <Metric label="导出格式" value="MP4 / SRT" />
      </section>
      <ChatAssistant />
    </aside>
  )
}

function ChatAssistant() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: '你好！这是 VideoGen 的智能助手。输入问题开始对话。' },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

  async function send() {
    if (!input.trim()) return
    const currentInput = input
    const userMessage = { role: 'user', content: currentInput }
    const history = messages.map((message) => ({ role: message.role, content: message.content }))
    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: currentInput, history }),
      })
      if (!resp.ok) throw new Error('智能助手响应失败')
      const data = await resp.json()
      setMessages((prev) => [...prev, { role: 'assistant', content: data.reply || '' }])
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'assistant', content: `调用接口出错: ${err.message}` }])
    } finally {
      setLoading(false)
    }
  }

  function onKeyDown(event) {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      send()
    }
  }

  return (
    <section className="assistant-panel">
      <h2>智能助手</h2>
      <div className="assistant-messages">
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`assistant-message ${message.role}`}>
            {message.content}
          </div>
        ))}
      </div>
      <textarea
        value={input}
        onChange={(event) => setInput(event.target.value)}
        onKeyDown={onKeyDown}
        placeholder="输入问题，按 Ctrl+Enter 发送"
        rows={3}
      />
      <button type="button" className="secondary-action" onClick={send} disabled={loading}>
        <Sparkles size={16} aria-hidden="true" />
        {loading ? '发送中' : '发送'}
      </button>
    </section>
  )
}

function DataTable({ title, columns, rows, empty }) {
  return (
    <section className="section compact">
      <h2>{title}</h2>
      <table>
        <thead>
          <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
        </thead>
        <tbody>
          {rows.length ? rows.map((row, index) => (
            <tr key={`${title}-${index}`}>
              {row.map((cell, cellIndex) => <td key={cellIndex}>{cell || '-'}</td>)}
            </tr>
          )) : (
            <tr><td colSpan={columns.length}>{empty}</td></tr>
          )}
        </tbody>
      </table>
    </section>
  )
}

function Metric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}
