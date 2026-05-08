<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'

// ── Formatters ────────────────────────────────────────────────────────────
const fmtDate = (val) => {
  if (!val) return '—'
  const s = String(val).split('T')[0].split(' ')[0]
  // Already DD/MM/YYYY or DD-MM-YYYY
  if (/^\d{2}[\/\-]\d{2}[\/\-]\d{4}$/.test(s)) return s.replace(/-/g, '/')
  // YYYY-MM-DD → DD/MM/YYYY
  const m = s.match(/^(\d{4})[\/\-](\d{2})[\/\-](\d{2})$/)
  if (m) return `${m[3]}/${m[2]}/${m[1]}`
  return s
}
const fmtDateTime = (val) => {
  if (!val) return '—'
  const d = new Date(val)
  return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}
const fmtCr = (n) => {
  if (!n && n !== 0) return '—'
  if (n >= 10000000) return `₹${(n / 10000000).toFixed(2)} Cr`
  if (n >= 100000)   return `₹${(n / 100000).toFixed(2)} L`
  if (n >= 1000)     return `₹${(n / 1000).toFixed(1)} K`
  return `₹${Math.round(n)}`
}

const fmtCrPdf = (n) => {
  if (!n && n !== 0) return '—'
  if (n >= 10000000) return `Rs.${(n / 10000000).toFixed(2)} Cr`
  if (n >= 100000)   return `Rs.${(n / 100000).toFixed(2)} L`
  if (n >= 1000)     return `Rs.${(n / 1000).toFixed(1)} K`
  return `Rs.${Math.round(n)}`
}

// ── State ─────────────────────────────────────────────────────────────────
const allWorks     = ref([])
const selectedWork = ref(null)
const isLoading    = ref(true)
const searchQuery  = ref('')
const itemFilter   = ref('')
const expandedId   = ref(null)
const sortKey      = ref('')
const sortDir      = ref('desc')
const activeTab    = ref('analytics')

// ── Load ──────────────────────────────────────────────────────────────────
const loadWorks = async () => {
  isLoading.value = true
  try {
    const res = await axios.get('/api/work-details/search/')
    allWorks.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    isLoading.value = false
  }
}
onMounted(loadWorks)

// ── Filtering ─────────────────────────────────────────────────────────────
const filteredWorks = computed(() => {
  if (!searchQuery.value.trim()) return allWorks.value
  const q = searchQuery.value.toLowerCase()
  return allWorks.value.filter(w =>
    (w.loa_number      && w.loa_number.toLowerCase().includes(q)) ||
    (w.contractor_name && w.contractor_name.toLowerCase().includes(q)) ||
    (w.tender_number   && w.tender_number.toLowerCase().includes(q)) ||
    (w.consignee       && w.consignee.toLowerCase().includes(q))
  )
})

const filteredItems = computed(() => {
  if (!selectedWork.value) return []
  if (!itemFilter.value.trim()) return selectedWork.value.items
  const q = itemFilter.value.toLowerCase()
  return selectedWork.value.items.filter(i =>
    (i.schedule  && i.schedule.toLowerCase().includes(q)) ||
    (i.item_desc && i.item_desc.toLowerCase().includes(q))
  )
})

// ── Progress ──────────────────────────────────────────────────────────────
const progressPct = (item) => {
  const req  = item.qty || 0
  if (!req) return 0
  const sch  = String(item.schedule || '').toUpperCase().trim()
  const done = sch.startsWith('B') ? (item.executed_quantity || 0) : (item.supplied_quantity || 0)
  return Math.min(Math.round((done / req) * 100), 999)
}

// ── Sorting ───────────────────────────────────────────────────────────────
const toggleSort = (key) => {
  if (sortKey.value === key) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  else { sortKey.value = key; sortDir.value = 'desc' }
}
const sortIcon = (key) => {
  if (sortKey.value !== key) return 'i-carbon-arrows-vertical'
  return sortDir.value === 'asc' ? 'i-carbon-arrow-up' : 'i-carbon-arrow-down'
}
const sortedItems = computed(() => {
  if (!sortKey.value) return filteredItems.value
  return [...filteredItems.value].sort((a, b) => {
    let av, bv
    if      (sortKey.value === 'qty')       { av = a.qty || 0;               bv = b.qty || 0 }
    else if (sortKey.value === 'submitted') { av = a.supplied_quantity || 0; bv = b.supplied_quantity || 0 }
    else if (sortKey.value === 'progress')  { av = progressPct(a);           bv = progressPct(b) }
    else if (sortKey.value === 'entries')   { av = (a.entries||[]).length;   bv = (b.entries||[]).length }
    return sortDir.value === 'asc' ? av - bv : bv - av
  })
})

const selectWork = (work) => {
  itemFilter.value   = ''
  expandedId.value   = null
  sortKey.value      = ''
  activeTab.value    = 'analytics'
  selectedWork.value = work
}

const toggleExpand = (itemId) => {
  expandedId.value = expandedId.value === itemId ? null : itemId
}

// ── Analytics computation ─────────────────────────────────────────────────
const analytics = computed(() => {
  if (!selectedWork.value) return null
  const items = selectedWork.value.items

  let contractTotal = 0, earnedTotal = 0
  let schAContract = 0, schAEarned = 0, schACount = 0
  let schBContract = 0, schBEarned = 0, schBCount = 0
  const statusA = { Completed: 0, 'In Progress': 0, 'Not Started': 0 }
  const statusB = { Completed: 0, 'In Progress': 0, 'Not Started': 0 }
  const brandMap   = {}
  const unitMap    = {}
  const challanMap = {}
  const mbByMonth  = {}

  for (const item of items) {
    const sch      = String(item.schedule || '').toUpperCase().trim()
    const isA      = sch.startsWith('A')
    const isB      = sch.startsWith('B')
    const contract = item.total_amount || 0
    const qty      = item.qty || 1
    const done     = isB ? (item.executed_quantity || 0) : (item.supplied_quantity || 0)
    const pct      = Math.min(done / qty, 1)
    const earned   = contract * pct

    contractTotal += contract
    earnedTotal   += earned
    if (isA) { schAContract += contract; schAEarned += earned; schACount++ }
    if (isB) { schBContract += contract; schBEarned += earned; schBCount++ }

    const sg = isA ? statusA : isB ? statusB : null
    if (sg) {
      if (pct >= 0.99) sg.Completed++
      else if (pct > 0) sg['In Progress']++
      else sg['Not Started']++
    }

    const agencyRaw = (item.inspection_agency || '').trim()
    const agencyKey = agencyRaw.toLowerCase() || 'unspecified'
    const agencyLabel = agencyRaw ? agencyRaw.charAt(0).toUpperCase() + agencyRaw.slice(1) : 'Unspecified'
    if (!brandMap[agencyKey]) brandMap[agencyKey] = { label: agencyLabel, contract: 0, earned: 0 }
    brandMap[agencyKey].contract += contract
    brandMap[agencyKey].earned   += earned

    const unit = (item.unit || 'Other').trim() || 'Other'
    unitMap[unit] = (unitMap[unit] || 0) + contract

    for (const e of (item.entries || [])) {
      if (e.entry_type === 'execution') continue
      const dateStr = e.date_of_receipt || (e.submitted_at ? String(e.submitted_at).substring(0, 10) : null)
      if (dateStr) {
        const month = String(dateStr).substring(0, 7)
        challanMap[month] = (challanMap[month] || 0) + 1
      }
    }
  }

  // MB Billing Velocity — only from uploaded MB records
  for (const mb of (selectedWork.value.mb_billing || [])) {
    if (!mb.date) continue
    const month = mb.date.substring(0, 7)
    mbByMonth[month] = (mbByMonth[month] || 0) + (mb.amount || 0)
  }

  const top10 = [...items]
    .filter(i => (i.total_amount || 0) > 0)
    .sort((a, b) => (b.total_amount || 0) - (a.total_amount || 0))
    .slice(0, 10)
    .map(i => {
      const sch  = String(i.schedule || '').toUpperCase()
      const isB  = sch.startsWith('B')
      const qty  = i.qty || 1
      const done = isB ? (i.executed_quantity || 0) : (i.supplied_quantity || 0)
      const pct  = Math.min(done / qty, 1)
      const earned = (i.total_amount || 0) * pct
      const desc = String(i.item_desc || 'Item')
      return {
        desc:    desc.length > 48 ? desc.substring(0, 48) + '…' : desc,
        contract: i.total_amount || 0,
        earned,
        pending: (i.total_amount || 0) - earned,
        sch:     i.schedule || '',
      }
    })

  const brands = Object.entries(brandMap)
    .filter(([k]) => k !== 'unspecified')
    .sort((a, b) => b[1].contract - a[1].contract)
    .slice(0, 12)

  const challanMonths = Object.keys(challanMap).sort()
  const challanCounts = challanMonths.map(m => challanMap[m])

  const earnedMonths = Object.keys(mbByMonth).sort()
  let cumulative = 0
  const cumulativeEarned = earnedMonths.map(m => {
    cumulative += mbByMonth[m]
    return parseFloat((cumulative / 100000).toFixed(2))
  })

  const schAPct = schAContract > 0 ? schAEarned / schAContract * 100 : 0
  const schBPct = schBContract > 0 ? schBEarned / schBContract * 100 : 0
  const overallPct = contractTotal > 0 ? earnedTotal / contractTotal * 100 : 0

  // Insights
  const insights = []
  if (schAPct > schBPct + 30 && schBCount > 0)
    insights.push({ type: 'warn', text: `Supply (${schAPct.toFixed(1)}%) is significantly ahead of execution (${schBPct.toFixed(1)}%). Idle inventory may be sitting on site.` })
  if (schACount > 0 && statusA['Not Started'] > schACount * 0.4)
    insights.push({ type: 'warn', text: `${statusA['Not Started']} of ${schACount} Schedule A items (${Math.round(statusA['Not Started'] / schACount * 100)}%) have zero supply recorded.` })
  if (schBCount > 0 && statusB['Not Started'] > schBCount * 0.5)
    insights.push({ type: 'warn', text: `${statusB['Not Started']} of ${schBCount} Schedule B items have no execution recorded yet.` })

  const topBrand = brands[0]
  if (topBrand && contractTotal > 0 && topBrand[1].contract / contractTotal > 0.5)
    insights.push({ type: 'info', text: `Single-agency concentration: "${topBrand[1].label}" accounts for ${((topBrand[1].contract / contractTotal) * 100).toFixed(0)}% of total contract value.` })

  const noProgressHigh = items.filter(i => {
    const sch  = String(i.schedule || '').toUpperCase()
    const done = sch.startsWith('B') ? (i.executed_quantity || 0) : (i.supplied_quantity || 0)
    return done === 0 && (i.total_amount || 0) > 100000
  }).length
  if (noProgressHigh > 0)
    insights.push({ type: 'warn', text: `${noProgressHigh} high-value item${noProgressHigh > 1 ? 's' : ''} (> ₹1L each) with zero progress — likely driving most of the pending value.` })

  if (overallPct > 80)
    insights.push({ type: 'good', text: `Overall financial progress is strong at ${overallPct.toFixed(1)}%. Work is nearing completion.` })
  else if (overallPct < 20 && contractTotal > 0)
    insights.push({ type: 'warn', text: `Overall financial progress is only ${overallPct.toFixed(1)}%. Significant ramp-up required.` })

  if (challanMonths.length > 2) {
    const latestMonth  = challanMonths[challanMonths.length - 1]
    const latestCount  = challanMap[latestMonth]
    const avgCount     = challanCounts.reduce((s, c) => s + c, 0) / challanCounts.length
    if (latestCount < avgCount * 0.5)
      insights.push({ type: 'warn', text: `Challan activity in ${latestMonth} (${latestCount} entries) is well below the monthly average (${avgCount.toFixed(1)}). Supply momentum may be slowing.` })
  }

  if (insights.length === 0)
    insights.push({ type: 'info', text: `Work is progressing. ${overallPct.toFixed(1)}% of contract value earned across ${items.length} items.` })

  return {
    contractTotal, earnedTotal, pendingTotal: contractTotal - earnedTotal,
    schAContract, schAEarned, schACount,
    schBContract, schBEarned, schBCount,
    schAPct, schBPct, overallPct,
    statusA, statusB,
    top10, brands,
    unitMap,
    challanMonths, challanCounts,
    earnedMonths, cumulativeEarned,
    insights,
    totalEntries: items.reduce((s, i) => s + (i.entries || []).length, 0),
  }
})

// ── ECharts management ────────────────────────────────────────────────────
const chartInstances = {}

const TEAL  = '#1D5F5E'
const AMBER = '#C17841'
const PALETTE = [TEAL, AMBER, '#8b5cf6', '#10b981', '#f59e0b', '#6366f1', '#ec4899', '#14b8a6', '#f97316']

const initOneChart = (id, option) => {
  const el = document.getElementById(id)
  if (!el) return
  let chart = chartInstances[id]
  if (!chart) {
    chart = echarts.init(el, null, { renderer: 'canvas' })
    chartInstances[id] = chart
  }
  chart.clear()
  chart.setOption(option)
}

const destroyCharts = () => {
  for (const [id, c] of Object.entries(chartInstances)) {
    try { c.dispose() } catch {}
    delete chartInstances[id]
  }
}

const handleResize = () => Object.values(chartInstances).forEach(c => { try { c.resize() } catch {} })

const L = n => parseFloat((n / 100000).toFixed(2))

const initCharts = async () => {
  if (!analytics.value || activeTab.value !== 'analytics') return
  await nextTick()
  await new Promise(r => requestAnimationFrame(r))
  const a = analytics.value

  // 1. Twin donut gauges
  initOneChart('chart-gauges', {
    tooltip: { trigger: 'item', formatter: p => `${p.seriesName} — ${p.name}: ${p.value.toFixed(1)}%` },
    series: [
      {
        name: 'Supply', type: 'pie',
        radius: ['52%', '78%'], center: ['25%', '52%'], startAngle: 90,
        data: [
          { value: Math.max(a.schAPct, 0), name: 'Earned', itemStyle: { color: TEAL } },
          { value: Math.max(100 - a.schAPct, 0), name: 'Pending', itemStyle: { color: '#D4E4E2' } },
        ],
        label: { show: true, position: 'center', formatter: () => `${a.schAPct.toFixed(0)}%`, fontSize: 20, fontWeight: 700, color: TEAL },
        emphasis: { label: { show: true } },
      },
      {
        name: 'Execution', type: 'pie',
        radius: ['52%', '78%'], center: ['75%', '52%'], startAngle: 90,
        data: [
          { value: Math.max(a.schBPct, 0), name: 'Earned', itemStyle: { color: AMBER } },
          { value: Math.max(100 - a.schBPct, 0), name: 'Pending', itemStyle: { color: '#F2DFCC' } },
        ],
        label: { show: true, position: 'center', formatter: () => `${a.schBPct.toFixed(0)}%`, fontSize: 20, fontWeight: 700, color: AMBER },
        emphasis: { label: { show: true } },
      },
    ],
    graphic: [
      { type: 'text', left: '12%', bottom: 8, style: { text: 'Schedule A · Supply',  fill: '#6b7280', fontSize: 10, fontWeight: 600 } },
      { type: 'text', left: '60%', bottom: 8, style: { text: 'Schedule B · Execution', fill: '#6b7280', fontSize: 10, fontWeight: 600 } },
    ],
  })

  // 2. Financial progress — grouped bar (Earned vs Pending)
  initOneChart('chart-waterfall', {
    tooltip: {
      trigger: 'axis', axisPointer: { type: 'shadow' },
      formatter: params => params.map(p => `${p.seriesName}: ₹${p.value} L`).join('<br/>'),
    },
    legend: { bottom: 0, textStyle: { fontSize: 10 }, itemWidth: 10, itemHeight: 10 },
    grid: { top: 12, bottom: 56, left: 52, right: 8 },
    xAxis: { type: 'category', data: ['Total', 'Sch A', 'Sch B'], axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', axisLabel: { formatter: v => `₹${v}L`, fontSize: 9 }, splitLine: { lineStyle: { type: 'dashed', color: '#f3f4f6' } } },
    series: [
      {
        name: 'Earned', type: 'bar', barMaxWidth: 36, itemStyle: { color: TEAL, borderRadius: [3, 3, 0, 0] },
        data: [L(a.earnedTotal), L(a.schAEarned), L(a.schBEarned)],
        label: { show: true, position: 'top', fontSize: 9, formatter: p => `₹${p.value}L` },
      },
      {
        name: 'Pending', type: 'bar', barMaxWidth: 36, itemStyle: { color: '#fca5a5', borderRadius: [3, 3, 0, 0] },
        data: [L(a.pendingTotal), L(a.schAContract - a.schAEarned), L(a.schBContract - a.schBEarned)],
        label: { show: true, position: 'top', fontSize: 9, formatter: p => `₹${p.value}L` },
      },
    ],
  })

  // 3. Item status stacked bar
  initOneChart('chart-status', {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { bottom: 0, textStyle: { fontSize: 10 }, itemWidth: 10, itemHeight: 10 },
    grid: { top: 10, bottom: 56, left: 36, right: 8 },
    xAxis: { type: 'category', data: ['Sch A', 'Sch B'], axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', name: 'Items', nameTextStyle: { fontSize: 9 }, axisLabel: { fontSize: 9 }, splitLine: { lineStyle: { type: 'dashed', color: '#f3f4f6' } } },
    series: [
      { name: 'Completed',   type: 'bar', stack: 'total', itemStyle: { color: TEAL  }, data: [a.statusA.Completed,     a.statusB.Completed]     },
      { name: 'In Progress', type: 'bar', stack: 'total', itemStyle: { color: AMBER }, data: [a.statusA['In Progress'], a.statusB['In Progress']] },
      { name: 'Not Started', type: 'bar', stack: 'total', itemStyle: { color: '#e5e7eb' }, data: [a.statusA['Not Started'], a.statusB['Not Started']] },
    ],
  })

  // 4. Top 10 items — horizontal stacked bar
  const top10Rev = [...a.top10].reverse()
  initOneChart('chart-top10', {
    tooltip: {
      trigger: 'axis', axisPointer: { type: 'shadow' },
      formatter: params => {
        const e = params.find(p => p.seriesName === 'Earned')
        const p = params.find(p => p.seriesName === 'Pending')
        return `${params[0]?.name}<br/>Earned: ₹${e?.value ?? 0} L<br/>Pending: ₹${p?.value ?? 0} L`
      },
    },
    legend: { bottom: 0, textStyle: { fontSize: 10 }, itemWidth: 10, itemHeight: 10 },
    grid: { top: 8, bottom: 40, left: 260, right: 8 },
    xAxis: { type: 'value', axisLabel: { formatter: v => `₹${v}L`, fontSize: 9 }, splitLine: { lineStyle: { type: 'dashed', color: '#f3f4f6' } } },
    yAxis: {
      type: 'category',
      data: top10Rev.map(i => i.desc),
      axisLabel: { fontSize: 9, width: 245, overflow: 'truncate' },
    },
    series: [
      { name: 'Earned',  type: 'bar', stack: 'v', barMaxWidth: 18, itemStyle: { color: TEAL  }, data: top10Rev.map(i => L(i.earned))  },
      { name: 'Pending', type: 'bar', stack: 'v', barMaxWidth: 18, itemStyle: { color: '#fca5a5' }, data: top10Rev.map(i => L(i.pending)) },
    ],
  })

  // 5. Pending Value by Inspection Agency
  const brandRev = [...a.brands].reverse()
  initOneChart('chart-brand', {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { bottom: 0, textStyle: { fontSize: 10 }, itemWidth: 10, itemHeight: 10 },
    grid: { top: 8, bottom: 40, left: 160, right: 8 },
    xAxis: { type: 'value', axisLabel: { formatter: v => `₹${v}L`, fontSize: 9 }, splitLine: { lineStyle: { type: 'dashed', color: '#f3f4f6' } } },
    yAxis: {
      type: 'category',
      data: brandRev.map(([,v]) => v.label.length > 20 ? v.label.substring(0, 20) + '…' : v.label),
      axisLabel: { fontSize: 9, width: 145, overflow: 'truncate' },
    },
    series: [
      { name: 'Earned',  type: 'bar', stack: 'v', barMaxWidth: 14, itemStyle: { color: TEAL  }, data: brandRev.map(([,v]) => L(v.earned))              },
      { name: 'Pending', type: 'bar', stack: 'v', barMaxWidth: 14, itemStyle: { color: '#fca5a5' }, data: brandRev.map(([,v]) => L(v.contract - v.earned)) },
    ],
  })

  // 6. Unit-type treemap
  const unitEntries = Object.entries(a.unitMap).filter(([,v]) => v > 0).sort((x, y) => y[1] - x[1])
  if (unitEntries.length > 0) {
    initOneChart('chart-unit', {
      tooltip: { formatter: p => `${p.name}<br/>${fmtCr(p.value)}` },
      series: [{
        type: 'treemap', roam: false, nodeClick: false,
        breadcrumb: { show: false },
        label: { fontSize: 11, fontWeight: 700 },
        itemStyle: { borderColor: '#fff', borderWidth: 2, gapWidth: 2 },
        data: unitEntries.map(([name, value], idx) => ({
          name, value,
          itemStyle: { color: PALETTE[idx % PALETTE.length] },
          label: { formatter: p => `${p.name}\n${fmtCr(p.value)}` },
        })),
      }],
    })
  }

  // 7. Challan cadence — always render; show "No data" title when empty
  initOneChart('chart-challan', {
    title: a.challanMonths.length === 0 ? { text: 'No receipt entries recorded yet', left: 'center', top: 'middle', textStyle: { color: '#9ca3af', fontSize: 12, fontWeight: 'normal' } } : undefined,
    tooltip: { trigger: 'axis', formatter: params => `${params[0].name}: ${params[0].value} entries` },
    grid: { top: 12, bottom: 52, left: 36, right: 8 },
    xAxis: { type: 'category', data: a.challanMonths, axisLabel: { fontSize: 9, rotate: a.challanMonths.length > 6 ? 45 : 0 } },
    yAxis: { type: 'value', name: 'Entries', nameTextStyle: { fontSize: 9 }, axisLabel: { fontSize: 9 }, minInterval: 1, splitLine: { lineStyle: { type: 'dashed', color: '#f3f4f6' } } },
    series: [{ type: 'bar', barMaxWidth: 36, itemStyle: { color: TEAL, borderRadius: [3, 3, 0, 0] }, data: a.challanCounts, label: { show: true, position: 'top', fontSize: 10, color: '#374151' } }],
  })
  chartInstances['chart-challan']?.resize()

  // 8. MB Billing velocity — always render; show "No data" title when empty
  initOneChart('chart-earned', {
    title: a.earnedMonths.length === 0 ? { text: 'No supply entries with dates recorded yet', left: 'center', top: 'middle', textStyle: { color: '#9ca3af', fontSize: 12, fontWeight: 'normal' } } : undefined,
    tooltip: { trigger: 'axis', formatter: params => `${params[0].name}<br/>Cumulative: ₹${params[0].value} L` },
    grid: { top: 12, bottom: 52, left: 52, right: 8 },
    xAxis: { type: 'category', data: a.earnedMonths, axisLabel: { fontSize: 9, rotate: a.earnedMonths.length > 6 ? 45 : 0 } },
    yAxis: { type: 'value', axisLabel: { formatter: v => `₹${v}L`, fontSize: 9 }, splitLine: { lineStyle: { type: 'dashed', color: '#f3f4f6' } } },
    series: [{
      type: 'line', smooth: true, symbol: 'circle', symbolSize: 6,
      itemStyle: { color: TEAL }, lineStyle: { width: 2 },
      areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(29,95,94,0.25)' }, { offset: 1, color: 'rgba(29,95,94,0)' }] } },
      data: a.cumulativeEarned,
      label: { show: a.earnedMonths.length <= 8 && a.earnedMonths.length > 0, position: 'top', fontSize: 9, formatter: p => `₹${p.value}L` },
    }],
  })
  chartInstances['chart-earned']?.resize()
}

watch([activeTab, selectedWork], () => {
  if (activeTab.value === 'analytics') {
    destroyCharts()
    initCharts()
  }
})

onMounted(() => window.addEventListener('resize', handleResize))
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  destroyCharts()
})

// ── PDF Export ────────────────────────────────────────────────────────────
const isGeneratingPDF = ref(false)

const generateWorkPDF = async () => {
  if (!selectedWork.value || !analytics.value) return
  isGeneratingPDF.value = true
  try {
    const { jsPDF } = await import('jspdf')
    const { default: autoTable } = await import('jspdf-autotable')

    const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' })

    const pdfFont = 'helvetica'
    doc.setFont(pdfFont)
    const pw = doc.internal.pageSize.getWidth()   // 297
    const ph = doc.internal.pageSize.getHeight()  // 210
    const mg = 12
    const cw = pw - mg * 2

    const C_TEAL  = [29, 95, 94]
    const C_AMBER = [193, 120, 65]
    const C_BLUE  = [0, 113, 227]
    const C_GRAY  = [107, 114, 128]

    const w = selectedWork.value
    const a = analytics.value

    const addPageHeader = (label) => {
      doc.setFillColor(...C_TEAL)
      doc.rect(0, 0, pw, 12, 'F')
      doc.setTextColor(255, 255, 255)
      doc.setFont(pdfFont, 'bold')
      doc.setFontSize(8.5)
      doc.text(`${label} — ${w.contractor_name || ''} · ${w.loa_number || ''}`, mg, 8)
      doc.setFontSize(7)
      doc.setFont(pdfFont, 'normal')
      doc.text(new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }), pw - mg, 8, { align: 'right' })
    }

    // ── PAGE 1: Summary ──────────────────────────────────────────────────────
    addPageHeader('Work Report')

    // Work name
    let y = 17
    if (w.name_of_work) {
      doc.setFont(pdfFont, 'normal')
      doc.setFontSize(9)
      doc.setTextColor(50, 50, 50)
      const lines = doc.splitTextToSize(w.name_of_work, cw)
      doc.text(lines.slice(0, 2), mg, y)
      y += lines.slice(0, 2).length * 5 + 3
    }

    // Metadata row
    const metaFields = [
      ['Consignee', w.consignee || '—'],
      ['HRMS ID', w.hrms_id || '—'],
      ['Completion', fmtDate(w.date_of_completion)],
      ['Agreement', w.contract_agreement || '—'],
      ['Tender', w.tender_number || '—'],
    ]
    const metaColW = cw / metaFields.length
    metaFields.forEach(([lbl, val], i) => {
      const x = mg + i * metaColW
      doc.setFont(pdfFont, 'bold')
      doc.setFontSize(7)
      doc.setTextColor(...C_GRAY)
      doc.text(lbl.toUpperCase(), x, y)
      doc.setFont(pdfFont, 'normal')
      doc.setFontSize(8.5)
      doc.setTextColor(30, 30, 30)
      doc.text(String(val).substring(0, 26), x, y + 5)
    })
    y += 13

    const tblFont = { font: pdfFont }

    // KPI table
    autoTable(doc, {
      startY: y,
      margin: { left: mg, right: mg },
      styles: tblFont,
      head: [['Contract Value', 'Earned', 'Pending', 'Supply (Sch A)', 'Execution (Sch B)', 'Lot Entries']],
      body: [[
        fmtCrPdf(a.contractTotal),
        fmtCrPdf(a.earnedTotal),
        fmtCrPdf(a.pendingTotal),
        `${a.schAPct.toFixed(1)}%  (${a.schACount} items)`,
        `${a.schBPct.toFixed(1)}%  (${a.schBCount} items)`,
        String(a.totalEntries),
      ]],
      headStyles: { fillColor: C_TEAL, textColor: [255, 255, 255], fontSize: 8, fontStyle: 'bold', halign: 'center' },
      bodyStyles: { fontSize: 9.5, fontStyle: 'bold', halign: 'center', minCellHeight: 9 },
      columnStyles: {
        1: { textColor: C_TEAL },
        2: { textColor: [220, 50, 50] },
        3: { textColor: C_TEAL },
        4: { textColor: C_AMBER },
      },
      tableLineColor: [229, 231, 235],
      tableLineWidth: 0.2,
    })
    y = doc.lastAutoTable.finalY + 8

    // Insights
    doc.setFont(pdfFont, 'bold')
    doc.setFontSize(8)
    doc.setTextColor(...C_TEAL)
    doc.text('AUTO-GENERATED INSIGHTS', mg, y)
    y += 5

    for (const ins of a.insights) {
      const icon = ins.type === 'warn' ? '⚠  ' : ins.type === 'good' ? '✓  ' : '→  '
      const color = ins.type === 'warn' ? [180, 70, 10] : ins.type === 'good' ? [22, 130, 60] : C_TEAL
      doc.setFont(pdfFont, 'normal')
      doc.setFontSize(8)
      doc.setTextColor(...color)
      const lines = doc.splitTextToSize(icon + ins.text, cw - 4)
      if (y + lines.length * 4.5 > ph - 10) { doc.addPage(); addPageHeader('Work Report — Insights'); y = 16 }
      doc.text(lines, mg + 2, y)
      y += lines.length * 4.5 + 2
    }

    // ── PAGE 2+: Charts ──────────────────────────────────────────────────────
    const chartDefs = [
      { id: 'chart-gauges',    title: 'Schedule A vs B — Progress' },
      { id: 'chart-waterfall', title: 'Financial Progress — Waterfall' },
      { id: 'chart-status',    title: 'Item Status' },
      { id: 'chart-top10',     title: 'Top 10 Items by Contract Value' },
      { id: 'chart-brand',     title: 'Pending Value by Inspection Agency' },
      { id: 'chart-unit',      title: 'Unit-type Contribution' },
      { id: 'chart-challan',   title: 'Challan Cadence' },
      { id: 'chart-earned',    title: 'MB Billing Velocity' },
    ]

    const chartImgs = chartDefs.map(({ id, title }) => {
      const inst = chartInstances[id]
      if (!inst) return null
      try {
        const pxW = inst.getWidth()
        const pxH = inst.getHeight()
        return {
          title,
          img: inst.getDataURL({ type: 'jpeg', pixelRatio: 1.5, backgroundColor: '#ffffff' }),
          ratio: pxH / pxW,
        }
      } catch { return null }
    }).filter(Boolean)

    if (chartImgs.length > 0) {
      doc.addPage()
      addPageHeader('Analytics Charts')

      const chartW = (cw - 6) / 2
      let cy = 16
      let col = 0
      let leftH = 0

      for (const { title, img, ratio } of chartImgs) {
        const imgH = chartW * ratio
        const rowH = imgH + 8  // 6 title + 2 gap
        const cx = mg + col * (chartW + 6)

        if (col === 0) {
          // Check page break before starting a new row
          if (cy + rowH > ph - 8) { doc.addPage(); addPageHeader('Analytics Charts'); cy = 16 }
          leftH = rowH
        }

        doc.setFont(pdfFont, 'bold')
        doc.setFontSize(7)
        doc.setTextColor(60, 60, 60)
        doc.text(title, cx, cy + 4)
        doc.addImage(img, 'JPEG', cx, cy + 6, chartW, imgH)

        if (col === 1) {
          col = 0
          cy += Math.max(leftH, rowH) + 4
        } else {
          col++
        }
      }
    }

    // ── PAGE: Items with progress ────────────────────────────────────────────
    doc.addPage()
    addPageHeader('Item Progress')

    const progressItems = (w.items || []).filter(item => {
      const sch = String(item.schedule || '').toUpperCase().trim()
      const isB = sch.startsWith('B')
      const done = isB ? (item.executed_quantity || 0) : (item.supplied_quantity || 0)
      return done > 0
    })

    autoTable(doc, {
      startY: 16,
      margin: { left: mg, right: mg },
      styles: tblFont,
      head: [['Sch', 'S.No', 'Item Description', 'Required', 'Supplied / Exec', 'Progress', 'Contract Value', 'Earned']],
      body: progressItems.map(item => {
        const sch = String(item.schedule || '').toUpperCase().trim()
        const isB = sch.startsWith('B')
        const qty = item.qty || 1
        const done = isB ? (item.executed_quantity || 0) : (item.supplied_quantity || 0)
        const pct = Math.min(done / qty * 100, 999)
        const contract = item.total_amount || 0
        const earned = contract * Math.min(done / qty, 1)
        return [
          item.schedule || '',
          item.serial_number || '',
          (item.item_desc || '').substring(0, 80),
          `${item.qty} ${item.unit}`,
          `${done} ${item.unit}`,
          `${pct.toFixed(0)}%`,
          fmtCrPdf(contract),
          fmtCrPdf(earned),
        ]
      }),
      headStyles: { fillColor: C_TEAL, textColor: [255, 255, 255], fontSize: 7.5, fontStyle: 'bold' },
      bodyStyles: { fontSize: 7.5 },
      columnStyles: {
        0: { cellWidth: 14, halign: 'center' },
        1: { cellWidth: 14, halign: 'center' },
        2: { cellWidth: 'auto' },
        3: { cellWidth: 26, halign: 'right' },
        4: { cellWidth: 28, halign: 'right' },
        5: { cellWidth: 18, halign: 'center', fontStyle: 'bold' },
        6: { cellWidth: 28, halign: 'right' },
        7: { cellWidth: 24, halign: 'right', textColor: C_TEAL },
      },
      alternateRowStyles: { fillColor: [249, 250, 251] },
      tableLineColor: [229, 231, 235],
      tableLineWidth: 0.2,
      didParseCell: (data) => {
        if (data.column.index === 5 && data.section === 'body') {
          const pct = parseFloat(data.cell.raw) || 0
          data.cell.styles.textColor = pct >= 99 ? C_TEAL : pct > 0 ? C_BLUE : C_GRAY
        }
      },
    })

    // Entries sub-tables per item
    for (const item of progressItems) {
      if (!(item.entries || []).length) continue
      const sch = String(item.schedule || '').toUpperCase().trim()
      const isB = sch.startsWith('B')

      autoTable(doc, {
        startY: doc.lastAutoTable.finalY + 2,
        margin: { left: mg + 3, right: mg },
        styles: tblFont,
        head: [
          [{ content: `${item.schedule} · S.No ${item.serial_number}  —  ${(item.item_desc || '').substring(0, 70)}`, colSpan: 7, styles: { fillColor: [235, 245, 244], textColor: C_TEAL, fontStyle: 'bold', fontSize: 7 } }],
          ['#', 'Type', 'Qty', 'Receive Note / Challan', 'UDM Entry', 'Submitted By', 'Date'],
        ],
        body: item.entries.map((e, idx) => [
          idx + 1,
          e.entry_type === 'execution' ? 'Exec' : 'Supply',
          `${e.quantity} ${item.unit}`,
          [e.receive_note_no, e.challan_no].filter(Boolean).join(' / ') || '—',
          e.udm_entry || '—',
          (() => {
            const u = e.submitted_by_user
            if (!u) return '—'
            const name = u.full_name || u.username
            const desig = u.designation
            return desig ? `${name}\n(${desig})` : name
          })(),
          e.date_of_receipt ? fmtDate(e.date_of_receipt) : fmtDateTime(e.submitted_at),
        ]),
        headStyles: { fillColor: [241, 245, 249], textColor: [75, 85, 99], fontSize: 7, fontStyle: 'bold' },
        bodyStyles: { fontSize: 7 },
        columnStyles: {
          0: { cellWidth: 8, halign: 'center' },
          1: { cellWidth: 16 },
          2: { cellWidth: 24, halign: 'right' },
          3: { cellWidth: 'auto' },
          4: { cellWidth: 28 },
          5: { cellWidth: 30 },
          6: { cellWidth: 28 },
        },
        tableLineColor: [229, 231, 235],
        tableLineWidth: 0.15,
        didParseCell: (data) => {
          if (data.column.index === 1 && data.section === 'body') {
            data.cell.styles.textColor = data.cell.raw === 'Exec' ? C_AMBER : C_TEAL
            data.cell.styles.fontStyle = 'bold'
          }
        },
      })
    }

    // Page numbers
    const totalPages = doc.getNumberOfPages()
    for (let i = 1; i <= totalPages; i++) {
      doc.setPage(i)
      doc.setFont(pdfFont, 'normal')
      doc.setFontSize(7)
      doc.setTextColor(...C_GRAY)
      doc.text(`Page ${i} of ${totalPages}`, pw - mg, ph - 4, { align: 'right' })
      doc.text(`ManageWorks — ${w.loa_number || 'Report'}`, mg, ph - 4)
    }

    doc.save(`Work_Report_${(w.loa_number || 'export').replace(/\//g, '-')}.pdf`)
  } finally {
    isGeneratingPDF.value = false
  }
}
</script>

<template>
  <div class="bg-white rounded-2xl soft-shadow h-full w-full flex flex-col overflow-hidden">

    <!-- ══ WORK LIST ══════════════════════════════════════════════════ -->
    <template v-if="!selectedWork">

      <div class="flex-shrink-0 px-8 pt-7 pb-5 border-b border-gray-100">
        <h1 class="text-2xl font-bold text-gray-900 tracking-tight mb-1">Work Details</h1>
        <p class="text-gray-400 text-sm font-medium mb-5">Browse all works and inspect item-level lot entry history.</p>
        <div class="flex items-center bg-gray-50 border border-gray-200 rounded-2xl px-5 py-3 focus-within:ring-2 focus-within:ring-[#1D5F5E]/20 focus-within:border-[#1D5F5E] focus-within:bg-white transition-all">
          <div class="i-carbon-search text-gray-400 text-base mr-3 flex-shrink-0"></div>
          <input v-model="searchQuery" type="text"
            placeholder="Search by LOA, Contractor, Tender, Consignee..."
            class="bg-transparent outline-none w-full text-gray-700 font-medium placeholder-gray-400 text-sm">
          <button v-if="searchQuery" @click="searchQuery = ''" class="ml-2 text-gray-300 hover:text-gray-500 transition-colors">
            <div class="i-carbon-close text-sm"></div>
          </button>
        </div>
      </div>

      <div v-if="isLoading" class="flex-1 flex items-center justify-center py-24">
        <div class="i-carbon-circle-dash animate-spin text-3xl text-[#1D5F5E]"></div>
      </div>

      <div v-else-if="filteredWorks.length === 0" class="flex-1 flex flex-col items-center justify-center py-24 text-center">
        <div class="i-carbon-document-unknown text-5xl text-gray-200 mb-4"></div>
        <p class="text-sm font-semibold text-gray-400">
          {{ searchQuery ? 'No works match your search.' : 'No works uploaded yet.' }}
        </p>
      </div>

      <template v-else>
        <div class="flex-1 overflow-auto px-8 py-5">
          <p class="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-4">
            {{ filteredWorks.length }} {{ filteredWorks.length === 1 ? 'work' : 'works' }}
            <template v-if="searchQuery"> matching "{{ searchQuery }}"</template>
          </p>
          <div class="grid grid-cols-1 gap-3">
            <button v-for="work in filteredWorks" :key="work.id" @click="selectWork(work)"
              class="w-full text-left bg-white border border-gray-200 hover:border-[#1D5F5E] hover:bg-[#1D5F5E]/5 px-5 py-4 transition-all group rounded-xl">
              <div class="flex items-center justify-between gap-3">
                <div class="min-w-0">
                  <p class="text-sm font-semibold text-gray-900 truncate">{{ work.contractor_name || '—' }}</p>
                  <div class="flex items-center gap-3 flex-wrap mt-1">
                    <span class="text-[11px] font-semibold text-[#1D5F5E] bg-[#1D5F5E]/10 px-2 py-0.5 rounded-full">{{ work.loa_number || '—' }}</span>
                    <span class="text-[11px] text-gray-500">Tender: <span class="font-semibold text-gray-700">{{ work.tender_number || '—' }}</span></span>
                    <span class="text-[11px] text-gray-500">Consignee: <span class="font-semibold text-gray-700">{{ work.consignee || '—' }}</span></span>
                    <span class="text-[11px] text-gray-500">Completion: <span class="font-semibold text-gray-700">{{ fmtDate(work.date_of_completion) }}</span></span>
                  </div>
                </div>
                <div class="flex items-center gap-4 flex-shrink-0">
                  <div class="text-right">
                    <p class="text-sm font-bold text-gray-800">{{ work.items.length }}</p>
                    <p class="text-[10px] text-gray-400">items</p>
                  </div>
                  <div class="text-right">
                    <p class="text-sm font-bold text-gray-800">{{ work.items.reduce((s, i) => s + (i.entries || []).length, 0) }}</p>
                    <p class="text-[10px] text-gray-400">entries</p>
                  </div>
                  <div class="i-carbon-chevron-right text-gray-300 group-hover:text-[#1D5F5E] transition-colors text-lg"></div>
                </div>
              </div>
            </button>
          </div>
        </div>
      </template>

    </template>

    <!-- ══ WORK DETAIL VIEW ══════════════════════════════════════════ -->
    <template v-else>
      <div class="flex flex-col h-full overflow-hidden animate-fade-in">

        <!-- Header -->
        <div class="flex-shrink-0 px-6 pt-5 pb-4 border-b border-gray-100">
          <div class="flex items-start gap-4 min-w-0">
            <button @click="selectedWork = null"
              class="mt-0.5 w-9 h-9 flex-shrink-0 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-600 transition-all">
              <div class="i-carbon-arrow-left text-base"></div>
            </button>
            <div class="min-w-0 flex-1">
              <h2 class="text-xl font-bold text-gray-900 truncate">{{ selectedWork.contractor_name }}</h2>
              <p v-if="selectedWork.name_of_work" class="text-xs text-gray-500 mt-0.5 leading-snug max-w-3xl">{{ selectedWork.name_of_work }}</p>
              <div class="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1.5 text-xs text-gray-500">
                <span><span class="text-gray-400 font-medium">LOA</span> <span class="font-semibold text-gray-800">{{ selectedWork.loa_number || '—' }}</span></span>
                <span class="text-gray-200">·</span>
                <span><span class="text-gray-400 font-medium">Tender</span> <span class="font-semibold text-gray-800">{{ selectedWork.tender_number || '—' }}</span></span>
                <span class="text-gray-200">·</span>
                <span><span class="text-gray-400 font-medium">Consignee</span> <span class="font-semibold text-gray-800">{{ selectedWork.consignee || '—' }}</span></span>
                <span class="text-gray-200">·</span>
                <span><span class="text-gray-400 font-medium">Completion</span> <span class="font-semibold text-gray-800">{{ fmtDate(selectedWork.date_of_completion) }}</span></span>
              </div>
            </div>
          </div>

          <!-- Tab bar + Export -->
          <div class="flex items-center justify-between mt-4">
          <div class="flex gap-1.5">
            <button @click="activeTab = 'analytics'"
              :class="activeTab === 'analytics'
                ? 'bg-[#1D5F5E] text-white'
                : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700'"
              class="px-4 py-1.5 rounded-md text-xs font-semibold transition-all flex items-center gap-1.5">
              <div class="i-carbon-analytics text-[11px]"></div>
              Analytics
            </button>
            <button @click="activeTab = 'items'"
              :class="activeTab === 'items'
                ? 'bg-[#1D5F5E] text-white'
                : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700'"
              class="px-4 py-1.5 rounded-md text-xs font-semibold transition-all flex items-center gap-1.5">
              <div class="i-carbon-list-boxes text-[11px]"></div>
              Item Tracking
            </button>
          </div>

          <!-- Export PDF -->
          <button @click="generateWorkPDF" :disabled="isGeneratingPDF"
            class="flex items-center gap-1.5 px-4 py-1.5 rounded-xl border border-gray-200 text-xs font-semibold text-gray-600 hover:bg-gray-50 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0">
            <div :class="isGeneratingPDF ? 'i-carbon-circle-dash animate-spin' : 'i-carbon-document-pdf'" class="text-[11px]"></div>
            {{ isGeneratingPDF ? 'Generating…' : 'Export PDF' }}
          </button>
          </div>
        </div>

        <!-- ══ ANALYTICS TAB ══════════════════════════════════════════ -->
        <div v-if="activeTab === 'analytics'" class="flex-1 overflow-y-auto p-5 space-y-4">

          <!-- KPI Strip -->
          <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <div class="bg-gray-50 border border-gray-200 rounded-xl p-3 relative overflow-hidden">
              <div class="absolute top-0 left-0 right-0 h-0.5 bg-gray-700"></div>
              <div class="text-[9px] font-bold text-gray-400 uppercase tracking-widest mt-0.5 mb-1.5">Contract Value</div>
              <div class="text-base font-extrabold text-gray-900 leading-tight">{{ fmtCr(analytics?.contractTotal) }}</div>
            </div>
            <div class="bg-gray-50 border border-gray-200 rounded-xl p-3 relative overflow-hidden">
              <div class="absolute top-0 left-0 right-0 h-0.5 bg-[#1D5F5E]"></div>
              <div class="text-[9px] font-bold text-gray-400 uppercase tracking-widest mt-0.5 mb-1.5">Earned</div>
              <div class="text-base font-extrabold text-[#1D5F5E] leading-tight">{{ fmtCr(analytics?.earnedTotal) }}</div>
              <div class="text-[10px] text-gray-400 mt-0.5">{{ analytics?.overallPct?.toFixed(1) }}% overall</div>
            </div>
            <div class="bg-gray-50 border border-gray-200 rounded-xl p-3 relative overflow-hidden">
              <div class="absolute top-0 left-0 right-0 h-0.5 bg-red-400"></div>
              <div class="text-[9px] font-bold text-gray-400 uppercase tracking-widest mt-0.5 mb-1.5">Pending</div>
              <div class="text-base font-extrabold text-red-500 leading-tight">{{ fmtCr(analytics?.pendingTotal) }}</div>
            </div>
            <div class="bg-gray-50 border border-gray-200 rounded-xl p-3 relative overflow-hidden">
              <div class="absolute top-0 left-0 right-0 h-0.5 bg-[#1D5F5E]"></div>
              <div class="text-[9px] font-bold text-gray-400 uppercase tracking-widest mt-0.5 mb-1.5">Supply (Sch A)</div>
              <div class="text-base font-extrabold text-[#1D5F5E] leading-tight">{{ analytics?.schAPct?.toFixed(1) }}%</div>
              <div class="text-[10px] text-gray-400 mt-0.5">{{ analytics?.schACount }} items</div>
            </div>
            <div class="bg-gray-50 border border-gray-200 rounded-xl p-3 relative overflow-hidden">
              <div class="absolute top-0 left-0 right-0 h-0.5 bg-[#C17841]"></div>
              <div class="text-[9px] font-bold text-gray-400 uppercase tracking-widest mt-0.5 mb-1.5">Execution (Sch B)</div>
              <div class="text-base font-extrabold text-[#C17841] leading-tight">{{ analytics?.schBPct?.toFixed(1) }}%</div>
              <div class="text-[10px] text-gray-400 mt-0.5">{{ analytics?.schBCount }} items</div>
            </div>
            <div class="bg-gray-50 border border-gray-200 rounded-xl p-3 relative overflow-hidden">
              <div class="absolute top-0 left-0 right-0 h-0.5 bg-accent"></div>
              <div class="text-[9px] font-bold text-gray-400 uppercase tracking-widest mt-0.5 mb-1.5">Lot Entries</div>
              <div class="text-base font-extrabold text-accent leading-tight">{{ analytics?.totalEntries }}</div>
              <div class="text-[10px] text-gray-400 mt-0.5">submissions</div>
            </div>
          </div>

          <!-- Row 1: Gauges + Waterfall + Status -->
          <div class="grid grid-cols-12 gap-3">
            <div class="col-span-12 lg:col-span-5 bg-white border border-gray-200 rounded-xl p-4">
              <div class="flex justify-between items-baseline mb-0.5">
                <h3 class="text-sm font-bold text-gray-900">Schedule A vs B — Progress</h3>
                <span class="text-[9px] font-bold text-gray-400 uppercase tracking-widest">Value %</span>
              </div>
              <p class="text-[11px] text-gray-400 mb-2">Supply ships first; execution cannot outrun it.</p>
              <div id="chart-gauges" style="height:210px"></div>
            </div>
            <div class="col-span-12 lg:col-span-4 bg-white border border-gray-200 rounded-xl p-4">
              <div class="flex justify-between items-baseline mb-0.5">
                <h3 class="text-sm font-bold text-gray-900">Financial Progress — Waterfall</h3>
                <span class="text-[9px] font-bold text-gray-400 uppercase tracking-widest">₹ Lakhs</span>
              </div>
              <p class="text-[11px] text-gray-400 mb-2">Contract value earned vs pending by schedule.</p>
              <div id="chart-waterfall" style="height:210px"></div>
            </div>
            <div class="col-span-12 lg:col-span-3 bg-white border border-gray-200 rounded-xl p-4">
              <div class="flex justify-between items-baseline mb-0.5">
                <h3 class="text-sm font-bold text-gray-900">Item Status</h3>
                <span class="text-[9px] font-bold text-gray-400 uppercase tracking-widest">Item Count</span>
              </div>
              <p class="text-[11px] text-gray-400 mb-2">≥99% done · 1–98% · 0%, by schedule.</p>
              <div id="chart-status" style="height:210px"></div>
            </div>
          </div>

          <!-- Row 2: Top 10 + Brand supply -->
          <div class="grid grid-cols-12 gap-3">
            <div class="col-span-12 lg:col-span-7 bg-white border border-gray-200 rounded-xl p-4">
              <div class="flex justify-between items-baseline mb-0.5">
                <h3 class="text-sm font-bold text-gray-900">Top 10 Items by Contract Value</h3>
                <span class="text-[9px] font-bold text-gray-400 uppercase tracking-widest">₹ Earned vs Pending</span>
              </div>
              <p class="text-[11px] text-gray-400 mb-2">High-value line-items driving overall progress.</p>
              <div id="chart-top10" style="height:310px">
                <div v-if="!analytics?.top10?.length" class="flex items-center justify-center h-full text-gray-300 text-xs">No financial data available</div>
              </div>
            </div>
            <div class="col-span-12 lg:col-span-5 bg-white border border-gray-200 rounded-xl p-4">
              <div class="flex justify-between items-baseline mb-0.5">
                <h3 class="text-sm font-bold text-gray-900">Pending Value by Inspection Agency</h3>
                <span class="text-[9px] font-bold text-gray-400 uppercase tracking-widest">₹ Lakhs</span>
              </div>
              <p class="text-[11px] text-gray-400 mb-2">Agency-wise earned vs pending contract value.</p>
              <div id="chart-brand" style="height:310px">
                <div v-if="!analytics?.brands?.length" class="flex items-center justify-center h-full text-gray-300 text-xs">No inspection agency data available</div>
              </div>
            </div>
          </div>

          <!-- Row 3: Unit treemap + Challan cadence -->
          <div class="grid grid-cols-12 gap-3">
            <div class="col-span-12 lg:col-span-4 bg-white border border-gray-200 rounded-xl p-4">
              <div class="flex justify-between items-baseline mb-0.5">
                <h3 class="text-sm font-bold text-gray-900">Unit-type Contribution</h3>
                <span class="text-[9px] font-bold text-gray-400 uppercase tracking-widest">By Contract Value</span>
              </div>
              <p class="text-[11px] text-gray-400 mb-2">Numbers, Metre, Set, Lumpsum — shape of the work.</p>
              <div id="chart-unit" style="height:230px">
                <div v-if="!Object.keys(analytics?.unitMap || {}).length" class="flex items-center justify-center h-full text-gray-300 text-xs">No unit data</div>
              </div>
            </div>
            <div class="col-span-12 lg:col-span-8 bg-white border border-gray-200 rounded-xl p-4">
              <div class="flex justify-between items-baseline mb-0.5">
                <h3 class="text-sm font-bold text-gray-900">Challan Cadence</h3>
                <span class="text-[9px] font-bold text-gray-400 uppercase tracking-widest">Entries per Month</span>
              </div>
              <p class="text-[11px] text-gray-400 mb-2">Supply receipt tempo over time.</p>
              <div id="chart-challan" style="height:230px"></div>
            </div>
          </div>

          <!-- Row 4: MB Billing Velocity -->
          <div class="bg-white border border-gray-200 rounded-xl p-4">
            <div class="flex justify-between items-baseline mb-0.5">
              <h3 class="text-sm font-bold text-gray-900">MB Billing Velocity</h3>
              <span class="text-[9px] font-bold text-gray-400 uppercase tracking-widest">Cumulative Earned ₹ L by Receipt Month</span>
            </div>
            <p class="text-[11px] text-gray-400 mb-2">Cumulative contract value earned as supply receipts arrive over time.</p>
            <div id="chart-earned" style="height:220px">
            </div>
          </div>

          <!-- Auto-generated Insights -->
          <div class="bg-white border border-gray-200 rounded-xl p-4">
            <h3 class="text-sm font-bold text-gray-900 mb-3 flex items-center gap-2">
              <div class="w-2 h-2 rounded-full bg-[#1D5F5E] flex-shrink-0"></div>
              Auto-generated Insights
              <span class="text-[11px] text-gray-400 font-normal ml-1">(reads current data)</span>
            </h3>
            <ul class="divide-y divide-dashed divide-gray-100">
              <li v-for="(ins, idx) in analytics?.insights" :key="idx"
                class="py-2.5 pl-6 pr-2 relative text-xs text-gray-700 leading-relaxed">
                <span class="absolute left-0 top-2.5 font-bold text-sm"
                  :class="ins.type === 'warn' ? 'text-orange-400' : ins.type === 'good' ? 'text-green-500' : 'text-[#1D5F5E]'">
                  {{ ins.type === 'warn' ? '⚠' : ins.type === 'good' ? '✓' : '→' }}
                </span>
                <span v-html="ins.text"></span>
              </li>
            </ul>
          </div>

        </div>

        <!-- ══ ITEMS & LEVEL TRACKING TAB ════════════════════════════ -->
        <div v-else class="flex flex-col flex-1 overflow-hidden">

          <!-- Filter bar -->
          <div class="flex-shrink-0 px-6 py-3 border-b border-gray-100 flex items-center gap-3">
            <div class="flex items-center bg-gray-50 border border-gray-200 rounded-xl px-4 py-2 flex-1 max-w-xs focus-within:ring-2 focus-within:ring-[#1D5F5E]/20 focus-within:border-[#1D5F5E] transition-all">
              <div class="i-carbon-filter text-gray-400 mr-2 text-sm"></div>
              <input v-model="itemFilter" type="text" placeholder="Filter items..."
                class="bg-transparent outline-none w-full text-xs text-gray-700 placeholder-gray-400 font-medium">
            </div>
            <button @click="sortKey = ''; itemFilter = ''" class="px-3 py-1.5 border border-gray-200 rounded-lg text-xs font-semibold text-gray-500 hover:bg-gray-50 transition-colors flex items-center gap-1">
              <div class="i-carbon-reset text-xs"></div> Reset
            </button>
            <div class="ml-auto text-[11px] text-gray-400 font-medium">
              {{ sortedItems.length }} item{{ sortedItems.length !== 1 ? 's' : '' }}
            </div>
          </div>

          <!-- Items table -->
          <div class="overflow-y-auto flex-1">
            <table class="w-full border-collapse">
              <thead class="bg-gray-50 sticky top-0 z-10">
                <tr class="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-gray-100">
                  <th class="px-4 py-3 text-center w-14">Sch</th>
                  <th class="px-4 py-3 text-center w-14">S.No</th>
                  <th class="px-4 py-3 text-left">Item Description</th>
                  <th @click="toggleSort('qty')" class="px-4 py-3 text-right w-28 cursor-pointer select-none hover:text-gray-600 transition-colors">
                    <div class="flex items-center justify-end gap-1">Required <div :class="sortIcon('qty')" class="text-[9px]" :style="{ opacity: sortKey === 'qty' ? 1 : 0.35 }"></div></div>
                  </th>
                  <th @click="toggleSort('submitted')" class="px-4 py-3 text-right w-28 cursor-pointer select-none hover:text-gray-600 transition-colors">
                    <div class="flex items-center justify-end gap-1">Submitted <div :class="sortIcon('submitted')" class="text-[9px]" :style="{ opacity: sortKey === 'submitted' ? 1 : 0.35 }"></div></div>
                  </th>
                  <th @click="toggleSort('progress')" class="px-4 py-3 w-40 cursor-pointer select-none hover:text-gray-600 transition-colors">
                    <div class="flex items-center gap-1">Progress <div :class="sortIcon('progress')" class="text-[9px]" :style="{ opacity: sortKey === 'progress' ? 1 : 0.35 }"></div></div>
                  </th>
                  <th @click="toggleSort('entries')" class="px-4 py-3 text-center w-24 cursor-pointer select-none hover:text-gray-600 transition-colors">
                    <div class="flex items-center justify-center gap-1">Entries <div :class="sortIcon('entries')" class="text-[9px]" :style="{ opacity: sortKey === 'entries' ? 1 : 0.35 }"></div></div>
                  </th>
                </tr>
              </thead>
              <tbody>
                <template v-if="sortedItems.length === 0">
                  <tr><td colspan="7" class="p-8 text-center text-gray-400 text-xs font-medium">No items match your filter.</td></tr>
                </template>

                <template v-for="item in sortedItems" :key="item.id">
                  <!-- Main item row -->
                  <tr
                    class="border-b border-gray-100 hover:bg-accent-soft/40 transition-colors cursor-pointer"
                    :class="expandedId === item.id ? 'bg-accent-soft/40' : ''"
                    @click="toggleExpand(item.id)"
                  >
                    <td class="px-4 py-3 text-center">
                      <span class="rounded-md px-2 py-0.5 text-[10px] font-bold"
                        :class="String(item.schedule||'').toUpperCase().startsWith('A')
                          ? 'bg-[#1D5F5E]/10 text-[#1D5F5E]'
                          : 'bg-[#C17841]/10 text-[#C17841]'">
                        {{ item.schedule }}
                      </span>
                    </td>
                    <td class="px-4 py-3 text-center text-[11px] text-gray-500 font-semibold">{{ item.serial_number }}</td>
                    <td class="px-4 py-3">
                      <p class="text-xs font-medium text-gray-800 line-clamp-2 leading-relaxed">{{ item.item_desc }}</p>
                      <p v-if="item.technical_specification" class="text-[10px] text-gray-400 mt-0.5">{{ item.technical_specification }}</p>
                    </td>
                    <td class="px-4 py-3 text-right text-xs font-semibold text-gray-600">
                      {{ item.qty }} <span class="text-gray-400 font-normal text-[10px]">{{ item.unit }}</span>
                    </td>
                    <td class="px-4 py-3 text-right text-xs font-semibold"
                      :class="(item.supplied_quantity || 0) > (item.qty || 0) ? 'text-orange-500' : 'text-gray-800'">
                      {{ String(item.schedule||'').toUpperCase().startsWith('B') ? (item.executed_quantity || 0) : (item.supplied_quantity || 0) }}
                      <span class="text-gray-400 font-normal text-[10px]">{{ item.unit }}</span>
                      <span v-if="(item.supplied_quantity || 0) > (item.qty || 0)" class="ml-1 text-[9px] text-orange-400 font-bold">OVER</span>
                    </td>
                    <td class="px-4 py-3">
                      <div class="flex items-center gap-2">
                        <div class="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                          <div class="h-full rounded-full transition-all duration-500"
                            :class="progressPct(item) > 100 ? 'bg-orange-400' : 'bg-[#1D5F5E]'"
                            :style="{ width: Math.min(progressPct(item), 100) + '%' }">
                          </div>
                        </div>
                        <span class="text-[10px] font-bold w-8 text-right"
                          :class="progressPct(item) > 100 ? 'text-orange-500' : progressPct(item) >= 99 ? 'text-[#1D5F5E]' : 'text-gray-500'">
                          {{ progressPct(item) }}%
                        </span>
                      </div>
                    </td>
                    <td class="px-4 py-3 text-center">
                      <div class="flex items-center justify-center gap-1">
                        <span class="text-[11px] font-bold"
                          :class="(item.entries||[]).length > 0 ? 'text-[#1D5F5E]' : 'text-gray-300'">
                          {{ (item.entries || []).length }}
                        </span>
                        <div :class="expandedId === item.id ? 'i-carbon-chevron-up text-gray-500' : 'i-carbon-chevron-down text-gray-300'" class="text-xs"></div>
                      </div>
                    </td>
                  </tr>

                  <!-- Expanded entry history + mini tracking chart -->
                  <tr v-if="expandedId === item.id">
                    <td colspan="7" class="border-b border-gray-100 px-6 py-4 bg-gray-50/40">

                      <div v-if="(item.entries || []).length === 0"
                        class="text-center py-6 text-xs text-gray-400 font-medium bg-white rounded-xl border border-dashed border-gray-200">
                        <div class="i-carbon-data-table text-2xl text-gray-200 mb-2 mx-auto"></div>
                        No lot entries recorded for this item yet.
                      </div>

                      <div v-else class="space-y-3">

                        <!-- Lot history table -->
                        <div class="bg-white rounded-xl border border-gray-200 overflow-hidden">
                          <div class="px-5 py-3 border-b border-gray-100 flex items-center gap-2">
                            <div class="i-carbon-list text-gray-400 text-sm"></div>
                            <h4 class="text-xs font-bold text-gray-600 uppercase tracking-wide">
                              Lot History — {{ item.entries.length }} {{ item.entries.length === 1 ? 'entry' : 'entries' }}
                            </h4>
                          </div>
                          <div class="overflow-x-auto">
                            <table class="w-full text-xs min-w-[600px]">
                              <thead class="bg-gray-50 text-[10px] text-gray-400 font-bold uppercase tracking-widest">
                                <tr>
                                  <th class="px-4 py-2 text-left w-8">#</th>
                                  <th class="px-4 py-2 text-left w-20">Type</th>
                                  <th class="px-4 py-2 text-right w-28">Quantity</th>
                                  <th class="px-4 py-2 text-left">Receive Note / Challan</th>
                                  <th class="px-4 py-2 text-left">UDM Entry</th>
                                  <th class="px-4 py-2 text-left">Submitted By</th>
                                  <th class="px-4 py-2 text-left">Date</th>
                                </tr>
                              </thead>
                              <tbody class="divide-y divide-gray-50">
                                <tr v-for="(entry, idx) in item.entries" :key="entry.id"
                                  class="hover:bg-gray-50/50 transition-colors">
                                  <td class="px-4 py-2.5 text-gray-400 font-semibold">{{ idx + 1 }}</td>
                                  <td class="px-4 py-2.5">
                                    <span class="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase"
                                      :class="entry.entry_type === 'execution'
                                        ? 'bg-[#C17841]/10 text-[#C17841]'
                                        : 'bg-[#1D5F5E]/10 text-[#1D5F5E]'">
                                      {{ entry.entry_type }}
                                    </span>
                                  </td>
                                  <td class="px-4 py-2.5 text-right font-bold text-gray-800">
                                    {{ entry.quantity }} <span class="text-gray-400 font-normal">{{ item.unit }}</span>
                                  </td>
                                  <td class="px-4 py-2.5 text-gray-600 font-medium">
                                    <span v-if="entry.receive_note_no" class="block text-gray-800">{{ entry.receive_note_no }}</span>
                                    <span v-if="entry.challan_no" class="block text-gray-500 text-[10px]">{{ entry.challan_no }}</span>
                                    <span v-if="!entry.receive_note_no && !entry.challan_no" class="text-gray-300">—</span>
                                  </td>
                                  <td class="px-4 py-2.5 text-gray-600 font-medium">{{ entry.udm_entry || '—' }}</td>
                                  <td class="px-4 py-2.5 text-gray-600 font-medium">
                                    <span class="block font-semibold text-gray-800">{{ entry.submitted_by_user?.full_name || entry.submitted_by_user?.username || '—' }}</span>
                                    <span v-if="entry.submitted_by_user?.designation" class="block text-[10px] text-gray-400">{{ entry.submitted_by_user.designation }}</span>
                                  </td>
                                  <td class="px-4 py-2.5 text-gray-400 whitespace-nowrap">
                                    <span v-if="entry.date_of_receipt" class="block font-medium text-gray-600">{{ fmtDate(entry.date_of_receipt) }}</span>
                                    <span class="text-[10px]">{{ fmtDateTime(entry.submitted_at) }}</span>
                                  </td>
                                </tr>
                              </tbody>
                              <tfoot class="bg-gray-50 border-t border-gray-100">
                                <tr>
                                  <td class="px-4 py-2.5 text-[10px] font-bold text-gray-400 uppercase tracking-wide" colspan="2">Total</td>
                                  <td class="px-4 py-2.5 text-right font-bold text-gray-800">
                                    {{ (item.supplied_quantity || 0) }} <span class="text-gray-400 font-normal">{{ item.unit }}</span>
                                    <span v-if="(item.supplied_quantity || 0) > (item.qty || 0)"
                                      class="ml-1 text-[9px] font-bold text-orange-500">EXCEEDS SCHEDULE</span>
                                  </td>
                                  <td colspan="4"></td>
                                </tr>
                              </tfoot>
                            </table>
                          </div>
                        </div>

                      </div>
                    </td>
                  </tr>

                </template>
              </tbody>
            </table>
          </div>

        </div>

      </div>
    </template>

  </div>
</template>

<style scoped>
@keyframes fade-in { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
.animate-fade-in { animation: fade-in 0.25s cubic-bezier(.4,0,.2,1); }
</style>
