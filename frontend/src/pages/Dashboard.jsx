import { useEffect, useState } from 'react'
import { Shield, Activity, Lock, GitBranch, Key } from 'lucide-react'
import axios from 'axios'
import VerificationPipeline from '../components/VerificationPipeline.jsx'

import config from '../config.js'
const API = config.API

function StatCard({ label, value, sub, accent = 'green', icon: Icon }) {
  const colors = {
    green: 'var(--accent-green)',
    red:   'var(--accent-red)',
    amber: 'var(--accent-amber)',
    blue:  'var(--accent-blue)',
  }
  const color = colors[accent]

  return (
    <div className="card" style={{ position: 'relative', overflow: 'hidden' }}>
      <div style={{
        position: 'absolute', top: 0, left: 0,
        width: '3px', height: '100%',
        background: color,
      }} />
      <div style={{ paddingLeft: '12px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div style={{ fontSize: '10px', color: 'var(--text-dim)', letterSpacing: '0.12em', marginBottom: '8px', fontFamily: 'var(--font-mono)' }}>
              {label.toUpperCase()}
            </div>
            <div style={{ fontSize: '28px', fontWeight: '700', color, fontFamily: 'var(--font-mono)', lineHeight: 1 }}>
              {value}
            </div>
            {sub && (
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '6px', fontFamily: 'var(--font-mono)' }}>
                {sub}
              </div>
            )}
          </div>
          {Icon && <Icon size={20} color={color} style={{ opacity: 0.5 }} />}
        </div>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [status,     setStatus]     = useState(null)
  const [pipeline,   setPipeline]   = useState(null)
  const [loading,    setLoading]    = useState(true)
  const [verifying,  setVerifying]  = useState(false)

  useEffect(() => {
    axios.get(`${API}/api/status`)
      .then(r => setStatus(r.data))
      .catch(() => setStatus(null))
      .finally(() => setLoading(false))
  }, [])

  const runVerify = async () => {
    setVerifying(true)
    setPipeline(null)
    try {
      const r = await axios.get(`${API}/api/verify-detailed`)
      setPipeline(r.data)
    } catch(e) {
      setPipeline({
        overall_status: 'REJECTED',
        stages: [{
          stage: 'error', label: 'API Error',
          status: 'fail', time_ms: 0,
        }],
        total_time_ms: 0,
      })
    } finally {
      setVerifying(false)
    }
  }

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--text-secondary)', paddingTop: '40px' }}>
      <div className="spinner" /> Connecting to ModelGuard API...
    </div>
  )

  if (!status) return (
    <div className="card" style={{ borderColor: 'var(--accent-red)' }}>
      <div style={{ color: 'var(--accent-red)', fontFamily: 'var(--font-mono)', fontSize: '13px' }}>
        ✗ Cannot connect to API at {API} — is the backend running?
      </div>
    </div>
  )

  return (
    <div style={{ animation: 'slideIn 0.3s ease' }}>
      {/* Header */}
      <div style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
          <Shield size={20} color="var(--accent-green)" />
          <h1 style={{ fontFamily: 'var(--font-mono)', fontSize: '18px', fontWeight: '700', letterSpacing: '0.08em' }}>
            SYSTEM DASHBOARD
          </h1>
          <span className="badge badge-green" style={{ animation: 'pulse-green 2s infinite' }}>
            ● ONLINE
          </span>
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-dim)', letterSpacing: '0.08em' }}>
          Cryptographically Enforced AI Model Integrity System
        </div>
      </div>

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '28px' }}>
        <StatCard
          label="Model Status"
          value={status.model_trained ? 'READY' : 'MISSING'}
          sub="MNIST Classifier"
          accent={status.model_trained ? 'green' : 'red'}
          icon={Activity}
        />
        <StatCard
          label="Signature"
          value={status.model_signed ? 'SIGNED' : 'UNSIGNED'}
          sub="2-of-3 Threshold"
          accent={status.model_signed ? 'green' : 'amber'}
          icon={Lock}
        />
        <StatCard
          label="Ledger Entries"
          value={status.ledger_entries}
          sub={status.chain_valid ? 'Chain intact' : 'Chain broken!'}
          accent={status.chain_valid ? 'green' : 'red'}
          icon={GitBranch}
        />
        <StatCard
          label="Merkle Chunks"
          value="1648"
          sub="O(log N) verify"
          accent="blue"
          icon={Key}
        />
      </div>

      {/* Two column layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>

        {/* Verification pipeline */}
        <div className="card">
          <div className="section-header">
            <span className="prefix">//</span>
            <h2>Observable Verification Pipeline</h2>
          </div>

          <button
            className="btn btn-primary"
            onClick={runVerify}
            disabled={verifying}
            style={{ marginBottom: '20px', width: '100%', justifyContent: 'center' }}
          >
            {verifying ? <><div className="spinner" /> VERIFYING...</> : '▶ RUN VERIFICATION'}
          </button>

          <VerificationPipeline data={pipeline} />
        </div>

        {/* System info */}
        <div className="card">
          <div className="section-header">
            <span className="prefix">//</span>
            <h2>Cryptographic Stack</h2>
          </div>

          {[
            { label: 'Hash Algorithm',    value: 'BLAKE3 / SHA-256',     accent: 'green' },
            { label: 'Signature Scheme',  value: 'Ed25519 (256-bit)',     accent: 'green' },
            { label: 'Secret Sharing',    value: "Shamir's SSS (2-of-3)", accent: 'blue'  },
            { label: 'Tree Structure',    value: 'Binary Merkle Tree',    accent: 'blue'  },
            { label: 'Verification',      value: 'O(log N) per chunk',    accent: 'amber' },
            { label: 'Ledger',            value: 'Hash-chained entries',  accent: 'amber' },
            { label: 'Chain Status',      value: status.chain_reason,     accent: status.chain_valid ? 'green' : 'red' },
          ].map(({ label, value, accent }) => {
            const colors = { green: 'var(--accent-green)', blue: 'var(--accent-blue)', amber: 'var(--accent-amber)', red: 'var(--accent-red)' }
            return (
              <div key={label} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '10px 0', borderBottom: '1px solid var(--border)',
                fontFamily: 'var(--font-mono)', fontSize: '11px',
              }}>
                <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
                <span style={{ color: colors[accent] }}>{value}</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
