import { useState } from 'react'
import { useI18n } from '../i18n'
import { useAudit } from '../hooks/useAudit'
import { fmtInt } from '../lib/format'

// 帆型中文名（与后端 benchmark_ranges key 对应）
const SAIL_NAMES: Record<string, string> = {
  flettner: 'Flettner 转子帆',
  rigid_wing: '刚性翼帆',
  suction_wing: '吸力翼帆',
}

/** 审计正文：仅在用户首次展开后挂载，才发起 /api/audit 请求 */
function AuditContent() {
  const { t } = useI18n()
  const { data, error } = useAudit()

  if (error) return <div className="note">{t.audit_err(error)}</div>
  if (!data) return <p className="hint">{t.audit_loading}</p>

  const cov = data.coverage
  const g = data.guardrails
  const rep = data.reproducibility

  return (
    <>
      {/* 覆盖统计 */}
      <div className="audit-stats">
        <div className="audit-stat">
          <b>{fmtInt(cov.records)}</b>
          <span>{t.audit_records}</span>
        </div>
        <div className="audit-stat">
          <b>{cov.weather_years.join(' / ')}</b>
          <span>{t.audit_weather_years}</span>
        </div>
        <div className="audit-stat">
          <b>{`${cov.ships.length} × ${cov.routes.length} × ${cov.seasons.length}`}</b>
          <span>{t.audit_scope}</span>
        </div>
        <div className="audit-stat">
          <b>{fmtInt(cov.insight_records)}</b>
          <span>{t.audit_insights}</span>
        </div>
        <div className="audit-stat">
          <b>{fmtInt(rep.ci_tests)}</b>
          <span>{t.audit_tests}</span>
        </div>
        <div className="audit-stat">
          <b>{rep.bootstrap_seed ?? '—'}</b>
          <span>{t.audit_seed}</span>
        </div>
      </div>

      {/* 模型链路 */}
      <h3 className="audit-h">{t.audit_model_chain}</h3>
      <ol className="audit-chain">
        {data.model_chain.map((m, i) => (
          <li key={m.name}>
            <div className="audit-chain-head">
              <span className="audit-step">{i + 1}</span>
              <b>{m.name}</b>
              <span className="audit-src">{m.source}</span>
            </div>
            <p className="audit-role">{m.role}</p>
            <p className="audit-val">✓ {m.validation}</p>
          </li>
        ))}
      </ol>

      {/* 护栏与实船对照 */}
      <h3 className="audit-h">{t.audit_guardrails}</h3>
      <ul className="audit-list">
        {g.screening_cap_pct != null && (
          <li>
            {t.audit_cap}：{g.screening_cap_pct}%
          </li>
        )}
        <li>{g.compatibility_derating}</li>
        {Object.entries(g.benchmark_ranges).map(([sail, b]) => (
          <li key={sail}>
            {SAIL_NAMES[sail] ?? sail} · {t.bench_range} {b.lo}–{b.hi}%（{b.refs}）
          </li>
        ))}
      </ul>

      {/* 已知限制 */}
      <h3 className="audit-h">{t.audit_limitations}</h3>
      <ul className="audit-list audit-limits">
        {data.limitations.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ul>

      {/* 可复现性 */}
      <h3 className="audit-h">{t.audit_repro}</h3>
      <ul className="audit-list">
        <li>{rep.single_source_kpi}</li>
        <li>
          {rep.bootstrap_method} × {rep.bootstrap_samples ?? '—'} · seed{' '}
          {rep.bootstrap_seed ?? '—'}
        </li>
        <li>
          {rep.physics_grid} · {rep.insights_grid}
        </li>
        {rep.dockerized && <li>{t.audit_docker}</li>}
      </ul>
    </>
  )
}

/** 折叠式审计面板：默认收起，评委需要时点开；正文懒加载 */
export default function AuditPanel() {
  const { t } = useI18n()
  const [openedOnce, setOpenedOnce] = useState(false)

  return (
    <details
      className="card audit-card"
      onToggle={(e) => {
        if ((e.target as HTMLDetailsElement).open) setOpenedOnce(true)
      }}
    >
      <summary className="audit-summary">{t.audit_expand}</summary>
      {openedOnce && <AuditContent />}
    </details>
  )
}
