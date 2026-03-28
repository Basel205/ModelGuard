import { useState, useEffect } from 'react'
import { CheckCircle, XCircle, Clock, Shield, GitBranch, Key, FileCheck } from 'lucide-react'

const STAGE_ICONS = {
  hash_check:      Shield,
  merkle_check:    GitBranch,
  signature_check: Key,
  policy_check:    FileCheck,
}

const STAGE_COLORS = {
  pass: 'var(--accent-green)',
  fail: 'var(--accent-red)',
  pending: 'var(--text-dim)',
}

function StageRow({ stage, index, visible }) {
  const Icon = STAGE_ICONS[stage.stage] || Shield
  const color = STAGE_COLORS[stage.status]
  const isPassing = stage.status === 'pass'

  return (
    <div
      className="pipeline-stage"
      style={{
        opacity:    visible ? 1 : 0,
        transform:  visible ? 'translateX(0)' : 'translateX(-20px)',
        transition: `all 0.4s ease ${index * 0.15}s`,
      }}
    >
      {/* Connector line */}
      {index > 0 && (
        <div style={{
          position:   'absolute',
          top:        '-16px',
          left:       '19px',
          width:      '2px',
          height:     '16px',
          background: color,
          opacity:    0.4,
        }} />
      )}

      <div style={{
        display:      'flex',
        alignItems:   'flex-start',
        gap:          '16px',
        padding:      '16px',
        background:   isPassing ? '#00ff8808' : '#ff335508',
        border:       `1px solid ${isPassing ? '#00ff8830' : '#ff335530'}`,
        borderRadius: '4px',
        position:     'relative',
      }}>
        {/* Stage number & icon */}
        <div style={{
          display:        'flex',
          flexDirection:  'column',
          alignItems:     'center',
          gap:            '6px',
          minWidth:       '38px',
        }}>
          <div style={{
            width:          '38px',
            height:         '38px',
            borderRadius:   '50%',
            background:     `${color}18`,
            border:         `2px solid ${color}`,
            display:        'flex',
            alignItems:     'center',
            justifyContent: 'center',
            animation:      isPassing ? 'none' : 'pulse-red 2s infinite',
          }}>
            <Icon size={16} color={color} />
          </div>
          <span style={{
            fontSize:     '9px',
            fontFamily:   'var(--font-mono)',
            color:        'var(--text-dim)',
            letterSpacing:'0.08em',
          }}>
            STEP {index + 1}
          </span>
        </div>

        {/* Content */}
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{
                fontFamily:    'var(--font-mono)',
                fontSize:      '12px',
                fontWeight:    '600',
                letterSpacing: '0.06em',
                color:         'var(--text-primary)',
              }}>
                {stage.label}
              </span>
              {isPassing
                ? <CheckCircle size={14} color="var(--accent-green)" />
                : <XCircle    size={14} color="var(--accent-red)" />
              }
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Clock size={10} color="var(--text-dim)" />
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize:   '10px',
                color:      'var(--accent-amber)',
                fontWeight: '600',
              }}>
                {stage.time_ms}ms
              </span>
            </div>
          </div>

          {/* Stage-specific detail rows */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {/* Hash check details */}
            {stage.stage === 'hash_check' && (
              <>
                <DetailRow label="Expected" value={stage.expected} color={color} />
                <DetailRow label="Actual"   value={stage.actual}   color={color} />
              </>
            )}

            {/* Merkle check details */}
            {stage.stage === 'merkle_check' && (
              <>
                <DetailRow label="Expected Root" value={stage.expected_root} color={color} />
                <DetailRow label="Actual Root"   value={stage.actual_root}   color={color} />
                <DetailRow label="Total Chunks"  value={stage.total_chunks}  color="var(--accent-blue)" />
                {stage.dirty_chunks?.length > 0 && (
                  <DetailRow
                    label="Dirty Chunks"
                    value={`${stage.dirty_chunks.length} tampered`}
                    color="var(--accent-red)"
                  />
                )}
              </>
            )}

            {/* Signature check details */}
            {stage.stage === 'signature_check' && (
              <>
                <DetailRow label="Threshold" value={stage.threshold} color="var(--accent-blue)" />
                <DetailRow
                  label="Signers"
                  value={stage.valid_signers?.join(', ') || 'none'}
                  color={color}
                />
              </>
            )}

            {/* Policy check details */}
            {stage.stage === 'policy_check' && (
              <>
                <DetailRow label="Rules Checked" value={stage.rules_checked} color="var(--accent-blue)" />
                {stage.violations?.length > 0 && stage.violations.map((v, i) => (
                  <DetailRow key={i} label={v.rule} value={v.reason} color="var(--accent-red)" />
                ))}
                {stage.violations?.length === 0 && (
                  <DetailRow label="Violations" value="0 — all rules satisfied" color="var(--accent-green)" />
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function DetailRow({ label, value, color = 'var(--text-secondary)' }) {
  return (
    <div style={{
      display:        'flex',
      justifyContent: 'space-between',
      fontFamily:     'var(--font-mono)',
      fontSize:       '10px',
      padding:        '2px 0',
    }}>
      <span style={{ color: 'var(--text-dim)', minWidth: '110px' }}>{label}</span>
      <span style={{ color, textAlign: 'right', wordBreak: 'break-all' }}>{String(value)}</span>
    </div>
  )
}

export default function VerificationPipeline({ data }) {
  const [visibleCount, setVisibleCount] = useState(0)

  useEffect(() => {
    if (!data) return
    setVisibleCount(0)
    const total = data.stages.length + 1 // stages + verdict
    let i = 0
    const timer = setInterval(() => {
      i++
      setVisibleCount(i)
      if (i >= total) clearInterval(timer)
    }, 300)
    return () => clearInterval(timer)
  }, [data])

  if (!data) return null

  const isVerified = data.overall_status === 'VERIFIED'

  return (
    <div style={{ animation: 'slideIn 0.3s ease' }}>
      {/* Stages */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '20px' }}>
        {data.stages.map((stage, i) => (
          <StageRow
            key={stage.stage}
            stage={stage}
            index={i}
            visible={i < visibleCount}
          />
        ))}
      </div>

      {/* Final verdict */}
      <div
        style={{
          padding:      '16px 20px',
          background:   isVerified ? '#00ff8812' : '#ff335512',
          border:       `1px solid ${isVerified ? 'var(--accent-green)' : 'var(--accent-red)'}`,
          borderRadius: '4px',
          display:      'flex',
          justifyContent: 'space-between',
          alignItems:   'center',
          opacity:      visibleCount > data.stages.length ? 1 : 0,
          transform:    visibleCount > data.stages.length ? 'translateY(0)' : 'translateY(10px)',
          transition:   'all 0.4s ease',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {isVerified
            ? <CheckCircle size={18} color="var(--accent-green)" />
            : <XCircle    size={18} color="var(--accent-red)" />
          }
          <span style={{
            fontFamily:    'var(--font-mono)',
            fontSize:      '14px',
            fontWeight:    '700',
            letterSpacing: '0.1em',
            color:         isVerified ? 'var(--accent-green)' : 'var(--accent-red)',
          }}>
            {data.overall_status}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize:   '11px',
            color:      'var(--accent-amber)',
          }}>
            <Clock size={10} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} />
            {data.total_time_ms}ms total
          </span>
          {data.user_id && data.user_id !== 'anonymous' && (
            <span className="badge badge-blue" style={{ fontSize: '9px', padding: '2px 6px' }}>
              {data.user_id}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
