import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { Shield, GitBranch, Zap, Key, BookOpen, Activity } from 'lucide-react'
import Dashboard   from './pages/Dashboard.jsx'
import MerklePage  from './pages/MerklePage.jsx'
import AttackPage  from './pages/AttackPage.jsx'
import ShamirPage  from './pages/ShamirPage.jsx'
import LedgerPage  from './pages/LedgerPage.jsx'

const NAV_ITEMS = [
  { to: '/',        icon: Activity,   label: 'Dashboard' },
  { to: '/merkle',  icon: GitBranch,  label: 'Merkle Tree' },
  { to: '/attacks', icon: Zap,        label: 'Attack Sim' },
  { to: '/shamir',  icon: Key,        label: 'Shamir SSS' },
  { to: '/ledger',  icon: BookOpen,   label: 'Ledger' },
]

export default function App() {
  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Sidebar */}
      <aside style={{
        width:      '220px',
        minHeight:  '100vh',
        background: 'var(--bg-secondary)',
        borderRight:'1px solid var(--border)',
        display:    'flex',
        flexDirection: 'column',
        flexShrink: 0,
        position:   'sticky',
        top:        0,
        height:     '100vh',
      }}>
        {/* Logo */}
        <div style={{
          padding:      '28px 20px 24px',
          borderBottom: '1px solid var(--border)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
            <Shield size={18} color="var(--accent-green)" />
            <span style={{
              fontFamily:    'var(--font-mono)',
              fontSize:      '15px',
              fontWeight:    '700',
              color:         'var(--accent-green)',
              letterSpacing: '0.08em',
              animation:     'flicker 8s infinite',
            }}>
              MODELGUARD
            </span>
          </div>
          <div style={{
            fontSize:   '10px',
            color:      'var(--text-dim)',
            fontFamily: 'var(--font-mono)',
            letterSpacing: '0.1em',
          }}>
            CRYPTOGRAPHIC INTEGRITY
          </div>
        </div>

        {/* Nav */}
        <nav style={{ padding: '16px 0', flex: 1 }}>
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              style={({ isActive }) => ({
                display:        'flex',
                alignItems:     'center',
                gap:            '10px',
                padding:        '10px 20px',
                textDecoration: 'none',
                fontFamily:     'var(--font-mono)',
                fontSize:       '12px',
                letterSpacing:  '0.06em',
                color:          isActive ? 'var(--accent-green)' : 'var(--text-secondary)',
                background:     isActive ? '#00ff8810' : 'transparent',
                borderLeft:     isActive ? '2px solid var(--accent-green)' : '2px solid transparent',
                transition:     'all 0.15s',
              })}
            >
              <Icon size={14} />
              {label.toUpperCase()}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div style={{
          padding:      '16px 20px',
          borderTop:    '1px solid var(--border)',
          fontSize:     '10px',
          color:        'var(--text-dim)',
          fontFamily:   'var(--font-mono)',
          lineHeight:   '1.8',
        }}>
          <div>ED25519 + BLAKE3</div>
          <div>SHAMIR (2-of-3)</div>
          <div>MERKLE O(LOG N)</div>
        </div>
      </aside>

      {/* Main content */}
      <main style={{ flex: 1, padding: '32px', overflowY: 'auto' }}>
        <Routes>
          <Route path="/"        element={<Dashboard />} />
          <Route path="/merkle"  element={<MerklePage />} />
          <Route path="/attacks" element={<AttackPage />} />
          <Route path="/shamir"  element={<ShamirPage />} />
          <Route path="/ledger"  element={<LedgerPage />} />
        </Routes>
      </main>
    </div>
  )
}