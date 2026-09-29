import { useState, type FormEvent } from 'react'
import { useMutation } from '@tanstack/react-query'
import { ArrowRight, CircleCheck, FileSearch, LockKeyhole, ScanLine } from 'lucide-react'
import { api } from '../../api/client'
import type { User } from '../../api/types'
import { displayError } from '../../lib/format'

export function LoginPage({ onLogin }: { onLogin: (user: User) => void }) {
  const [email, setEmail] = useState('operator@example.com')
  const [password, setPassword] = useState('DemoPass123!')
  const login = useMutation({
    mutationFn: () => api.login(email.trim(), password),
    onSuccess: (response) => {
      onLogin(response.user)
    },
  })
  const submit = (event: FormEvent) => { event.preventDefault(); login.mutate() }
  return <main className="login-shell">
    <section className="login-left">
      <div className="brand brand-login"><span className="brand-mark"><ScanLine size={22} strokeWidth={2.2} /></span><span>Invoice<span className="brand-strong">Lens</span></span></div>
      <div className="login-intro">
        <span className="eyebrow"><span className="eyebrow-line" /> DOCUMENT OPERATIONS / HARBOR INDUSTRIAL</span>
        <h1>Every number<br /><em>has a source.</em></h1>
        <p>Move from an unread invoice to a reviewed, evidence-backed record your accounting team can use.</p>
        <div className="login-flow"><span><FileSearch size={17} /> Examine</span><i /><span><CircleCheck size={17} /> Reconcile</span><i /><span><ArrowRight size={17} /> Export</span></div>
      </div>
      <div className="login-footer">SYNTHETIC DEMO DATASET <span>·</span> LOCAL PILOT WORKSPACE</div>
    </section>
    <section className="login-right">
      <div className="login-card">
        <span className="card-kicker">WORKSPACE ACCESS</span>
        <h2>Welcome back.</h2>
        <p className="muted">Sign in to the Harbor Industrial review desk.</p>
        <form onSubmit={submit} className="login-form">
          <label htmlFor="email">Email address</label>
          <input id="email" type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} required />
          <label htmlFor="password">Password</label>
          <input id="password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          {login.isError && <div className="inline-error" role="alert">{displayError(login.error)}</div>}
          <button className="button button-primary login-submit" type="submit" disabled={login.isPending}>{login.isPending ? 'Signing in…' : 'Enter workbench'} <ArrowRight size={17} /></button>
        </form>
        <div className="demo-hint"><LockKeyhole size={16} /><div><strong>Local demo access</strong><span>operator@example.com / DemoPass123!</span></div></div>
      </div>
      <p className="login-aside">InvoiceLens v1 pilot <span>·</span> No real customer documents</p>
    </section>
  </main>
}
