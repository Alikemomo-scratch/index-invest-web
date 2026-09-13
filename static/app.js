const svgNS = "http://www.w3.org/2000/svg";
function localISO(value) {
  const year = value.getFullYear(), month = String(value.getMonth() + 1).padStart(2, "0"), day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
const initialDcaEnd = new Date();
const initialDcaStart = new Date(initialDcaEnd);
initialDcaStart.setFullYear(initialDcaStart.getFullYear() - 10);
const state = {
  indexId: "csi300", metricId: "pe", lookback: 10, historyFrequency: "monthly",
  frequency: "quarterly", years: 5, measure: "annualized",
  dcaStartDate: localISO(initialDcaStart), dcaEndDate: localISO(initialDcaEnd),
  dcaCadence: "monthly", dcaScheduleValue: 1, contributionAmount: 1000,
  indices: [], requestToken: 0, historyHover: null, returnHover: null,
};
const $ = (id) => document.getElementById(id);

async function fetchJSON(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try { message = (await response.json()).detail || message; } catch (_) { /* keep status */ }
    throw new Error(message);
  }
  return response.json();
}

function setHealth(ok, text) {
  $("healthDot").className = `dot ${ok ? "ok" : "error"}`;
  $("healthText").textContent = text;
}

function selectedIndex() { return state.indices.find((item) => item.id === state.indexId); }
function formatDate(value) { return value ? value.replaceAll("-", ".") : "暂无日期"; }
function formatPct(value) { return value == null ? "—" : `${value < 0 ? "−" : ""}${Math.abs(value).toFixed(1)}%`; }
function formatMoney(value, currency = "") {
  if (value == null) return "—";
  const amount = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(value);
  return `${currency === "CNY" ? "¥" : currency === "USD" ? "$" : ""}${amount}`;
}
function showNotice(id, message, isError = false) {
  const element = $(id);
  element.textContent = message || "";
  element.classList.toggle("hidden", !message);
  element.classList.toggle("error", isError);
}

function dcaQuery() {
  return new URLSearchParams({
    contribution_amount: String(state.contributionAmount),
    start_date: state.dcaStartDate,
    end_date: state.dcaEndDate,
    cadence: state.dcaCadence,
    schedule_value: String(state.dcaScheduleValue),
  });
}

function rebuildDcaScheduleOptions() {
  const select = $("dcaScheduleValue");
  const weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
  const limit = state.dcaCadence === "monthly" ? 31 : 7;
  if (state.dcaScheduleValue > limit) state.dcaScheduleValue = 1;
  select.replaceChildren(...Array.from({length: limit}, (_, index) => {
    const option = document.createElement("option");
    option.value = String(index + 1);
    option.textContent = state.dcaCadence === "monthly" ? `${index + 1} 号` : weekdays[index];
    return option;
  }));
  select.value = String(state.dcaScheduleValue);
  $("dcaScheduleLabel").textContent = state.dcaCadence === "monthly" ? "每月几号" : "每周几";
}

async function bootstrap() {
  try {
    await fetchJSON("/api/health");
    setHealth(true, "本地运行 · 数据可追溯");
    const payload = await fetchJSON("/api/indices");
    state.indices = payload.items;
    const select = $("indexSelect");
    select.replaceChildren(...state.indices.map((item) => {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = `${item.name} · ${item.code} · ${item.market_label}`;
      return option;
    }));
    select.value = state.indexId;
    select.disabled = false;
    $("refreshButton").disabled = false;
    $("dcaStartDate").value = state.dcaStartDate;
    $("dcaEndDate").value = state.dcaEndDate;
    rebuildDcaScheduleOptions();
    await loadAll();
  } catch (error) {
    setHealth(false, "本地服务异常");
    showNotice("valuationNotice", `无法启动研究台：${error.message}`, true);
    showNotice("returnNotice", "请确认本地服务仍在运行，然后刷新页面。", true);
    showNotice("dcaNotice", "本地服务不可用，暂时无法计算定投。", true);
  }
}

function setBusy(id, busy) { $(id).setAttribute("aria-busy", String(busy)); }

async function loadAll() {
  const requestToken = ++state.requestToken;
  const index = selectedIndex();
  if (!index) return;
  $("marketBadge").textContent = index.market_label;
  $("valuationTitle").textContent = `${index.name} · 当前估值`;
  $("asOf").textContent = "正在从本地缓存或远端来源读取…";
  $("validationIndex").textContent = `核验 ${index.name} 的公开历史值`;
  showNotice("valuationNotice", ""); showNotice("returnNotice", ""); showNotice("dcaNotice", "");
  setBusy("valuation", true); setBusy("returns", true); setBusy("dca", true);
  const researchURL = `/api/indices/${state.indexId}/research?lookback_years=${state.lookback}&history_frequency=${state.historyFrequency}`;
  const returnsURL = `/api/indices/${state.indexId}/returns?frequency=${state.frequency}&holding_years=${state.years}&measure=${state.measure}`;
  const dcaURL = `/api/indices/${state.indexId}/dca?${dcaQuery()}`;
  const [research, returns, dca] = await Promise.allSettled([fetchJSON(researchURL), fetchJSON(returnsURL), fetchJSON(dcaURL)]);
  if (requestToken !== state.requestToken) return;
  if (research.status === "fulfilled") renderResearch(research.value);
  else renderResearchError(research.reason);
  if (returns.status === "fulfilled") renderReturns(returns.value);
  else renderReturnsError(returns.reason);
  if (dca.status === "fulfilled") renderDca(dca.value);
  else renderDcaError(dca.reason);
  setBusy("valuation", false); setBusy("returns", false); setBusy("dca", false);
}

function renderResearch(payload) {
  window.lastResearch = payload;
  const index = payload.index;
  $("valuationTitle").textContent = `${index.name} · 当前估值`;
  $("asOf").textContent = `${index.currency} · 数据截至 ${formatDate(payload.as_of)} · ${payload.lookback_years} 年回看`;
  const useful = payload.metrics.filter((metric) => metric.history?.length);
  if (!payload.metrics.some((metric) => metric.id === state.metricId && metric.history?.length)) {
    state.metricId = useful[0]?.id || "pe";
  }
  const container = $("metrics");
  container.replaceChildren(...payload.metrics.map((metric) => metricCard(metric)));
  const active = payload.metrics.find((metric) => metric.id === state.metricId) || payload.metrics[0];
  renderHistory(active);
  const missing = payload.metrics.filter((metric) => metric.status !== "ready").map((metric) => `${metric.label}：${metric.reason || metric.note || "历史样本不足"}`);
  const stale = payload.metrics.some((metric) => metric.stale);
  showNotice("valuationNotice", [stale ? "远端刷新失败，当前展示过期缓存。" : "", ...missing].filter(Boolean).join(" "));
}

function metricCard(metric) {
  const button = document.createElement("button");
  const available = metric.history?.length > 0;
  button.className = `metric ${available ? "available" : "unavailable"} ${metric.id === state.metricId ? "active" : ""}`;
  button.disabled = !available;
  const percentile = metric.percentile == null ? "分位不可用" : `${metric.lookback_years} 年分位`;
  const value = metric.value == null ? "—" : `${metric.value.toFixed(metric.id === "dividend_yield" ? 2 : 2)}${metric.unit}`;
  button.innerHTML = `<div class="metric-top"><span>${metric.label}</span><span>${percentile}</span></div><div class="metric-value">${value}</div><div class="metric-foot"><span>${metric.percentile == null ? metric.status === "unavailable" ? "暂无" : "样本不足" : `${metric.percentile}%`}</span><span class="meter"><i style="width:${metric.percentile || 0}%"></i></span></div>`;
  if (available) button.addEventListener("click", () => { state.metricId = metric.id; renderResearch(window.lastResearch); });
  button.title = metric.reason || metric.note || `${metric.label}，${metric.sample_count} 个样本`;
  return button;
}

function renderDividendAudit(metric) {
  const audit = $("dividendAudit");
  const visible = metric?.id === "dividend_yield";
  audit.classList.toggle("hidden", !visible);
  if (!visible) return;
  const official = metric.official_values || [];
  $("dividendOfficial").textContent = official.length
    ? `官方核对：${official.map((item) => `${item.label} ${item.value.toFixed(2)}${item.unit}`).join(" · ")} · ${formatDate(official[0].date)}`
    : "官方核对：当前未取得 D/P1 与 D/P2";
  const coverage = metric.coverage;
  if (!coverage?.first_date) {
    $("dividendCoverage").textContent = "历史覆盖：暂无有效区间";
    return;
  }
  const clipped = coverage.requested_range_clipped
    ? ` · 未覆盖完整 ${metric.lookback_years} 年`
    : " · 已覆盖所选回看期";
  $("dividendCoverage").textContent = `历史覆盖：${formatDate(coverage.first_date)}—${formatDate(coverage.last_date)} · ${coverage.valid_month_count} 个有效月份 · 缺 ${coverage.missing_month_count} 月${clipped}`;
}

function renderRiskPremiumAudit(metric) {
  const audit = $("riskPremiumAudit");
  const visible = ["earnings_yield_premium", "dividend_yield_premium"].includes(metric?.id);
  audit.classList.toggle("hidden", !visible);
  if (!visible) return;
  $("riskPremiumFormula").textContent = `公式：${metric.formula || "暂无"}`;
  const components = metric.component_sources || [];
  $("riskPremiumSources").textContent = components.length
    ? `组成来源：${components.map((item) => `${item.role}（${item.name}）`).join(" · ")}`
    : "组成来源：暂无完整来源信息";
}

function renderHistory(metric) {
  const empty = !metric || !metric.history?.length;
  state.historyHover = null;
  hideHistoryHover();
  $("historyEmpty").classList.toggle("hidden", !empty);
  ["historyGrid", "historyAxes"].forEach((id) => $(id).replaceChildren());
  $("historyLine").setAttribute("points", ""); $("historyArea").setAttribute("d", "");
  if (empty) {
    renderDividendAudit(metric);
    renderRiskPremiumAudit(metric);
    $("sourceText").textContent = metric?.reason || "暂无可绘制数据";
    $("sampleText").textContent = "样本 0";
    return;
  }
  const points = metric.history;
  const values = points.map((point) => point.value);
  const min = Math.min(...values), max = Math.max(...values);
  const pad = Math.max((max - min) * 0.12, Math.max(Math.abs(min), Math.abs(max), 1) * 0.03);
  const low = metric.allow_negative ? min - pad : Math.max(0, min - pad), high = max + pad;
  const x0 = 42, x1 = 744, y0 = 18, y1 = 214;
  const x = (index) => x0 + index * (x1 - x0) / Math.max(1, points.length - 1);
  const y = (value) => y0 + (high - value) / Math.max(.0001, high - low) * (y1 - y0);
  const coords = points.map((point, index) => [x(index), y(point.value)]);
  state.historyHover = { metric, points, coords, x0, x1, y0, y1 };
  [0, .5, 1].forEach((ratio) => {
    const lineY = y0 + ratio * (y1 - y0);
    const line = document.createElementNS(svgNS, "line"); line.setAttribute("class", "gridline"); line.setAttribute("x1", x0); line.setAttribute("x2", x1); line.setAttribute("y1", lineY); line.setAttribute("y2", lineY); $("historyGrid").append(line);
    const text = document.createElementNS(svgNS, "text"); text.setAttribute("class", "axis-label"); text.setAttribute("x", 0); text.setAttribute("y", lineY + 3); text.textContent = (high - ratio * (high - low)).toFixed(1); $("historyAxes").append(text);
  });
  const medianValue = [...values].sort((a,b) => a-b)[Math.floor(values.length / 2)];
  Object.entries({x1:x0,x2:x1,y1:y(medianValue),y2:y(medianValue)}).forEach(([key,value]) => $("medianLine").setAttribute(key,value));
  $("historyLine").setAttribute("points", coords.map((point) => point.join(",")).join(" "));
  $("historyArea").setAttribute("d", `M ${coords[0][0]} ${y1} L ${coords.map((point) => point.join(" ")).join(" L ")} L ${coords.at(-1)[0]} ${y1} Z`);
  $("currentDot").setAttribute("cx", coords.at(-1)[0]); $("currentDot").setAttribute("cy", coords.at(-1)[1]);
  [0, Math.floor((points.length - 1) / 2), points.length - 1].forEach((index) => {
    const text = document.createElementNS(svgNS, "text"); text.setAttribute("class", "axis-label"); text.setAttribute("x", x(index) - 14); text.setAttribute("y", 242); text.textContent = points[index].date.slice(0,7); $("historyAxes").append(text);
  });
  $("chartMetric").textContent = metric.label;
  const frequencyLabels = { daily: "日", monthly: "月", quarterly: "季度", yearly: "年" };
  $("chartRange").textContent = `${points[0].date.slice(0,4)}—${points.at(-1).date.slice(0,4)} · ${frequencyLabels[metric.history_frequency] || "月"}`;
  const source = metric.source;
  const noUpsampling = metric.history_frequency === "daily" && points.length <= metric.sample_count + 1 ? " · 源仅有月级观测，不补日线" : "";
  const methodology = metric.methodology_status === "unconfirmed" ? " · 精确口径未确认" : "";
  const tierLabels = {official: "官方", aggregated: "公共聚合", derived: "计算指标"};
  $("sourceText").textContent = source ? `来源：${source.name} · ${tierLabels[source.tier] || source.tier}${methodology}${metric.estimated ? " · 最新值为估算" : ""}${noUpsampling}${metric.stale ? " · 过期缓存" : ""}` : "来源不可用";
  $("sampleText").textContent = `折线 ${points.length} 点 · 分位 ${metric.sample_count} 个月末样本 · 更新 ${formatDate(metric.date)}`;
  renderDividendAudit(metric);
  renderRiskPremiumAudit(metric);
}

function renderResearchError(error) {
  $("metrics").replaceChildren(); $("historyEmpty").classList.remove("hidden");
  showNotice("valuationNotice", `估值读取失败：${error.message}`, true);
  $("asOf").textContent = "未取得估值数据";
}

function renderReturns(payload) {
  const summary = payload.summary;
  $("medianReturn").textContent = formatPct(summary.median); $("averageReturn").textContent = formatPct(summary.average); $("standardDeviationReturn").textContent = formatPct(summary.standard_deviation); $("winRate").textContent = formatPct(summary.win_rate);
  $("worstReturn").textContent = formatPct(summary.worst); $("sampleCount").textContent = String(summary.count || 0);
  $("medianLabel").textContent = state.measure === "annualized" ? "年化收益中位数" : "累计收益中位数";
  $("averageLabel").textContent = state.measure === "annualized" ? "年化收益平均值" : "累计收益平均值";
  $("standardDeviationLabel").textContent = state.measure === "annualized" ? "年化收益标准差" : "累计收益标准差";
  renderReturnChart(payload.samples);
  const latestWindow = payload.latest_complete_start && payload.latest_complete_end
    ? `最近完整样本 ${formatDate(payload.latest_complete_start)} → ${formatDate(payload.latest_complete_end)}`
    : "暂无完整持有期样本";
  $("returnDates").textContent = `行情更新至 ${formatDate(payload.data_as_of)} · ${latestWindow}`;
  const sourceText = payload.source ? `${payload.source.name}（${payload.return_label}）` : "来源不可用";
  $("returnMethod").textContent = `收益口径：${sourceText}。图中只统计已经完整持有 ${state.years} 年的样本。${payload.warning || "历史结果不代表未来表现。"}${payload.stale ? " 当前使用过期缓存。" : ""}`;
  showNotice("returnNotice", payload.error || payload.warning || (payload.partial ? "数据只覆盖了部分请求区间。" : ""), Boolean(payload.error));
}

function renderReturnChart(samples) {
  state.returnHover = null;
  hideReturnHover();
  $("returnGrid").replaceChildren(); $("returnAxes").replaceChildren();
  $("returnLine").setAttribute("points", "");
  const empty = !samples?.length;
  $("returnEmpty").classList.toggle("hidden", !empty);
  $("returnCurrentDot").classList.toggle("hidden", empty);
  $("zeroLine").classList.toggle("hidden", empty);
  if (empty) return;
  const x0=38,x1=510,y0=14,y1=190, values=samples.map((sample)=>sample.value);
  const min=Math.min(0,...values),max=Math.max(0,...values),pad=Math.max(1,(max-min)*.1),low=min-pad,high=max+pad,span=high-low;
  const x=(index)=>x0+index*(x1-x0)/Math.max(1,samples.length-1),y=(value)=>y0+(high-value)/span*(y1-y0);
  const coords=samples.map((sample,index)=>[x(index),y(sample.value)]);
  state.returnHover={samples,coords,x0,x1,y0,y1};
  const zero=y(0); Object.entries({x1:x0,x2:x1,y1:zero,y2:zero}).forEach(([key,value])=>$("zeroLine").setAttribute(key,value));
  [0,.5,1].forEach((ratio)=>{const gy=y0+ratio*(y1-y0),line=document.createElementNS(svgNS,"line");line.setAttribute("class","gridline");line.setAttribute("x1",x0);line.setAttribute("x2",x1);line.setAttribute("y1",gy);line.setAttribute("y2",gy);$("returnGrid").append(line);const text=document.createElementNS(svgNS,"text");text.setAttribute("class","axis-label");text.setAttribute("x",0);text.setAttribute("y",gy+3);text.textContent=`${(high-ratio*span).toFixed(0)}%`;$("returnAxes").append(text)});
  $("returnLine").setAttribute("points",coords.map((point)=>point.join(",")).join(" "));
  $("returnCurrentDot").setAttribute("cx",coords.at(-1)[0]);$("returnCurrentDot").setAttribute("cy",coords.at(-1)[1]);
  [0,Math.floor((samples.length-1)/2),samples.length-1].forEach((index)=>{const text=document.createElementNS(svgNS,"text");text.setAttribute("class","axis-label");text.setAttribute("x",x(index)-12);text.setAttribute("y",222);text.textContent=samples[index].start_date.slice(0,7);$("returnAxes").append(text)});
}

function renderReturnsError(error) { renderReturnChart([]); $("returnDates").textContent="未取得行情日期"; showNotice("returnNotice", `收益读取失败：${error.message}`, true); ["medianReturn","averageReturn","standardDeviationReturn","winRate","worstReturn","sampleCount"].forEach((id)=>$(id).textContent="—"); }

function renderDca(payload) {
  const result = payload.result;
  if (!result) {
    renderDcaChart([]);
    ["dcaAnnualized", "dcaInvested", "dcaEnding", "dcaProfit"].forEach((id) => $(id).textContent = "—");
    showNotice("dcaNotice", payload.error || "没有足够历史数据完成这段回测。", Boolean(payload.error));
    return;
  }
  $("dcaAnnualized").textContent = formatPct(result.annualized_return);
  $("dcaInvested").textContent = formatMoney(result.total_invested, payload.currency);
  $("dcaEnding").textContent = formatMoney(result.ending_value, payload.currency);
  $("dcaProfit").textContent = `${formatMoney(result.profit, payload.currency)} · ${formatPct(result.cumulative_return)}`;
  $("dcaProfit").style.color = result.profit < 0 ? "var(--negative)" : "var(--positive)";
  const skipped = result.skipped_count ? ` · 跳过 ${result.skipped_count} 次` : "";
  $("dcaRange").textContent = `${formatDate(result.start_date)}—${formatDate(result.end_date)} · ${result.contribution_count} 次 · 顺延 ${result.adjusted_count} 次${skipped}`;
  renderDcaChart(result.curve);
  const source = payload.source ? `${payload.source.name}（${payload.return_label}）` : "来源不可用";
  const schedule = result.cadence === "monthly" ? `每月 ${result.schedule_value} 号` : `每${["周一", "周二", "周三", "周四", "周五", "周六", "周日"][result.schedule_value - 1]}`;
  $("dcaMethod").textContent = `来源：${source}。${schedule}投入 ${formatMoney(result.contribution_amount, payload.currency)}；${payload.assumptions.join("；")}。`;
  const clipped = result.range_clipped ? `行情覆盖限制了实际区间，使用 ${formatDate(result.start_date)} 至 ${formatDate(result.end_date)}。` : "";
  showNotice("dcaNotice", [payload.warning, payload.partial ? "数据只覆盖了部分请求区间。" : "", clipped].filter(Boolean).join(" "));
}

function renderDcaChart(curve) {
  $("dcaGrid").replaceChildren(); $("dcaAxes").replaceChildren();
  $("dcaValueLine").setAttribute("points", ""); $("dcaInvestedLine").setAttribute("points", "");
  const empty = !curve?.length;
  $("dcaEmpty").classList.toggle("hidden", !empty);
  if (empty) return;
  const x0 = 54, x1 = 744, y0 = 15, y1 = 200;
  const max = Math.max(...curve.flatMap((point) => [point.invested, point.portfolio_value]), 1);
  const x = (index) => x0 + index * (x1 - x0) / Math.max(1, curve.length - 1);
  const y = (value) => y1 - value / max * (y1 - y0);
  [0, .5, 1].forEach((ratio) => {
    const gy = y0 + ratio * (y1 - y0);
    const line = document.createElementNS(svgNS, "line");
    Object.entries({ class: "gridline", x1: x0, x2: x1, y1: gy, y2: gy }).forEach(([key, value]) => line.setAttribute(key, value));
    $("dcaGrid").append(line);
    const label = document.createElementNS(svgNS, "text");
    label.setAttribute("class", "axis-label"); label.setAttribute("x", 0); label.setAttribute("y", gy + 3);
    label.textContent = new Intl.NumberFormat("zh-CN", { notation: "compact", maximumFractionDigits: 1 }).format(max * (1 - ratio));
    $("dcaAxes").append(label);
  });
  $("dcaInvestedLine").setAttribute("points", curve.map((point, index) => `${x(index)},${y(point.invested)}`).join(" "));
  $("dcaValueLine").setAttribute("points", curve.map((point, index) => `${x(index)},${y(point.portfolio_value)}`).join(" "));
  [0, Math.floor((curve.length - 1) / 2), curve.length - 1].forEach((index) => {
    const label = document.createElementNS(svgNS, "text");
    label.setAttribute("class", "axis-label"); label.setAttribute("x", x(index) - 14); label.setAttribute("y", 230);
    label.textContent = curve[index].date.slice(0, 7); $("dcaAxes").append(label);
  });
  const title = document.createElementNS(svgNS, "title");
  const latest = curve.at(-1);
  title.textContent = `${latest.date}：累计投入 ${latest.invested.toFixed(0)}，组合市值 ${latest.portfolio_value.toFixed(0)}`;
  $("dcaValueLine").replaceChildren(title);
}

function renderDcaError(error) {
  renderDcaChart([]);
  ["dcaAnnualized", "dcaInvested", "dcaEnding", "dcaProfit"].forEach((id) => $(id).textContent = "—");
  showNotice("dcaNotice", `定投回测失败：${error.message}`, true);
}

async function loadDca() {
  setBusy("dca", true);
  $("dcaRunButton").disabled = true;
  showNotice("dcaNotice", "");
  try {
    const payload = await fetchJSON(`/api/indices/${state.indexId}/dca?${dcaQuery()}`);
    renderDca(payload);
  } catch (error) {
    renderDcaError(error);
  } finally {
    setBusy("dca", false);
    $("dcaRunButton").disabled = false;
  }
}

function resetValidation() {
  $("validationBadge").className = "validation-badge idle";
  $("validationBadge").textContent = "待核验";
  ["validationReference", "validationObserved", "validationDifference"].forEach((id) => $(id).textContent = "—");
  $("validationConclusion").textContent = "选择参考日期和值后开始核验。";
  $("validationMethod").textContent = "核验会同时检查日期、数值容差和口径可确认性。";
}

async function runValidation() {
  const referenceValue = Number($("validationValue").value);
  const referenceDate = $("validationDate").value;
  if (!Number.isFinite(referenceValue) || referenceValue <= 0 || !referenceDate) {
    $("validationConclusion").textContent = "请先填写有效的参考日期和正数参考值。";
    return;
  }
  const button = $("validationButton");
  button.disabled = true; button.textContent = "核验中…";
  const query = new URLSearchParams({
    metric_id: $("validationMetric").value,
    reference_value: String(referenceValue), reference_date: referenceDate,
    reference_source: $("validationSource").value || "用户参考",
    tolerance_pct: $("validationTolerance").value || "2",
  });
  try {
    const payload = await fetchJSON(`/api/indices/${state.indexId}/validation?${query}`);
    $("validationBadge").className = `validation-badge ${payload.status}`;
    const labels = { consistent: "数值一致", source_mismatch: "数值偏离", date_mismatch: "日期不匹配", unavailable: "不可核验" };
    $("validationBadge").textContent = labels[payload.status] || payload.status;
    $("validationReference").textContent = payload.reference ? Number(payload.reference.value).toFixed(2) : "—";
    $("validationObserved").textContent = payload.observed ? `${Number(payload.observed.value).toFixed(2)} · ${formatDate(payload.observed.date)}` : "—";
    $("validationDifference").textContent = payload.difference_pct == null ? "—" : `${payload.difference_pct.toFixed(2)}%`;
    $("validationConclusion").textContent = payload.conclusion || payload.reason;
    const observedSource = payload.observed?.source?.name ? `本工具来源：${payload.observed.source.name}。` : "";
    const estimate = payload.observed?.estimated ? "本工具观测为估算值。" : "";
    $("validationMethod").textContent = `${observedSource}${payload.methodology_note || ""}${estimate} 口径状态：${payload.definition_status === "unknown" ? "未确认" : payload.definition_status || "未知"}。`;
  } catch (error) {
    $("validationBadge").className = "validation-badge source_mismatch";
    $("validationBadge").textContent = "核验失败";
    $("validationConclusion").textContent = error.message;
  } finally {
    button.disabled = false; button.textContent = "开始核验";
  }
}

async function loadFutuSample() {
  state.indexId = "sp500"; state.metricId = "pe";
  $("indexSelect").value = "sp500";
  $("validationMetric").value = "pe";
  $("validationSource").value = "富途 App（用户观察）";
  $("validationDate").value = "2026-09-04";
  $("validationValue").value = "26.12";
  $("validationTolerance").value = "2";
  await loadAll();
  await runValidation();
  $("validation").scrollIntoView({ behavior: "smooth", block: "center" });
}

function hideHistoryHover() {
  $("historyHoverLine")?.classList.add("hidden");
  $("historyHoverHorizontal")?.classList.add("hidden");
  $("historyHoverDot")?.classList.add("hidden");
  $("historyTooltip")?.classList.add("hidden");
}

function updateHistoryHover(event) {
  const hover = state.historyHover;
  if (!hover) return;
  const svg = $("historySvg");
  const svgRect = svg.getBoundingClientRect();
  if (!svgRect.width) return;
  const viewX = (event.clientX - svgRect.left) / svgRect.width * 760;
  const ratio = Math.max(0, Math.min(1, (viewX - hover.x0) / (hover.x1 - hover.x0)));
  const index = Math.round(ratio * (hover.points.length - 1));
  const point = hover.points[index];
  const [pointX, pointY] = hover.coords[index];
  const line = $("historyHoverLine");
  Object.entries({x1:pointX,x2:pointX,y1:hover.y0,y2:hover.y1}).forEach(([key,value]) => line.setAttribute(key,value));
  const horizontal = $("historyHoverHorizontal");
  Object.entries({x1:hover.x0,x2:hover.x1,y1:pointY,y2:pointY}).forEach(([key,value]) => horizontal.setAttribute(key,value));
  $("historyHoverDot").setAttribute("cx", pointX);
  $("historyHoverDot").setAttribute("cy", pointY);
  line.classList.remove("hidden");
  horizontal.classList.remove("hidden");
  $("historyHoverDot").classList.remove("hidden");

  const tooltip = $("historyTooltip");
  tooltip.replaceChildren();
  const title = document.createElement("b");
  title.textContent = `${point.value.toFixed(hover.metric.id === "dividend_yield" ? 2 : 2)}${hover.metric.unit}`;
  const detail = document.createElement("span");
  detail.textContent = `${hover.metric.label} · ${formatDate(point.date)}`;
  tooltip.append(title, detail);
  tooltip.classList.remove("hidden");
  const wrapRect = tooltip.parentElement.getBoundingClientRect();
  const desiredLeft = event.clientX - wrapRect.left + 12;
  const desiredTop = event.clientY - wrapRect.top - 12;
  tooltip.style.left = `${Math.max(8, Math.min(wrapRect.width - tooltip.offsetWidth - 8, desiredLeft))}px`;
  tooltip.style.top = `${Math.max(32, Math.min(wrapRect.height - tooltip.offsetHeight - 8, desiredTop))}px`;
}

function hideReturnHover() {
  $("returnHoverLine")?.classList.add("hidden");
  $("returnHoverHorizontal")?.classList.add("hidden");
  $("returnHoverDot")?.classList.add("hidden");
  $("returnTooltip")?.classList.add("hidden");
  $("returnTooltip")?.setAttribute("aria-hidden", "true");
}

function updateReturnHover(event) {
  const hover = state.returnHover;
  if (!hover) return;
  const svg = $("returnSvg");
  const svgRect = svg.getBoundingClientRect();
  if (!svgRect.width) return;
  const viewX = (event.clientX - svgRect.left) / svgRect.width * 520;
  const ratio = Math.max(0, Math.min(1, (viewX - hover.x0) / (hover.x1 - hover.x0)));
  const index = Math.round(ratio * (hover.samples.length - 1));
  const sample = hover.samples[index];
  const [pointX, pointY] = hover.coords[index];
  const vertical = $("returnHoverLine");
  Object.entries({x1:pointX,x2:pointX,y1:hover.y0,y2:hover.y1}).forEach(([key,value])=>vertical.setAttribute(key,value));
  const horizontal = $("returnHoverHorizontal");
  Object.entries({x1:hover.x0,x2:hover.x1,y1:pointY,y2:pointY}).forEach(([key,value])=>horizontal.setAttribute(key,value));
  $("returnHoverDot").setAttribute("cx",pointX);$("returnHoverDot").setAttribute("cy",pointY);
  [vertical,horizontal,$("returnHoverDot")].forEach((element)=>element.classList.remove("hidden"));

  const tooltip = $("returnTooltip");
  tooltip.replaceChildren();
  const title = document.createElement("b");title.textContent=formatPct(sample.value);
  const start = document.createElement("span");start.textContent=`买入 ${formatDate(sample.start_date)}`;
  const end = document.createElement("span");end.textContent=`结束 ${formatDate(sample.end_date)}`;
  tooltip.append(title,start,end);tooltip.classList.remove("hidden");tooltip.setAttribute("aria-hidden","false");
  const wrapRect=tooltip.parentElement.getBoundingClientRect(),desiredLeft=event.clientX-wrapRect.left+12,desiredTop=event.clientY-wrapRect.top-12;
  tooltip.style.left=`${Math.max(8,Math.min(wrapRect.width-tooltip.offsetWidth-8,desiredLeft))}px`;
  tooltip.style.top=`${Math.max(8,Math.min(wrapRect.height-tooltip.offsetHeight-8,desiredTop))}px`;
}

async function refreshCurrent() {
  const requestToken=++state.requestToken;
  let completionLabel="刷新";
  const button=$("refreshButton");button.disabled=true;button.textContent="刷新中…";showNotice("valuationNotice","正在按当前选项从远端更新，可能需要十几秒。");
  const query=new URLSearchParams({lookback_years:String(state.lookback),history_frequency:state.historyFrequency,frequency:state.frequency,holding_years:String(state.years),measure:state.measure,dca_amount:String(state.contributionAmount),dca_start_date:state.dcaStartDate,dca_end_date:state.dcaEndDate,dca_cadence:state.dcaCadence,dca_schedule_value:String(state.dcaScheduleValue)});
  try { const payload=await fetchJSON(`/api/refresh/${state.indexId}?${query}`,{method:"POST"}); if(requestToken!==state.requestToken)return; renderResearch(payload.research); renderReturns(payload.returns); renderDca(payload.dca); const stale=payload.returns.stale||payload.dca.stale||payload.research.metrics.some((metric)=>metric.stale);completionLabel=stale?"使用缓存":"已更新"; }
  catch(error){showNotice("valuationNotice",`刷新失败：${error.message}`,true)}
  finally{button.disabled=false;button.textContent=completionLabel;if(completionLabel!=="刷新")setTimeout(()=>{button.textContent="刷新"},1400)}
}

$("indexSelect").addEventListener("change", (event) => { state.indexId=event.target.value; state.metricId="pe"; resetValidation(); loadAll(); });
$("lookbackSelect").addEventListener("change", (event) => { state.lookback=Number(event.target.value); loadAll(); });
$("historyFrequencySelect").addEventListener("change", (event) => { state.historyFrequency=event.target.value; loadAll(); });
$("frequency").addEventListener("click", (event) => { if(event.target.tagName!=="BUTTON")return; $("frequency").querySelectorAll("button").forEach((button)=>button.classList.remove("active"));event.target.classList.add("active");state.frequency=event.target.dataset.value;loadAll(); });
$("years").addEventListener("click", (event) => { if(event.target.tagName!=="BUTTON")return; $("years").querySelectorAll("button").forEach((button)=>button.classList.remove("active"));event.target.classList.add("active");state.years=Number(event.target.dataset.value);loadAll(); });
$("measureButton").addEventListener("click", (event) => { state.measure=state.measure==="annualized"?"cumulative":"annualized";event.target.dataset.measure=state.measure;event.target.textContent=state.measure==="annualized"?"年化收益":"累计收益";loadAll(); });
$("dcaStartDate").addEventListener("change", (event) => { state.dcaStartDate=event.target.value; });
$("dcaEndDate").addEventListener("change", (event) => { state.dcaEndDate=event.target.value; });
$("dcaCadence").addEventListener("change", (event) => { state.dcaCadence=event.target.value; rebuildDcaScheduleOptions(); });
$("dcaScheduleValue").addEventListener("change", (event) => { state.dcaScheduleValue=Number(event.target.value); });
$("contributionAmountInput").addEventListener("change", (event) => { state.contributionAmount=Number(event.target.value); });
$("dcaRunButton").addEventListener("click", () => {
  state.dcaStartDate=$("dcaStartDate").value;
  state.dcaEndDate=$("dcaEndDate").value;
  state.dcaCadence=$("dcaCadence").value;
  state.dcaScheduleValue=Number($("dcaScheduleValue").value);
  state.contributionAmount=Number($("contributionAmountInput").value);
  loadDca();
});
$("validationButton").addEventListener("click", runValidation);
$("futuSampleButton").addEventListener("click", loadFutuSample);
$("refreshButton").addEventListener("click", refreshCurrent);
$("methodButton").addEventListener("click", ()=>$("methodDialog").showModal());
$("historySvg").addEventListener("pointermove", updateHistoryHover);
$("historySvg").addEventListener("pointerdown", updateHistoryHover);
$("historySvg").addEventListener("pointerleave", hideHistoryHover);
$("returnSvg").addEventListener("pointermove", updateReturnHover);
$("returnSvg").addEventListener("pointerdown", updateReturnHover);
$("returnSvg").addEventListener("pointerleave", hideReturnHover);

bootstrap();
