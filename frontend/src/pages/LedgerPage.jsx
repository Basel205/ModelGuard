import { useEffect, useState } from 'react'
import { BookOpen, CheckCircle, XCircle, RefreshCw, Shield, Zap, AlertTriangle } from 'lucide-react'
import axios from 'axios'

import config from '../config.js'
const API = config.API

const EVENT_STYLES = {
  SIGNED:           { color: 'var(--accent-green)',  badge: 'badge-green', icon: Shield },
  VERIFIED:         { color: 'var(--accent-blue)',   badge: 'badge-blue',  icon: CheckCircle },
  REJECTED:         { color: 'var(--accent-red)',    badge: 'badge-red',   icon: XCircle },
  REVOKED:          { color: 'var(--accent-red)',    badge: 'badge-red',   icon: XCircle },
  ATTACK_SIMULATED: { color: 'var(--accent-amber)',  badge: 'badge-amber', icon: Zap },
}

function EntryCard({ entry, index }) {
  const [expanded, setExpanded] = useState(false)
  const style = EVENT_STYLES[entry.event_type] || EVENT_STYLES.VERIFIED
  const Icon  = style.icon

  return (
    <div
      className="card"
      style={{
        borderLeft:   `3px solid ${style.color}`,
        marginBottom: '8px',
        cursor:       'pointer',
        transition:   'all 0.2s',
        animation:    `slideIn 0.3s ease ${index * 0.05}s both`,
      }}
      onClick={() => setExpanded(!expanded)}
    >
      {/* Entry header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <span style={{
          fontFamily:  'var(--font-mono)',
          fontSize:    '10px',
          color:       'var(--text-dim)',
          minWidth:    '28px',
        }}>
          #{String(index + 1).padStart(3, '0')}
        </span>

        <Icon size={13} color={style.color} />

        <span className={`badge ${style.badge}`} style={{ fontSize: '10px' }}>
          {entry.event_type}
        </span>

        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--text-primary)', flex: 1 }}>
          {entry.model_name}
        </span>

        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-dim)' }}>
          {entry.timestamp}
        </span>

        <span style={{ color: 'var(--text-dim)', fontSize: '12px' }}>
          {expanded ? '▲' : '▼'}
        </span>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div style={{
          marginTop:  '14px',
          paddingTop: '14px',
          borderTop:  '1px solid var(--border)',
          animation:  'slideIn 0.2s ease',
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            {[
              { k: 'Entry ID',    v: entry.entry_id },
              { k: 'Artifact ID', v: entry.artifact_id },
              { k: 'Model Hash',  v: entry.model_hash?.slice(0, 32) + '...' },
              { k: 'Merkle Root', v: entry.merkle_root?.slice(0, 32) + '...' },
              { k: 'Signed By',   v: entry.signed_by?.join(', ') || '—' },
              { k: 'Prev Hash',   v: entry.prev_hash?.slice(0, 32) + '...' },
            ].map(({ k, v }) => (
              <div key={k} style={{ fontFamily: 'var(--font-mono)', fontSize: '10px' }}>
                <span style={{ color: 'var(--text-dim)', display: 'block', marginBottom: '2px' }}>{k}</span>
                <span style={{ color: 'var(--text-secondary)', wordBreak: 'break-all' }}>{v}</span>
              </div>
            ))}
          </div>

          {/* Entry hash */}
          <div style={{ marginTop: '12px', padding: '10px', background: 'var(--bg-secondary)', borderRadius: '3px' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-dim)', marginBottom: '4px' }}>
              ENTRY HASH (SHA-256)
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: style.color, wordBreak: 'break-all' }}>
              {entry.entry_hash}
            </div>
          </div>

          {entry.extra && Object.keys(entry.extra).length > 0 && (
            <div style={{ marginTop: '8px', padding: '10px', background: 'var(--bg-secondary)', borderRadius: '3px' }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-dim)', marginBottom: '4px' }}>
                EXTRA DATA
              </div>
              {Object.entries(entry.extra).map(([k, v]) => (
                <div key={k} style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-secondary)' }}>
                  {k}: {JSON.stringify(v)}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function LedgerPage() {
  const [data,     setData]     = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const fetchLedger = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true)
    try {
      const r = await axios.get(`${API}/api/ledger`)
      setData(r.data)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => { fetchLedger() }, [])

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--text-secondary)' }}>
      <div className="spinner" /> Loading ledger...
    </div>
  )

  const entries     = data?.entries || []
  const chainValid  = data?.chain_valid
  const eventCounts = entries.reduce((acc, e) => {
    acc[e.event_type] = (acc[e.event_type] || 0) + 1
    return acc
  }, {})

  return (
    <div style={{ animation: 'slideIn 0.3s ease' }}>
      {/* Header */}
      <div style={{ marginBottom: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
            <BookOpen size={20} color="var(--accent-amber)" />
            <h1 style={{ fontFamily: 'var(--font-mono)', fontSize: '18px', fontWeight: '700', letterSpacing: '0.08em' }}>
              TAMPER-EVIDENT LEDGER
            </h1>
            <span className={`badge ${chainValid ? 'badge-green' : 'badge-red'}`}>
              {chainValid ? '✓ CHAIN VALID' : '✗ CHAIN BROKEN'}
            </span>
          </div>
          <button
            className="btn"
            onClick={() => fetchLedger(true)}
            disabled={refreshing}
            style={{ gap: '6px' }}
          >
            <RefreshCw size={12} style={{ animation: refreshing ? 'spin 0.6s linear infinite' : 'none' }} />
            REFRESH
          </button>
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-dim)' }}>
          Hash-chained audit log — every entry linked to the previous via SHA-256
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '24px', flexWrap: 'wrap' }}>
        <div className="card" style={{ flex: 1, minWidth: '120px', textAlign: 'center' }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '24px', fontWeight: '700', color: 'var(--accent-green)' }}>
            {entries.length}
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-dim)', marginTop: '4px' }}>
            TOTAL ENTRIES
          </div>
        </div>

        {Object.entries(eventCounts).map(([type, count]) => {
          const style = EVENT_STYLES[type] || EVENT_STYLES.VERIFIED
          return (
            <div key={type} className="card" style={{ flex: 1, minWidth: '120px', textAlign: 'center' }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '24px', fontWeight: '700', color: style.color }}>
                {count}
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-dim)', marginTop: '4px' }}>
                {type}
              </div>
            </div>
          )
        })}
      </div>

      {/* Chain status */}
      <div style={{
        padding:      '14px 18px',
        background:   chainValid ? '#00ff8808' : '#ff335508',
        border:       `1px solid ${chainValid ? '#00ff8830' : '#ff335530'}`,
        borderRadius: '3px',
        marginBottom: '20px',
        display:      'flex',
        alignItems:   'center',
        gap:          '10px',
        fontFamily:   'var(--font-mono)',
        fontSize:     '12px',
      }}>
        {chainValid
          ? <CheckCircle  size={14} color="var(--accent-green)" />
          : <AlertTriangle size={14} color="var(--accent-red)" />
        }
        <span style={{ color: chainValid ? 'var(--accent-green)' : 'var(--accent-red)' }}>
          {data?.chain_reason}
        </span>
      </div>

      {/* Entries */}
      {entries.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
          No ledger entries yet — sign a model to create the first entry
        </div>
      ) : (
        <div>
          {[...entries].reverse().map((entry, i) => (
            <EntryCard key={entry.entry_id} entry={entry} index={i} />
          ))}
        </div>
      )}
    </div>
  )
}
