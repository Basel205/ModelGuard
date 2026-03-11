import { useEffect, useState } from 'react'
import { GitBranch, CheckCircle, XCircle, Search } from 'lucide-react'
import axios from 'axios'

import config from '../config.js'
const API = config.API

export default function MerklePage() {
  const [merkle,   setMerkle]   = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [chunkIdx, setChunkIdx] = useState('')
  const [result,   setResult]   = useState(null)
  const [checking, setChecking] = useState(false)
  const [highlighted, setHighlighted] = useState(null)

  useEffect(() => {
    axios.get(`${API}/api/merkle`)
      .then(r => setMerkle(r.data))
      .finally(() => setLoading(false))
  }, [])

  const verifyChunk = async () => {
    if (chunkIdx === '') return
    setChecking(true)
    setHighlighted(parseInt(chunkIdx))
    try {
      const r = await axios.get(`${API}/api/chunk-verify/${chunkIdx}`)
      setResult(r.data)
    } catch(e) {
      setResult({ valid: false, reason: 'Error' })
    } finally {
      setChecking(false)
    }
  }

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--text-secondary)' }}>
      <div className="spinner" /> Loading Merkle tree...
    </div>
  )

  const leaves     = merkle?.leaf_hashes || []
  const depth      = merkle?.depth || 0
  const chunkCount = merkle?.chunk_count || 0

  // Show first 64 leaves visually
  const displayLeaves = leaves.slice(0, 64)

  return (
    <div style={{ animation: 'slideIn 0.3s ease' }}>
      <div style={{ marginBottom: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
          <GitBranch size={20} color="var(--accent-green)" />
          <h1 style={{ fontFamily: 'var(--font-mono)', fontSize: '18px', fontWeight: '700', letterSpacing: '0.08em' }}>
            MERKLE TREE VISUALIZER
          </h1>
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-dim)' }}>
          O(log N) chunk verification — {chunkCount} chunks, depth {depth}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '20px' }}>

        {/* Tree visualization */}
        <div className="card">
          <div className="section-header">
            <span className="prefix">//</span>
            <h2>Merkle Root</h2>
          </div>

          {/* Root */}
          <div style={{ textAlign: 'center', marginBottom: '24px' }}>
            <div style={{
              display: 'inline-block',
              padding: '10px 20px',
              background: '#00ff8815',
              border: '1px solid var(--accent-green)',
              borderRadius: '3px',
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              color: 'var(--accent-green)',
              animation: 'pulse-green 3s infinite',
            }}>
              ROOT: {merkle?.root?.slice(0, 24)}...
            </div>
          </div>

          {/* Visual tree connector */}
          <div style={{ textAlign: 'center', color: 'var(--text-dim)', fontSize: '20px', marginBottom: '8px' }}>│</div>
          <div style={{ textAlign: 'center', color: 'var(--text-dim)', fontSize: '11px', fontFamily: 'var(--font-mono)', marginBottom: '16px' }}>
            ┌─────────┬─────────┐
          </div>

          {/* Depth info */}
          <div style={{ display: 'flex', justifyContent: 'center', gap: '16px', marginBottom: '24px' }}>
            {Array.from({ length: Math.min(depth, 4) }).map((_, i) => (
              <div key={i} style={{
                padding: '6px 14px',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border)',
                borderRadius: '3px',
                fontFamily: 'var(--font-mono)',
                fontSize: '10px',
                color: 'var(--text-secondary)',
              }}>
                LEVEL {i + 1}
              </div>
            ))}
            <div style={{
              padding: '6px 14px',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border)',
              borderRadius: '3px',
              fontFamily: 'var(--font-mono)',
              fontSize: '10px',
              color: 'var(--text-dim)',
            }}>
              ... {depth} levels total
            </div>
          </div>

          {/* Leaf grid */}
          <div className="section-header">
            <span className="prefix">//</span>
            <h2>Leaf Nodes (first 64 of {chunkCount})</h2>
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
            {displayLeaves.map((hash, i) => {
              const isHighlighted = highlighted === i
              const isValid       = result?.valid
              return (
                <div
                  key={i}
                  title={`Chunk ${i}: ${hash.slice(0, 16)}...`}
                  style={{
                    width:        '28px',
                    height:       '28px',
                    borderRadius: '2px',
                    background:   isHighlighted
                      ? (isValid ? 'var(--accent-green)' : 'var(--accent-red)')
                      : '#00ff8820',
                    border: `1px solid ${isHighlighted
                      ? (isValid ? 'var(--accent-green)' : 'var(--accent-red)')
                      : '#00ff8840'}`,
                    cursor:    'pointer',
                    transition: 'all 0.2s',
                    animation:  isHighlighted
                      ? (isValid ? 'pulse-green 1s infinite' : 'pulse-red 1s infinite')
                      : 'none',
                    display:    'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize:   '8px',
                    fontFamily: 'var(--font-mono)',
                    color:      isHighlighted ? '#000' : 'var(--accent-green)',
                    fontWeight: '700',
                  }}
                  onClick={() => { setChunkIdx(String(i)); setHighlighted(i) }}
                >
                  {i}
                </div>
              )
            })}
          </div>

          <div style={{ marginTop: '12px', fontSize: '10px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
            Click any leaf to select it for verification →
          </div>
        </div>

        {/* Chunk verifier */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="card">
            <div className="section-header">
              <span className="prefix">//</span>
              <h2>Chunk Verifier</h2>
            </div>

            <div style={{ marginBottom: '12px', fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
              Verify any single chunk via O(log N) Merkle proof
            </div>

            <input
              type="number"
              min="0"
              max={chunkCount - 1}
              value={chunkIdx}
              onChange={e => setChunkIdx(e.target.value)}
              placeholder={`0 – ${chunkCount - 1}`}
              style={{
                width:        '100%',
                padding:      '10px 14px',
                background:   'var(--bg-secondary)',
                border:       '1px solid var(--border)',
                borderRadius: '3px',
                color:        'var(--text-primary)',
                fontFamily:   'var(--font-mono)',
                fontSize:     '13px',
                marginBottom: '12px',
                outline:      'none',
              }}
              onFocus={e => e.target.style.borderColor = 'var(--accent-green)'}
              onBlur={e  => e.target.style.borderColor = 'var(--border)'}
            />

            <button
              className="btn btn-primary"
              onClick={verifyChunk}
              disabled={checking || chunkIdx === ''}
              style={{ width: '100%', justifyContent: 'center' }}
            >
              {checking
                ? <><div className="spinner" /> VERIFYING</>
                : <><Search size={12} /> VERIFY CHUNK</>
              }
            </button>

            {result && (
              <div style={{
                marginTop:    '16px',
                padding:      '14px',
                background:   result.valid ? '#00ff8810' : '#ff335510',
                border:       `1px solid ${result.valid ? 'var(--accent-green)' : 'var(--accent-red)'}`,
                borderRadius: '3px',
                animation:    'slideIn 0.3s ease',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
                  {result.valid
                    ? <CheckCircle size={14} color="var(--accent-green)" />
                    : <XCircle    size={14} color="var(--accent-red)" />
                  }
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: result.valid ? 'var(--accent-green)' : 'var(--accent-red)', fontWeight: '600' }}>
                    {result.valid ? 'CHUNK VALID' : 'CHUNK INVALID'}
                  </span>
                </div>

                {[
                  { k: 'Chunk Index',   v: result.chunk_index },
                  { k: 'Proof Steps',   v: `${result.proof_steps} hashes (O(log N))` },
                  { k: 'Total Chunks',  v: result.total_chunks },
                ].map(({ k, v }) => (
                  <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontFamily: 'var(--font-mono)', fontSize: '10px' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>{k}</span>
                    <span style={{ color: 'var(--text-primary)' }}>{v}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Complexity info */}
          <div className="card">
            <div className="section-header">
              <span className="prefix">//</span>
              <h2>Complexity</h2>
            </div>
            {[
              { label: 'Full verification',  value: 'O(N)',      color: 'var(--accent-amber)' },
              { label: 'Single chunk proof', value: 'O(log N)',  color: 'var(--accent-green)' },
              { label: 'Tamper detection',   value: 'O(N) scan', color: 'var(--accent-amber)' },
              { label: 'Proof size',         value: `${depth} hashes`, color: 'var(--accent-blue)' },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)', fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
                <span style={{ color, fontWeight: '600' }}>{value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
