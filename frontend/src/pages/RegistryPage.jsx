import { useEffect, useState } from 'react'
import { Users, CheckCircle, XCircle, AlertTriangle, Clock, Shield, RefreshCw } from 'lucide-react'
import axios from 'axios'

import config from '../config.js'
const API = config.API

const STATUS_CONFIG = {
  VERIFIED:    { color: 'var(--accent-green)', badge: 'badge-green', icon: CheckCircle,    label: 'VERIFIED' },
  REJECTED:    { color: 'var(--accent-red)',   badge: 'badge-red',   icon: XCircle,        label: 'REJECTED' },
  COMPROMISED: { color: 'var(--accent-red)',   badge: 'badge-red',   icon: AlertTriangle,  label: 'COMPROMISED' },
  UNKNOWN:     { color: 'var(--accent-amber)', badge: 'badge-amber', icon: Clock,          label: 'UNKNOWN' },
}

export default function RegistryPage() {
  const [models,  setModels]  = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)

  const fetchModels = () => {
    setLoading(true)
    axios.get(`${API}/api/models`)
      .then(r => setModels(r.data))
      .catch(() => setModels([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchModels() }, [])

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--text-secondary)', paddingTop: '40px' }}>
      <div className="spinner" /> Loading model registry...
    </div>
  )

  return (
    <div style={{ animation: 'slideIn 0.3s ease' }}>
      {/* Header */}
      <div style={{ marginBottom: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
          <Users size={20} color="var(--accent-green)" />
          <h1 style={{ fontFamily: 'var(--font-mono)', fontSize: '18px', fontWeight: '700', letterSpacing: '0.08em' }}>
            MODEL REGISTRY
          </h1>
          <button
            className="btn"
            onClick={fetchModels}
            style={{ marginLeft: 'auto', padding: '6px 12px', fontSize: '10px' }}
          >
            <RefreshCw size={10} /> REFRESH
          </button>
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-dim)', letterSpacing: '0.08em' }}>
          Shared trust status derived from the hash-chained ledger — no separate database
        </div>
      </div>

      {models.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '48px' }}>
          <Shield size={32} color="var(--text-dim)" style={{ marginBottom: '16px' }} />
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', color: 'var(--text-secondary)' }}>
            No models registered yet.
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-dim)', marginTop: '8px' }}>
            Sign a model from the Dashboard to populate the registry.
          </div>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: selected ? '1fr 1fr' : '1fr', gap: '20px' }}>

          {/* Model table */}
          <div className="card">
            <div className="section-header">
              <span className="prefix">//</span>
              <h2>Registered Models</h2>
              <span className="badge badge-blue" style={{ marginLeft: 'auto', fontSize: '9px' }}>
                {models.length} MODEL{models.length !== 1 ? 'S' : ''}
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {models.map((model, i) => {
                const cfg = STATUS_CONFIG[model.latest_status] || STATUS_CONFIG.UNKNOWN
                const Icon = cfg.icon
                const isSelected = selected?.model_name === model.model_name

                return (
                  <div
                    key={model.model_name}
                    onClick={() => setSelected(isSelected ? null : model)}
                    style={{
                      padding:      '16px',
                      background:   isSelected ? `${cfg.color}08` : 'var(--bg-secondary)',
                      border:       `1px solid ${isSelected ? cfg.color + '60' : 'var(--border)'}`,
                      borderRadius: '4px',
                      cursor:       'pointer',
                      transition:   'all 0.2s',
                      animation:    `slideIn 0.3s ease ${i * 0.05}s both`,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <Icon size={16} color={cfg.color} />
                        <span style={{
                          fontFamily:    'var(--font-mono)',
                          fontSize:      '13px',
                          fontWeight:    '600',
                          color:         'var(--text-primary)',
                          letterSpacing: '0.04em',
                        }}>
                          {model.model_name}
                        </span>
                      </div>
                      <span className={`badge ${cfg.badge}`} style={{ fontSize: '9px', padding: '2px 8px' }}>
                        {cfg.label}
                      </span>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
                      <StatMini label="Verifications" value={model.total_verifications} color="var(--accent-green)" />
                      <StatMini label="Rejections"    value={model.total_rejections}    color="var(--accent-red)" />
                      <StatMini label="Attacks"       value={model.total_attacks}       color="var(--accent-amber)" />
                    </div>

                    <div style={{
                      display:    'flex',
                      justifyContent: 'space-between',
                      marginTop:  '10px',
                      paddingTop: '10px',
                      borderTop:  '1px solid var(--border)',
                      fontFamily: 'var(--font-mono)',
                      fontSize:   '9px',
                      color:      'var(--text-dim)',
                    }}>
                      <span>Last by: {model.last_checked_by}</span>
                      <span>{model.last_checked ? new Date(model.last_checked).toLocaleString() : 'Never'}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* History panel */}
          {selected && (
            <div className="card" style={{ animation: 'slideIn 0.3s ease' }}>
              <div className="section-header">
                <span className="prefix">//</span>
                <h2>Event History</h2>
              </div>

              <div style={{
                marginBottom: '16px',
                padding:      '12px',
                background:   'var(--bg-secondary)',
                borderRadius: '4px',
                fontFamily:   'var(--font-mono)',
              }}>
                <div style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '6px' }}>
                  {selected.model_name}
                </div>
                <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>
                  Artifact: {selected.artifact_id?.slice(0, 16)}...
                </div>
              </div>

              <div style={{
                display:     'flex',
                flexDirection: 'column',
                gap:          '0',
                maxHeight:    '500px',
                overflowY:    'auto',
              }}>
                {selected.history.slice().reverse().map((event, i) => (
                  <TimelineEvent key={i} event={event} index={i} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function StatMini({ label, value, color }) {
  return (
    <div>
      <div style={{ fontSize: '9px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', marginBottom: '4px' }}>
        {label.toUpperCase()}
      </div>
      <div style={{ fontSize: '18px', fontWeight: '700', fontFamily: 'var(--font-mono)', color }}>
        {value}
      </div>
    </div>
  )
}

function TimelineEvent({ event, index }) {
  const typeColors = {
    SIGNED:           'var(--accent-blue)',
    VERIFIED:         'var(--accent-green)',
    REJECTED:         'var(--accent-red)',
    ATTACK_SIMULATED: 'var(--accent-amber)',
  }
  const color = typeColors[event.event_type] || 'var(--text-dim)'

  return (
    <div style={{
      display:    'flex',
      gap:        '12px',
      padding:    '10px 0',
      borderLeft: '2px solid var(--border)',
      paddingLeft: '16px',
      position:   'relative',
      animation:  `slideIn 0.3s ease ${index * 0.05}s both`,
    }}>
      {/* Dot */}
      <div style={{
        position:     'absolute',
        left:         '-5px',
        top:          '14px',
        width:        '8px',
        height:       '8px',
        borderRadius: '50%',
        background:   color,
        boxShadow:    `0 0 6px ${color}`,
      }} />

      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
          <span style={{
            fontFamily:    'var(--font-mono)',
            fontSize:      '11px',
            fontWeight:    '600',
            color,
            letterSpacing: '0.06em',
          }}>
            {event.event_type}
          </span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-dim)' }}>
            {new Date(event.timestamp).toLocaleString()}
          </span>
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-secondary)' }}>
          by {event.user_id || 'system'}
          {event.details?.reason && ` — ${event.details.reason}`}
          {event.details?.attack_type && ` — ${event.details.attack_type}`}
        </div>
      </div>
    </div>
  )
}
