import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'

const state = {
  assets: [{ id: 'asset_1', name: 'launch.mp4', type: 'video', source: 'local' }],
  tasks: [{ id: 'task_1', title: '新品发布短片', module: 'intelligent_editing', status: 'pending', progress: 0 }],
  orders: [],
  users: [{ id: 'local-user', name: '本地用户', role: 'admin' }],
  membership: { plan: 'trial', quota_total: 100, quota_used: 12, features: ['generation'] },
  provider_configs: [{ kind: 'video', provider: 'mock', enabled: true, has_token: false }],
}

beforeEach(() => {
  localStorage.clear()
  global.fetch = vi.fn(async (url, options = {}) => {
    if (url === '/api/auth/login' && options.method === 'POST') {
      return Response.json({
        token: 'test-token',
        user: { id: 'acct_1', username: 'creator', display_name: '创作者', role: 'user' },
      })
    }
    if (url === '/api/wallet/recharge' && options.method === 'POST') {
      return Response.json({
        account_id: 'acct_1',
        balance: 200,
        transactions: [{ id: 'txn_1', type: 'recharge', amount: 200, balance_after: 200, note: '充值' }],
      })
    }
    if (url === '/api/workbench/state') {
      const headers = options.headers || {}
      if (headers.Authorization !== 'Bearer test-token') return Response.json({ detail: 'Missing bearer token' }, { status: 401 })
      return Response.json({
        ...state,
        current_user: { id: 'acct_1', username: 'creator', display_name: '创作者', role: 'user' },
        wallet: { account_id: 'acct_1', balance: 0, transactions: [] },
      })
    }
    if (url === '/api/tasks' && options.method === 'POST') {
      return Response.json({ id: 'task_new', title: '测试任务', module: 'intelligent_editing', status: 'pending', progress: 0 })
    }
    if (url === '/api/subtitles/srt') {
      return Response.json({ srt: '1\n00:00:00,000 --> 00:00:01,000\n开场\n' })
    }
    if (url === '/api/chat' && options.method === 'POST') {
      return Response.json({ reply: '已生成镜头建议' })
    }
    return Response.json({})
  })
})

afterEach(() => {
  cleanup()
  localStorage.clear()
  vi.restoreAllMocks()
})

async function login() {
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText('账号'), 'creator')
  await user.type(screen.getByLabelText('密码'), 'strong-password')
  await user.click(screen.getByRole('button', { name: '登录' }))
  await screen.findByText('视频创作工作台')
  return user
}

test('renders every reference module in the workbench navigation', async () => {
  render(<App />)
  await login()

  for (const label of ['素材与任务', '智能剪辑', '镜头控制', '画面处理', '字幕', '配音', '账号与会员', '支付与后台', '接口对接']) {
    expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
  }
})

test('creates a workbench task from the studio form', async () => {
  render(<App />)
  const user = await login()

  await screen.findByDisplayValue('新品发布短片')
  await user.clear(screen.getByLabelText('任务名称'))
  await user.type(screen.getByLabelText('任务名称'), '测试任务')
  await user.clear(screen.getByLabelText('故事主题'))
  await user.type(screen.getByLabelText('故事主题'), '城市夜景新品发布')
  await user.click(screen.getByRole('button', { name: '创建任务' }))

  await waitFor(() => {
    expect(global.fetch).toHaveBeenCalledWith('/api/tasks', expect.objectContaining({ method: 'POST' }))
  })
  await waitFor(() => {
    expect(screen.getAllByText('测试任务').length).toBeGreaterThan(0)
  })
})

test('keeps the chat assistant in the frontend workbench', async () => {
  render(<App />)
  const user = await login()

  await screen.findByText('智能助手')
  await user.type(screen.getByPlaceholderText('输入问题，按 Ctrl+Enter 发送'), '帮我规划镜头')
  await user.click(screen.getByRole('button', { name: '发送' }))

  await waitFor(() => {
    expect(global.fetch).toHaveBeenCalledWith('/api/chat', expect.objectContaining({ method: 'POST' }))
  })
  expect(await screen.findByText('已生成镜头建议')).toBeInTheDocument()
})

test('logs in and recharges account balance', async () => {
  render(<App />)
  const user = await login()

  expect(screen.getByText('创作者')).toBeInTheDocument()
  expect(screen.getByText('余额 0')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '账号与会员' }))
  await user.clear(screen.getByLabelText('充值金额'))
  await user.type(screen.getByLabelText('充值金额'), '200')
  await user.click(screen.getByRole('button', { name: '充值余额' }))

  await waitFor(() => {
    expect(global.fetch).toHaveBeenCalledWith('/api/wallet/recharge', expect.objectContaining({
      method: 'POST',
      headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
    }))
  })
  expect(await screen.findByText('余额 200')).toBeInTheDocument()
})
