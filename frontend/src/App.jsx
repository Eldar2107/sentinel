import React, { useState, useEffect, useCallback } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Legend
} from 'recharts'
import {
  Shield, Activity, Clock, AlertTriangle, CheckCircle, XCircle,
  RefreshCw, TrendingUp, Database, Zap, Eye, FileText
} from 'lucide-react'

const API = '/api'

// ─── Rəng Yardımçıları ────────────────────────────────────────────────────────
const scoreColor = (s) => {
  if (s >= 85) return '#22c55e'
  if (s >= 65) return '#f59e0b'
  return '#ef4444'
}
const scoreGradient = (s) => {
  if (s >= 85) return 'from-green-500/20 to-green-500/5'
  if (s >= 65) return 'from-yellow-500/20 to-yellow-500/5'
  return 'from-red-500/20 to-red-500/5'
}
const scoreBadgeBg = (s) => {
  if (s >= 85) return 'bg-green-500/10 text-green-400 border-green-500/30'
  if (s >= 65) return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30'
  return 'bg-red-500/10 text-red-400 border-red-500/30'
}

// ─── Banka Adı qısaltma ───────────────────────────────────────────────────────
const BANK_SHORT = {
  bank_a: 'TBC',
  bank_b: 'BoG',
  bank_c: 'Liberty',
}
const BANK_FULL = {
  bank_a: 'TBC Bank',
  bank_b: 'Bank of Georgia',
  bank_c: 'Liberty Bank',
}

// ─── Skelet Loader ────────────────────────────────────────────────────────────
const Skeleton = ({ className = '' }) => (
  <div className={`animate-pulse bg-white/5 rounded-lg ${className}`} />
)

// ─── Skor Kart ────────────────────────────────────────────────────────────────
function ScoreCard({ bankId, data, onClick, selected }) {
  const score = data?.score?.total_score ?? 0
  const grade = data?.score?.grade ?? 'N/A'
  const uptime = data?.uptime_pct ?? 100
  const latency = data?.latency?.p95 ?? 0
  const name = BANK_FULL[bankId] || bankId

  return (
    <button
      onClick={() => onClick(bankId)}
      className={`relative w-full text-left rounded-2xl border p-6 transition-all duration-200 bg-gradient-to-br ${scoreGradient(score)}
        ${selected
          ? 'border-blue-500/60 shadow-lg shadow-blue-500/10 scale-[1.02]'
          : 'border-white/10 hover:border-white/20 hover:scale-[1.01]'}`}
    >
      <div className="flex items-start justify-between mb-4">
        <div>
          <p className="text-xs font-medium text-slate-400 uppercase tracking-widest mb-1">{BANK_SHORT[bankId]}</p>
          <h3 className="text-white font-semibold text-lg leading-tight">{name}</h3>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className="text-4xl font-black tabular-nums" style={{ color: scoreColor(score) }}>
            {score.toFixed(0)}
          </span>
          <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${scoreBadgeBg(score)}`}>
            Grade {grade}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 text-center">
        <div className="bg-black/20 rounded-xl p-2">
          <p className="text-slate-400 text-xs mb-1">Uptime</p>
          <p className={`font-bold text-sm ${uptime >= 99 ? 'text-green-400' : uptime >= 95 ? 'text-yellow-400' : 'text-red-400'}`}>
            {uptime.toFixed(1)}%
          </p>
        </div>
        <div className="bg-black/20 rounded-xl p-2">
          <p className="text-slate-400 text-xs mb-1">p95</p>
          <p className={`font-bold text-sm ${latency < 400 ? 'text-green-400' : latency < 800 ? 'text-yellow-400' : 'text-red-400'}`}>
            {latency ? `${latency.toFixed(0)}ms` : '—'}
          </p>
        </div>
        <div className="bg-black/20 rounded-xl p-2">
          <p className="text-slate-400 text-xs mb-1">Drift</p>
          <p className={`font-bold text-sm ${(data?.recent_drift?.length ?? 0) === 0 ? 'text-green-400' : 'text-yellow-400'}`}>
            {data?.recent_drift?.length ?? 0}
          </p>
        </div>
      </div>

      {/* Skor barı */}
      <div className="mt-4">
        <div className="w-full bg-black/30 rounded-full h-1.5">
          <div
            className="h-1.5 rounded-full transition-all duration-700"
            style={{ width: `${score}%`, backgroundColor: scoreColor(score) }}
          />
        </div>
      </div>
    </button>
  )
}

// ─── Uyğunluq Matrisi ─────────────────────────────────────────────────────────
function ComplianceMatrix({ results }) {
  const categories = ['accounts', 'balances', 'transactions', 'payments', 'consent']
  const banks = ['bank_a', 'bank_b', 'bank_c']

  const getStatus = (bankId, category) => {
    if (!results || !results[bankId]) return null
    const r = results[bankId].find(x => x.category === category)
    if (!r) return null
    return {
      compliant: r.is_compliant,
      score: r.compliance_score,
      issues: r.compliance_issues?.length ?? 0,
    }
  }

  return (
    <div className="bg-slate-900 rounded-2xl border border-white/10 p-6">
      <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
        <CheckCircle size={16} className="text-blue-400" />
        Uyğunluq Matrisi
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className="text-left text-slate-400 font-medium pb-3 pr-4">Endpoint</th>
              {banks.map(b => (
                <th key={b} className="text-center text-slate-400 font-medium pb-3 px-3">
                  {BANK_SHORT[b]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {categories.map(cat => (
              <tr key={cat} className="border-t border-white/5">
                <td className="py-2.5 pr-4 text-slate-300 capitalize font-medium">{cat}</td>
                {banks.map(bankId => {
                  const s = getStatus(bankId, cat)
                  return (
                    <td key={bankId} className="py-2.5 px-3 text-center">
                      {s === null ? (
                        <span className="text-slate-600">—</span>
                      ) : s.compliant ? (
                        <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-green-500/10">
                          <CheckCircle size={14} className="text-green-400" />
                        </span>
                      ) : (
                        <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-red-500/10"
                              title={`${s.issues} problem`}>
                          <XCircle size={14} className="text-red-400" />
                        </span>
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ─── Drift Lenti ──────────────────────────────────────────────────────────────
function DriftFeed({ events }) {
  const severityStyle = {
    critical: 'bg-red-500/10 border-red-500/30 text-red-400',
    warning: 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400',
    info: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
  }

  if (!events || events.length === 0) {
    return (
      <div className="bg-slate-900 rounded-2xl border border-white/10 p-6">
        <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
          <Eye size={16} className="text-purple-400" />
          Drift Monitor
        </h3>
        <div className="flex items-center justify-center h-24 text-slate-500 text-sm">
          <CheckCircle size={16} className="mr-2 text-green-500" />
          Heç bir drift hadisəsi aşkar edilməyib
        </div>
      </div>
    )
  }

  return (
    <div className="bg-slate-900 rounded-2xl border border-white/10 p-6">
      <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
        <Eye size={16} className="text-purple-400" />
        Drift Monitor
        <span className="ml-auto bg-yellow-500/10 text-yellow-400 text-xs px-2 py-0.5 rounded-full border border-yellow-500/30">
          {events.length} hadisə
        </span>
      </h3>
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {events.map((e, i) => (
          <div key={i} className={`border rounded-xl p-3 ${severityStyle[e.severity] || severityStyle.info}`}>
            <div className="flex items-center justify-between mb-1">
              <span className="font-semibold text-xs uppercase tracking-wide">
                {BANK_SHORT[e.bank_id] || e.bank_id} — {e.drift_type?.replace(/_/g, ' ')}
              </span>
              <span className="text-xs opacity-60">
                {e.detected_at ? new Date(e.detected_at).toLocaleTimeString() : ''}
              </span>
            </div>
            <p className="text-xs opacity-80">{e.description || e.field_path}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Bank Detay Paneli ────────────────────────────────────────────────────────
function BankDetail({ bankId, data, latencyHistory }) {
  if (!data) return null
  const score = data.score || {}
  const breakdown = score.score_breakdown || {}

  const radarData = [
    { subject: 'Uyğunluq', value: breakdown.compliance || 0, fullMark: 100 },
    { subject: 'Etibarlılıq', value: breakdown.reliability || 0, fullMark: 100 },
    { subject: 'Gecikmə', value: breakdown.latency || 0, fullMark: 100 },
    { subject: 'Təhlükəsizlik', value: breakdown.security || 0, fullMark: 100 },
  ]

  const latencyChartData = (latencyHistory || []).slice(-20).map((m, i) => ({
    t: i,
    p50: Math.round(m.p50 || 0),
    p95: Math.round(m.p95 || 0),
    p99: Math.round(m.p99 || 0),
  }))

  const reasons = score.reasons || []

  return (
    <div className="space-y-4">
      {/* Radar Chart */}
      <div className="bg-slate-900 rounded-2xl border border-white/10 p-6">
        <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
          <TrendingUp size={16} className="text-cyan-400" />
          {BANK_FULL[bankId]} — Performans Profili
        </h3>
        <ResponsiveContainer width="100%" height={240}>
          <RadarChart data={radarData}>
            <PolarGrid stroke="#1e293b" />
            <PolarAngleAxis dataKey="subject" tick={{ fill: '#94a3b8', fontSize: 12 }} />
            <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 10 }} />
            <Radar name="Bank" dataKey="value" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.2} />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      {/* Latency Tarixi */}
      {latencyChartData.length > 0 && (
        <div className="bg-slate-900 rounded-2xl border border-white/10 p-6">
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Clock size={16} className="text-orange-400" />
            Gecikmə Tarixi (son 20 ölçüm)
          </h3>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={latencyChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="t" tick={{ fill: '#64748b', fontSize: 10 }} />
              <YAxis tick={{ fill: '#64748b', fontSize: 10 }} unit="ms" />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
                labelStyle={{ color: '#94a3b8' }}
              />
              <Line type="monotone" dataKey="p50" stroke="#22c55e" dot={false} strokeWidth={2} name="p50" />
              <Line type="monotone" dataKey="p95" stroke="#f59e0b" dot={false} strokeWidth={2} name="p95" />
              <Line type="monotone" dataKey="p99" stroke="#ef4444" dot={false} strokeWidth={2} name="p99" strokeDasharray="4 4" />
              <Legend wrapperStyle={{ fontSize: 12, color: '#94a3b8' }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Səbəb siyahısı */}
      {reasons.length > 0 && (
        <div className="bg-slate-900 rounded-2xl border border-white/10 p-6">
          <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
            <AlertTriangle size={16} className="text-yellow-400" />
            Bal Kəsinti Səbəbləri
          </h3>
          <div className="space-y-2">
            {reasons.map((r, i) => (
              <div key={i} className="flex items-start gap-3 text-sm">
                <span className={`mt-0.5 font-bold tabular-nums min-w-[48px] text-right ${r.impact < 0 ? 'text-red-400' : 'text-green-400'}`}>
                  {r.impact > 0 ? '+' : ''}{r.impact?.toFixed(1) || '0'}
                </span>
                <p className="text-slate-300 flex-1">{r.message}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Əsas App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [dashboard, setDashboard] = useState(null)
  const [latencyHistories, setLatencyHistories] = useState({})
  const [allDrifts, setAllDrifts] = useState([])
  const [latestResults, setLatestResults] = useState({})
  const [selectedBank, setSelectedBank] = useState('bank_a')
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [activeTab, setActiveTab] = useState('overview')
  const [report, setReport] = useState(null)

  const fetchAll = useCallback(async () => {
    try {
      const [dashRes, driftRes] = await Promise.all([
        fetch(`${API}/dashboard`),
        fetch(`${API}/drift?limit=20`),
      ])

      if (dashRes.ok) {
        const data = await dashRes.json()
        setDashboard(data)
      }
      if (driftRes.ok) {
        const data = await driftRes.json()
        setAllDrifts(data.events || [])
      }

      // Bank-specific məlumatlar
      for (const bankId of ['bank_a', 'bank_b', 'bank_c']) {
        const [latRes, resRes] = await Promise.all([
          fetch(`${API}/banks/${bankId}/latency?hours=12`),
          fetch(`${API}/banks/${bankId}/results?limit=10`),
        ])
        if (latRes.ok) {
          const d = await latRes.json()
          setLatencyHistories(prev => ({ ...prev, [bankId]: d.metrics || [] }))
        }
        if (resRes.ok) {
          const d = await resRes.json()
          setLatestResults(prev => ({ ...prev, [bankId]: d.results || [] }))
        }
      }

      setLastUpdated(new Date())
    } catch (e) {
      console.error('Fetch error:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()
    const interval = setInterval(fetchAll, 30000)
    return () => clearInterval(interval)
  }, [fetchAll])

  const runTests = async () => {
    setRunning(true)
    try {
      await fetch(`${API}/run-tests`, { method: 'POST' })
      setTimeout(fetchAll, 5000)
    } finally {
      setTimeout(() => setRunning(false), 5000)
    }
  }

  const fetchReport = async (bankId) => {
    const res = await fetch(`${API}/report/${bankId}`)
    if (res.ok) {
      const data = await res.json()
      setReport(data.report)
      setActiveTab('report')
    }
  }

  const banks = dashboard?.banks || {}

  // P95 bar chart data
  const p95Data = ['bank_a', 'bank_b', 'bank_c'].map(id => ({
    name: BANK_SHORT[id],
    p95: dashboard?.banks?.[id]?.latency?.p95?.toFixed(0) ?? 0,
    fill: scoreColor(dashboard?.banks?.[id]?.score?.total_score ?? 0),
  }))

  // Score comparison
  const scoreData = ['bank_a', 'bank_b', 'bank_c'].map(id => ({
    name: BANK_SHORT[id],
    Uyğunluq: banks[id]?.score?.score_breakdown?.compliance ?? 0,
    Etibarlılıq: banks[id]?.score?.score_breakdown?.reliability ?? 0,
    Gecikmə: banks[id]?.score?.score_breakdown?.latency ?? 0,
    Təhlükəsizlik: banks[id]?.score?.score_breakdown?.security ?? 0,
  }))

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-200">
      {/* Header */}
      <header className="border-b border-white/10 bg-black/40 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-blue-600 flex items-center justify-center">
              <Shield size={16} className="text-white" />
            </div>
            <div>
              <h1 className="text-white font-bold text-lg leading-none">Sentinel</h1>
              <p className="text-slate-500 text-xs">Georgia Open Banking Monitor</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {lastUpdated && (
              <span className="text-slate-500 text-xs hidden sm:block">
                Yeniləndi: {lastUpdated.toLocaleTimeString()}
              </span>
            )}
            <button
              onClick={runTests}
              disabled={running}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-xl transition-colors"
            >
              <RefreshCw size={14} className={running ? 'animate-spin' : ''} />
              {running ? 'Test gedir...' : 'Test Başlat'}
            </button>
          </div>
        </div>
      </header>

      {/* Tab Bar */}
      <div className="border-b border-white/10 bg-black/20">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex gap-1">
            {[
              { id: 'overview', label: 'Ümumi Baxış', icon: Activity },
              { id: 'detail', label: 'Bank Detay', icon: TrendingUp },
              { id: 'matrix', label: 'Uyğunluq', icon: CheckCircle },
              { id: 'drift', label: 'Drift', icon: Eye },
              { id: 'report', label: 'Hesabat', icon: FileText },
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <tab.icon size={14} />
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <main className="max-w-7xl mx-auto px-6 py-6">

        {/* ── Ümumi Baxış ── */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Skor kartları */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {loading ? (
                ['', '', ''].map((_, i) => <Skeleton key={i} className="h-48" />)
              ) : (
                ['bank_a', 'bank_b', 'bank_c'].map(id => (
                  <ScoreCard
                    key={id}
                    bankId={id}
                    data={banks[id]}
                    onClick={(bid) => { setSelectedBank(bid); setActiveTab('detail') }}
                    selected={selectedBank === id}
                  />
                ))
              )}
            </div>

            {/* p95 Latency Bar + Score Bar */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-slate-900 rounded-2xl border border-white/10 p-6">
                <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                  <Clock size={16} className="text-orange-400" />
                  p95 Gecikmə (ms)
                </h3>
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={p95Data}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                    <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} unit="ms" />
                    <Tooltip
                      contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
                      formatter={(v) => [`${v}ms`, 'p95']}
                    />
                    <Bar dataKey="p95" radius={[6, 6, 0, 0]}>
                      {p95Data.map((entry, i) => (
                        <rect key={i} fill={entry.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="bg-slate-900 rounded-2xl border border-white/10 p-6">
                <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                  <Database size={16} className="text-blue-400" />
                  Kateqoriya üzrə Skor
                </h3>
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={scoreData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                    <YAxis domain={[0, 100]} tick={{ fill: '#94a3b8', fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
                    />
                    <Bar dataKey="Uyğunluq" fill="#3b82f6" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="Etibarlılıq" fill="#22c55e" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="Gecikmə" fill="#f59e0b" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="Təhlükəsizlik" fill="#a855f7" radius={[3, 3, 0, 0]} />
                    <Legend wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Son drift xəbərdarlıqları */}
            {allDrifts.length > 0 && (
              <div className="bg-yellow-500/5 border border-yellow-500/20 rounded-2xl p-4">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle size={16} className="text-yellow-400" />
                  <span className="text-yellow-400 font-semibold text-sm">Drift Xəbərdarlıqları</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {allDrifts.slice(0, 4).map((d, i) => (
                    <span key={i} className="text-xs bg-yellow-500/10 text-yellow-300 px-3 py-1 rounded-full border border-yellow-500/20">
                      {BANK_SHORT[d.bank_id]}: {d.drift_type?.replace(/_/g, ' ')}
                    </span>
                  ))}
                  {allDrifts.length > 4 && (
                    <span className="text-xs text-slate-400">+{allDrifts.length - 4} daha</span>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Bank Detay ── */}
        {activeTab === 'detail' && (
          <div className="space-y-4">
            {/* Bank seçici */}
            <div className="flex gap-2">
              {['bank_a', 'bank_b', 'bank_c'].map(id => (
                <button
                  key={id}
                  onClick={() => setSelectedBank(id)}
                  className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
                    selectedBank === id
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-800 text-slate-400 hover:text-white'
                  }`}
                >
                  {BANK_FULL[id]}
                </button>
              ))}
              <button
                onClick={() => fetchReport(selectedBank)}
                className="ml-auto flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm px-4 py-2 rounded-xl transition-colors"
              >
                <FileText size={14} />
                Hesabat
              </button>
            </div>
            <BankDetail
              bankId={selectedBank}
              data={banks[selectedBank]}
              latencyHistory={latencyHistories[selectedBank]}
            />
          </div>
        )}

        {/* ── Uyğunluq Matrisi ── */}
        {activeTab === 'matrix' && (
          <div className="space-y-4">
            <ComplianceMatrix results={latestResults} />

            {/* Issue siyahısı */}
            <div className="bg-slate-900 rounded-2xl border border-white/10 p-6">
              <h3 className="text-white font-semibold mb-4">Son Uyğunsuzluqlar</h3>
              <div className="space-y-2">
                {['bank_a', 'bank_b', 'bank_c'].flatMap(bankId =>
                  (latestResults[bankId] || []).flatMap(r =>
                    (r.compliance_issues || []).slice(0, 2).map((issue, i) => ({
                      key: `${bankId}-${r.scenario}-${i}`,
                      bank: BANK_SHORT[bankId],
                      scenario: r.scenario,
                      ...issue,
                    }))
                  )
                ).slice(0, 10).map(item => (
                  <div key={item.key} className="flex items-start gap-3 text-sm p-3 bg-slate-800/50 rounded-xl">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                      item.severity === 'error' ? 'bg-red-500/10 text-red-400' : 'bg-yellow-500/10 text-yellow-400'
                    }`}>
                      {item.bank}
                    </span>
                    <div className="flex-1">
                      <p className="text-slate-300">{item.message}</p>
                      {item.field && <p className="text-slate-500 text-xs mt-0.5">{item.field}</p>}
                    </div>
                    <span className="text-slate-500 text-xs">{item.code}</span>
                  </div>
                ))}
                {!['bank_a', 'bank_b', 'bank_c'].some(id => (latestResults[id] || []).some(r => r.compliance_issues?.length > 0)) && (
                  <p className="text-slate-500 text-sm text-center py-4">Hələ məlumat yoxdur. "Test Başlat" düyməsini basın.</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── Drift Paneli ── */}
        {activeTab === 'drift' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <DriftFeed events={allDrifts} />

            <div className="bg-slate-900 rounded-2xl border border-white/10 p-6">
              <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                <Zap size={16} className="text-yellow-400" />
                Drift Statistikası
              </h3>
              {['bank_a', 'bank_b', 'bank_c'].map(id => {
                const bankDrifts = allDrifts.filter(d => d.bank_id === id)
                const critical = bankDrifts.filter(d => d.severity === 'critical').length
                return (
                  <div key={id} className="mb-4">
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-slate-300 text-sm">{BANK_FULL[id]}</span>
                      <span className="text-slate-400 text-xs">{bankDrifts.length} hadisə</span>
                    </div>
                    <div className="w-full bg-slate-800 rounded-full h-2">
                      <div
                        className="h-2 rounded-full bg-gradient-to-r from-yellow-500 to-orange-500"
                        style={{ width: `${Math.min(100, bankDrifts.length * 10)}%` }}
                      />
                    </div>
                    {critical > 0 && (
                      <p className="text-red-400 text-xs mt-1">{critical} kritik hadisə</p>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* ── Hesabat ── */}
        {activeTab === 'report' && (
          <div className="space-y-4">
            <div className="flex gap-2">
              {['bank_a', 'bank_b', 'bank_c'].map(id => (
                <button
                  key={id}
                  onClick={() => fetchReport(id)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm rounded-xl transition-colors"
                >
                  {BANK_SHORT[id]} Hesabatı
                </button>
              ))}
            </div>
            {report ? (
              <div className="bg-slate-900 rounded-2xl border border-white/10 p-8">
                <div className="prose prose-invert max-w-none text-slate-300 whitespace-pre-wrap font-mono text-sm leading-relaxed">
                  {report}
                </div>
              </div>
            ) : (
              <div className="bg-slate-900 rounded-2xl border border-white/10 p-12 text-center">
                <FileText size={40} className="mx-auto mb-3 text-slate-600" />
                <p className="text-slate-400">Hesabat görmək üçün bank seçin</p>
              </div>
            )}
          </div>
        )}

      </main>
    </div>
  )
}
