import { Fragment, useCallback, useEffect, useState } from 'react'
import { UserCog, Loader2 } from 'lucide-react'
import { adminApi, getAdminUsername } from '@/lib/adminClient'
import { PanelShell, PanelDesc, PanelError, PanelEmpty, PanelLoading, TableWrap, TableHead } from './panel'

interface AdminAccountRow {
  id: string
  username: string
  is_active: boolean
  created_at: string
  last_login_at: string | null
}

export function AdminAccountsPanel() {
  const [rows, setRows] = useState<AdminAccountRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  /** 正在等二次确认的那一行。停用是不可逆的破坏性操作（被停的人立刻掉线），
   *  此前**点一下就执行**，手滑就没了。刻意不用 window.confirm：
   *  Chrome 在同一页面连弹几次后会让用户勾"阻止此页面创建更多对话框"，
   *  勾上之后 confirm() 直接静默返回 false，按钮就变成点了没反应的死控件
   *  （ReviewHistoryPage 已经为同一个坑立过这条规矩）。 */
  const [confirmId, setConfirmId] = useState<string | null>(null)

  /** 我自己是谁。用静态主密钥进来时没有用户名（返回 null），此时不硬猜，
   *  只是不显示"这是你自己"那条警告——不知道就不说，别编。 */
  const currentUsername = getAdminUsername()
  const activeCount = rows?.filter((r) => r.is_active).length ?? 0

  const load = useCallback(async () => {
    try {
      setRows(await adminApi.listAdminUsers())
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const create = async () => {
    if (!username.trim() || password.length < 8) return
    setBusy(true)
    setError(null)
    try {
      await adminApi.createAdminUser(username.trim(), password)
      setUsername('')
      setPassword('')
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '创建失败')
    } finally {
      setBusy(false)
    }
  }

  const deactivate = async (id: string) => {
    setBusy(true)
    setError(null)
    try {
      await adminApi.deactivateAdminUser(id)
      setConfirmId(null)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '停用失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <PanelShell icon={UserCog} title="管理员账号" hint="具名登录，操作可追溯到人">
      <PanelDesc>
        每个人一个用户名+密码，登录后台不再共用一把令牌。停用的账号立即无法再用其已签发的会话登录。
      </PanelDesc>

      {error && <PanelError>{error}</PanelError>}

      {rows === null ? (
        <PanelLoading />
      ) : rows.length === 0 ? (
        <PanelEmpty />
      ) : (
        <div className="mt-4">
          <TableWrap>
            <TableHead>
              <tr>
                <th className="py-1.5">用户名</th>
                <th className="py-1.5">状态</th>
                <th className="py-1.5">最近登录</th>
                <th className="py-1.5 text-right">操作</th>
              </tr>
            </TableHead>
            <tbody>
              {rows.map((r) => {
                const isSelf = !!currentUsername && r.username === currentUsername
                const isLastActive = r.is_active && activeCount <= 1
                return (
                <Fragment key={r.id}>
                <tr className="border-t border-border">
                  <td className="py-1.5 text-text-primary">
                    {r.username}
                    {isSelf && <span className="ml-1.5 text-[10px] text-text-muted">（你）</span>}
                  </td>
                  <td className="py-1.5">
                    {r.is_active ? (
                      <span className="text-brand-primary">启用</span>
                    ) : (
                      <span className="text-text-muted">已停用</span>
                    )}
                  </td>
                  <td className="py-1.5 text-text-muted">
                    {r.last_login_at ? new Date(r.last_login_at).toLocaleString() : '尚未登录'}
                  </td>
                  <td className="py-1.5 text-right">
                    {r.is_active && confirmId !== r.id && (
                      <button
                        onClick={() => { setError(null); setConfirmId(r.id) }}
                        disabled={busy}
                        className="rounded-md bg-severity-critical/10 px-2.5 py-1 text-[11px] text-severity-critical hover:bg-severity-critical/20 transition-colors disabled:opacity-50"
                      >
                        停用
                      </button>
                    )}
                    {r.is_active && confirmId === r.id && (
                      <div className="flex justify-end gap-1.5">
                        <button
                          onClick={() => setConfirmId(null)}
                          disabled={busy}
                          className="rounded-md border border-border px-2.5 py-1 text-[11px] text-text-secondary hover:text-text-primary transition-colors disabled:opacity-50"
                        >
                          取消
                        </button>
                        <button
                          onClick={() => void deactivate(r.id)}
                          disabled={busy}
                          className="rounded-md bg-severity-critical px-2.5 py-1 text-[11px] font-semibold text-bg-primary hover:opacity-90 transition-opacity disabled:opacity-50"
                        >
                          确认停用
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
                {/* 确认态单独占一行：后果写在按钮**旁边**而不是事后才知道。
                    两条警告可以同时成立（自己 + 最后一个），所以不是 else if。 */}
                {confirmId === r.id && (
                  <tr className="border-t border-border/50">
                    <td colSpan={4} className="py-2">
                      <p className="text-[11px] text-text-secondary">
                        停用「{r.username}」后，它已签发的会话立即失效，本人会当场掉线。此操作在后台界面里没有撤销入口。
                      </p>
                      {isSelf && (
                        <p className="mt-1 text-[11px] font-semibold text-severity-critical">
                          这是你当前登录的账号——确认后你自己会被立刻踢出后台。
                        </p>
                      )}
                      {isLastActive && (
                        <p className="mt-1 text-[11px] font-semibold text-severity-critical">
                          这是最后一个启用中的管理员账号。停用之后，除非用服务端的 AL_ADMIN_TOKEN 原文登录，否则没有人能再进来。
                        </p>
                      )}
                    </td>
                  </tr>
                )}
                </Fragment>
                )
              })}
            </tbody>
          </TableWrap>
        </div>
      )}

      <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-3">
        <input
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="新账号用户名"
          className="rounded-lg border border-border bg-bg-secondary px-3 py-2 font-mono text-sm text-text-primary placeholder-text-muted outline-none focus:border-brand-primary transition-colors"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="密码（至少 8 位）"
          className="rounded-lg border border-border bg-bg-secondary px-3 py-2 font-mono text-sm text-text-primary placeholder-text-muted outline-none focus:border-brand-primary transition-colors"
        />
        <button
          onClick={() => void create()}
          disabled={busy || !username.trim() || password.length < 8}
          className="flex items-center justify-center gap-1.5 rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-bg-primary hover:bg-brand-primary-dim transition-colors disabled:opacity-50"
        >
          {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.5} />}
          新建
        </button>
      </div>
    </PanelShell>
  )
}
