import { useState } from 'react'
import { Zap, Shield, AlertTriangle, CheckCircle, XCircle } from 'lucide-react'
import axios from 'axios'

const API = 'http://localhost:8000'

const ATTACKS = [
  {
    id:          'modify_weights',
    label:       'Modify Weights',
    description: 'Tamper with model weight values directly',
    detail:      'Simulates an attacker injecting malicious values into the model weights. ModelGuard detects this via hash mismatch and Merkle proof failure.',
    color:       'var(--accent-red)',
    icon:        '⚡',
  },
  {
    id:          'replace_model',
    label:       'Replace Model',
    description: 'Swap in a completely different model',
    detail:      'Simulates replacing the signed model with a freshly initialized random model. The Merkle root will not match.',
    color:       'var(--accent-red)',
    icon:        '🔄',
  },
  {
    id:          'unsigned',
    label:       'Unsigned Model',
    description: 'Attempt to load with no valid signatures',
    detail:      'Simulates an attacker trying to load a model with no cryptographic signatures. The policy engine blocks execution immediately.',
    color:       'var(--accent-amber)',
    icon:        '🔓',
  },
  {
    id:          'downgrade',
    label:       'Version Downgrade',
    description: 'Replay an old artifact with outdated version',
    detail:      'Simulates a downgrade attack by replaying an old signed artifact. Policy engine enforces minimum version requirement.',
    color:       'var(--accent-amber)',
    icon:        '⬇',
  },
]

function AttackCard({ attack, onRun, loading, result }) {
  const isLoading = loading === attack.id
  const hasResult = result?.attack === attack.id

  return (
    <div className="card" style={{
      borderColor: hasResult
        ? (result.detected ? 'var(--accent-green)' : 'var(--accent-red)')
        : 'var(--border)',
      transition: 'all 0.3s',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '20px' }}>{attack.icon}</span>
          <div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', fontWeight: '600', color: attack.color }}>
              {attack.label.toUpperCase()}
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-secondary)', marginTop: '2px' }}>
              {attack.description}
            </div>
          </div>
        </div>
        {hasResult && (
          <span className={`badge ${result.detected ? 'badge-green' : 'badge-red'}`}>
            {result.detected ? '✓ BLOCKED' : '✗ BYPASSED'}
          </span>
        )}
      </div>

      {/* Detail */}
      <div style={{
        padding:      '10px',
        background:   'var(--bg-secondary)',
        borderRadius: '3px',
        fontFamily:   'var(--font-mono)',
        fontSize:     '10px',
        color:        'var(--text-dim)',
        marginBottom: '14px',
        lineHeight:   '1.7',
      }}>
        {attack.detail}
      </div>

      {/* Run button */}
      <button
        className={`btn ${isLoading ? '' : 'btn-danger'}`}
        onClick={() => onRun(attack.id)}
        disabled={!!loading}
        style={{ width: '100%', justifyContent: 'center' }}
      >
        {isLoading
          ? <><div className="spinner" /> SIMULATING ATTACK...</>
          : <><Zap size={12} /> LAUNCH ATTACK</>
        }
      </button>

      {/* Result */}
      {hasResult && (
        <div style={{
          marginTop:    '14px',
          padding:      '14px',
          background:   result.detected ? '#00ff8808' : '#ff335508',
          border:       `1px solid ${result.detected ? '#00ff8830' : '#ff335530'}`,
          borderRadius: '3px',
          animation:    'slideIn 0.3s ease',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
            {result.detected
              ? <Shield      size={14} color="var(--accent-green)" />
              : <AlertTriangle size={14} color="var(--accent-red)" />
            }
            <span style={{
              fontFamily: 'var(--font-mono)', fontSize: '12px', fontWeight: '600',
              color: result.detected ? 'var(--accent-green)' : 'var(--accent-red)',
            }}>
              {result.detected ? 'ATTACK DETECTED & BLOCKED' : 'ATTACK NOT DETECTED'}
            </span>
          </div>

          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-secondary)', marginBottom: '10px' }}>
            {result.reason}
          </div>

          {/* Attack-specific details */}
          {result.dirty_chunks?.length > 0 && (
            <div style={{ fontSize: '10px', color: 'var(--accent-amber)', fontFamily: 'var(--font-mono)' }}>
              ⚠ Dirty chunks: [{result.dirty_chunks.slice(0, 8).join(', ')}{result.dirty_chunks.length > 8 ? '...' : ''}]
            </div>
          )}

          {result.corrupted_layers && (
            <div style={{ fontSize: '10px', color: 'var(--accent-amber)', fontFamily: 'var(--font-mono)' }}>
              ⚠ Corrupted layers: {result.corrupted_layers.join(', ')}
            </div>
          )}

          {result.policy_report && (
            <div style={{ marginTop: '8px' }}>
              {result.policy_report.details?.map((v, i) => (
                <div key={i} style={{
                  display: 'flex', gap: '8px', padding: '4px 0',
                  fontFamily: 'var(--font-mono)', fontSize: '10px',
                  borderBottom: '1px solid var(--border)',
                }}>
                  <XCircle size={10} color="var(--accent-red)" style={{ flexShrink: 0, marginTop: '2px' }} />
                  <span style={{ color: 'var(--text-secondary)' }}>
                    <span style={{ color: 'var(--accent-amber)' }}>[{v.rule}]</span> {v.reason}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Check results */}
          {(result.hash_valid !== undefined || result.merkle_valid !== undefined) && (
            <div style={{ marginTop: '10px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {result.hash_valid !== undefined && (
                <span className={`badge ${result.hash_valid ? 'badge-green' : 'badge-red'}`}>
                  Hash: {result.hash_valid ? 'OK' : 'FAIL'}
                </span>
              )}
              {result.merkle_valid !== undefined && (
                <span className={`badge ${result.merkle_valid ? 'badge-green' : 'badge-red'}`}>
                  Merkle: {result.merkle_valid ? 'OK' : 'FAIL'}
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function AttackPage() {
  const [loading, setLoading] = useState(null)
  const [results, setResults] = useState({})
  const [log,     setLog]     = useState([])

  const runAttack = async (attackId) => {
    setLoading(attackId)
    const timestamp = new Date().toLocaleTimeString()

    try {
      const r = await axios.post(`${API}/api/attack`, {
        attack_type: attackId,
        intensity:   1.0,
      })

      setResults(prev => ({ ...prev, [attackId]: r.data }))
      setLog(prev => [{
        time:     timestamp,
        attack:   attackId,
        detected: r.data.detected,
        reason:   r.data.reason,
      }, ...prev])

    } catch(e) {
      setResults(prev => ({ ...prev, [attackId]: { attack: attackId, detected: false, reason: 'API error' } }))
    } finally {
      setLoading(null)
    }
  }

  const allDetected = Object.values(results).every(r => r.detected)
  const anyRun      = Object.keys(results).length > 0

  return (
    <div style={{ animation: 'slideIn 0.3s ease' }}>
      {/* Header */}
      <div style={{ marginBottom: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
          <Zap size={20} color="var(--accent-red)" />
          <h1 style={{ fontFamily: 'var(--font-mono)', fontSize: '18px', fontWeight: '700', letterSpacing: '0.08em' }}>
            ATTACK SIMULATOR
          </h1>
          {anyRun && (
            <span className={`badge ${allDetected ? 'badge-green' : 'badge-red'}`}>
              {Object.keys(results).length} ATTACKS RUN
            </span>
          )}
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-dim)' }}>
          Simulate real-world attacks against a signed AI model — watch ModelGuard detect each one
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '24px' }}>
        {ATTACKS.map(attack => (
          <AttackCard
            key={attack.id}
            attack={attack}
            onRun={runAttack}
            loading={loading}
            result={results[attack.id]}
          />
        ))}
      </div>

      {/* Attack log */}
      {log.length > 0 && (
        <div className="card">
          <div className="section-header">
            <span className="prefix">//</span>
            <h2>Attack Log</h2>
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
            {log.map((entry, i) => (
              <div key={i} style={{
                display:      'flex',
                alignItems:   'center',
                gap:          '12px',
                padding:      '8px 0',
                borderBottom: '1px solid var(--border)',
                animation:    'slideIn 0.3s ease',
              }}>
                <span style={{ color: 'var(--text-dim)', minWidth: '70px' }}>{entry.time}</span>
                {entry.detected
                  ? <CheckCircle size={12} color="var(--accent-green)" />
                  : <XCircle     size={12} color="var(--accent-red)" />
                }
                <span style={{ color: 'var(--accent-amber)', minWidth: '130px' }}>{entry.attack}</span>
                <span style={{ color: entry.detected ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                  {entry.detected ? 'BLOCKED' : 'BYPASSED'}
                </span>
                <span style={{ color: 'var(--text-dim)', fontSize: '10px' }}>{entry.reason}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}