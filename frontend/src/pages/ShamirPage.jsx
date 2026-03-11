import { useState } from 'react'
import { Key, CheckCircle, Lock, Unlock } from 'lucide-react'
import axios from 'axios'

const API = 'http://localhost:8000'

export default function ShamirPage() {
  const [secret,  setSecret]  = useState('ModelGuard secret approval')
  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [activeShares, setActiveShares] = useState([0, 1])

  const runDemo = async () => {
    setLoading(true)
    try {
      const r = await axios.post(`${API}/api/shamir-demo`, { secret_message: secret })
      setResult(r.data)
    } catch(e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const toggleShare = (i) => {
    setActiveShares(prev =>
      prev.includes(i) ? prev.filter(x => x !== i) : [...prev, i]
    )
  }

  const canReconstruct = activeShares.length >= 2

  const SIGNERS = [
    { id: 'alice',   role: 'ML Team',         color: 'var(--accent-green)' },
    { id: 'bob',     role: 'Security Team',    color: 'var(--accent-blue)'  },
    { id: 'charlie', role: 'Compliance Team',  color: 'var(--accent-amber)' },
  ]

  return (
    <div style={{ animation: 'slideIn 0.3s ease' }}>
      {/* Header */}
      <div style={{ marginBottom: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
          <Key size={20} color="var(--accent-blue)" />
          <h1 style={{ fontFamily: 'var(--font-mono)', fontSize: '18px', fontWeight: '700', letterSpacing: '0.08em' }}>
            SHAMIR'S SECRET SHARING
          </h1>
          <span className="badge badge-blue">2-OF-3</span>
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-dim)' }}>
          Live demonstration of (k=2, n=3) threshold cryptography over GF(prime)
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>

        {/* Left: Math explanation */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

          {/* How it works */}
          <div className="card">
            <div className="section-header">
              <span className="prefix">//</span>
              <h2>How It Works</h2>
            </div>

            {[
              { step: '01', title: 'Encode Secret', desc: 'Secret s is set as f(0) of a degree-(k-1) polynomial over a 256-bit prime field' },
              { step: '02', title: 'Generate Shares', desc: 'f(x) = s + a₁x  (mod prime) — 3 shares: (1,f(1)), (2,f(2)), (3,f(3))' },
              { step: '03', title: 'Distribute',     desc: 'Each signer receives exactly one share. No single share reveals anything about s' },
              { step: '04', title: 'Reconstruct',    desc: 'Any 2 shares determine the line uniquely. Lagrange interpolation recovers f(0) = s' },
            ].map(({ step, title, desc }) => (
              <div key={step} style={{ display: 'flex', gap: '14px', marginBottom: '16px' }}>
                <div style={{
                  minWidth:     '28px',
                  height:       '28px',
                  background:   '#00aaff18',
                  border:       '1px solid #00aaff44',
                  borderRadius: '2px',
                  display:      'flex',
                  alignItems:   'center',
                  justifyContent: 'center',
                  fontFamily:   'var(--font-mono)',
                  fontSize:     '10px',
                  color:        'var(--accent-blue)',
                  fontWeight:   '700',
                }}>
                  {step}
                </div>
                <div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '3px' }}>
                    {title}
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
                    {desc}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Interactive threshold demo */}
          <div className="card">
            <div className="section-header">
              <span className="prefix">//</span>
              <h2>Interactive Threshold Demo</h2>
            </div>

            <div style={{ marginBottom: '14px', fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
              Select which signers participate — need at least 2:
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '16px' }}>
              {SIGNERS.map((signer, i) => {
                const isActive = activeShares.includes(i)
                return (
                  <div
                    key={signer.id}
                    onClick={() => toggleShare(i)}
                    style={{
                      display:      'flex',
                      alignItems:   'center',
                      justifyContent: 'space-between',
                      padding:      '12px 16px',
                      background:   isActive ? `${signer.color}12` : 'var(--bg-secondary)',
                      border:       `1px solid ${isActive ? signer.color + '60' : 'var(--border)'}`,
                      borderRadius: '3px',
                      cursor:       'pointer',
                      transition:   'all 0.2s',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      {isActive
                        ? <Unlock size={14} color={signer.color} />
                        : <Lock   size={14} color="var(--text-dim)" />
                      }
                      <div>
                        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: isActive ? signer.color : 'var(--text-secondary)', fontWeight: '600' }}>
                          {signer.id.toUpperCase()}
                        </div>
                        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-dim)' }}>
                          {signer.role}
                        </div>
                      </div>
                    </div>
                    <span className={`badge ${isActive ? 'badge-green' : ''}`} style={!isActive ? { color: 'var(--text-dim)', border: '1px solid var(--border)' } : {}}>
                      Share {i + 1}
                    </span>
                  </div>
                )
              })}
            </div>

            <div style={{
              padding:      '12px',
              background:   canReconstruct ? '#00ff8810' : '#ff335510',
              border:       `1px solid ${canReconstruct ? 'var(--accent-green)' : 'var(--accent-red)'}`,
              borderRadius: '3px',
              fontFamily:   'var(--font-mono)',
              fontSize:     '12px',
              color:        canReconstruct ? 'var(--accent-green)' : 'var(--accent-red)',
              textAlign:    'center',
            }}>
              {canReconstruct
                ? `✓ ${activeShares.length} shares selected — threshold met, reconstruction possible`
                : `✗ Only ${activeShares.length} share(s) — need at least 2 to reconstruct`
              }
            </div>
          </div>
        </div>

        {/* Right: Live demo */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="card">
            <div className="section-header">
              <span className="prefix">//</span>
              <h2>Live Computation</h2>
            </div>

            <div style={{ marginBottom: '12px', fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
              Enter a secret message to split:
            </div>

            <input
              value={secret}
              onChange={e => setSecret(e.target.value)}
              placeholder="Enter secret message..."
              style={{
                width:        '100%',
                padding:      '10px 14px',
                background:   'var(--bg-secondary)',
                border:       '1px solid var(--border)',
                borderRadius: '3px',
                color:        'var(--text-primary)',
                fontFamily:   'var(--font-mono)',
                fontSize:     '12px',
                marginBottom: '12px',
                outline:      'none',
              }}
              onFocus={e => e.target.style.borderColor = 'var(--accent-blue)'}
              onBlur={e  => e.target.style.borderColor = 'var(--border)'}
            />

            <button
              className="btn"
              onClick={runDemo}
              disabled={loading || !secret}
              style={{
                width: '100%', justifyContent: 'center',
                borderColor: 'var(--accent-blue)',
                color:       'var(--accent-blue)',
                background:  '#00aaff10',
              }}
            >
              {loading
                ? <><div className="spinner" /> COMPUTING...</>
                : <><Key size={12} /> RUN SHAMIR DEMO</>
              }
            </button>

            {result && (
              <div style={{ marginTop: '16px', animation: 'slideIn 0.3s ease' }}>

                {/* Steps */}
                {result.explanation && Object.entries(result.explanation).map(([k, v]) => (
                  <div key={k} style={{
                    display:      'flex',
                    gap:          '10px',
                    padding:      '8px 0',
                    borderBottom: '1px solid var(--border)',
                    fontFamily:   'var(--font-mono)',
                    fontSize:     '10px',
                  }}>
                    <span style={{ color: 'var(--accent-blue)', minWidth: '40px' }}>{k.toUpperCase()}</span>
                    <span style={{ color: 'var(--text-secondary)' }}>{v}</span>
                  </div>
                ))}

                {/* Shares */}
                <div style={{ marginTop: '14px', marginBottom: '10px', fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-secondary)' }}>
                  Generated shares:
                </div>

                {result.shares?.map(([x, y], i) => (
                  <div key={i} style={{
                    display:      'flex',
                    alignItems:   'center',
                    gap:          '10px',
                    padding:      '8px 12px',
                    background:   'var(--bg-secondary)',
                    border:       '1px solid var(--border)',
                    borderRadius: '3px',
                    marginBottom: '6px',
                    fontFamily:   'var(--font-mono)',
                    fontSize:     '11px',
                  }}>
                    <span style={{ color: SIGNERS[i]?.color || 'var(--accent-green)', minWidth: '60px', fontWeight: '600' }}>
                      {SIGNERS[i]?.id?.toUpperCase()}
                    </span>
                    <span style={{ color: 'var(--text-dim)' }}>share({x}) =</span>
                    <span style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{y}</span>
                  </div>
                ))}

                {/* Reconstruction results */}
                <div style={{ marginTop: '14px', marginBottom: '8px', fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-secondary)' }}>
                  Reconstruction verification:
                </div>

                {result.reconstruction && Object.entries(result.reconstruction).map(([combo, ok]) => (
                  <div key={combo} style={{
                    display:    'flex',
                    alignItems: 'center',
                    gap:        '10px',
                    padding:    '6px 0',
                    fontFamily: 'var(--font-mono)',
                    fontSize:   '11px',
                    borderBottom: '1px solid var(--border)',
                  }}>
                    {ok
                      ? <CheckCircle size={12} color="var(--accent-green)" />
                      : <XCircle    size={12} color="var(--accent-red)" />
                    }
                    <span style={{ color: 'var(--text-secondary)' }}>
                      {combo.replace('shares_', 'Shares ').replace('_', ' + ')}
                    </span>
                    <span style={{ color: ok ? 'var(--accent-green)' : 'var(--accent-red)', marginLeft: 'auto' }}>
                      {ok ? 'SECRET RECOVERED ✓' : 'FAILED ✗'}
                    </span>
                  </div>
                ))}

                <div style={{
                  marginTop:    '14px',
                  padding:      '12px',
                  background:   result.all_correct ? '#00ff8810' : '#ff335510',
                  border:       `1px solid ${result.all_correct ? 'var(--accent-green)' : 'var(--accent-red)'}`,
                  borderRadius: '3px',
                  fontFamily:   'var(--font-mono)',
                  fontSize:     '12px',
                  color:        result.all_correct ? 'var(--accent-green)' : 'var(--accent-red)',
                  textAlign:    'center',
                }}>
                  {result.all_correct
                    ? '✓ All combinations reconstruct correctly — Shamir SSS verified'
                    : '✗ Reconstruction failed'}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}