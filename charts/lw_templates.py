"""LW 시간 라벨·상호작용 JavaScript 원문. iframe 안에서만 실행된다."""

TIME_FORMAT_JS = """
function lwPad(n) { return (n < 10 ? '0' : '') + n; }
function lwParts(t) {
  var sec = (typeof t === 'number') ? t : (t && t.timestamp !== undefined ? t.timestamp
            : Date.UTC(t.year, t.month - 1, t.day) / 1000);
  var d = new Date(sec * 1000);
  return { y: d.getUTCFullYear(), m: lwPad(d.getUTCMonth() + 1), d: lwPad(d.getUTCDate()),
           h: lwPad(d.getUTCHours()), mi: lwPad(d.getUTCMinutes()), s: lwPad(d.getUTCSeconds()) };
}
function lwYmd(p) { return p.y + '-' + p.m + '-' + p.d; }
function lwTooltipTime(t) { var p = lwParts(t); return TOOLTIP_CLOCK ? lwYmd(p) + ' ' + p.h + ':' + p.mi : lwYmd(p); }
function lwTickMark(t, type) {
  var p = lwParts(t);
  if (type === 0) return String(p.y);
  if (type === 1) return p.y + '-' + p.m;
  if (type === 2) return p.m + '-' + p.d;
  if (type === 3) return p.h + ':' + p.mi;
  return p.h + ':' + p.mi + ':' + p.s;
}
"""


_JS_TEMPLATE = """
(function () {
  var LWC = LightweightCharts;
  var el = document.getElementById('lw-chart');
  var chart = LWC.createChart(el, OPTS);
  // 시간 표기: JSON 옵션에는 함수를 못 실으므로 생성 뒤 적용 (TIME_FORMAT_JS)
  chart.applyOptions({ localization: { timeFormatter: lwTooltipTime },
                       timeScale: { tickMarkFormatter: lwTickMark } });
  var LINE_BASE = { priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false };
  function line(opts, pane) { return chart.addSeries(LWC.LineSeries, Object.assign({}, LINE_BASE, opts), pane); }
  function guide(series, price, color, style) {
    series.createPriceLine({ price: price, color: color, lineWidth: 1, lineStyle: style, axisLabelVisible: false, title: '' });
  }
  // 고정 스케일 pane(스토캐 0~320 · RSI 0~100): autoScale 을 끄고 setVisibleRange 로 못 박는다.
  // (autoscale 은 마커 여백을 더해 범위를 넓히므로 Plotly 의 고정 range 와 달라진다.) 축 더블클릭으로
  // autoScale 이 켜져도 모든 시리즈에 같은 범위의 provider 를 걸어 크게 벗어나지 않게 한다.
  var fixedScales = [];
  function fixedRange(seriesList, lo, hi, margin) {
    var provider = function () { return { priceRange: { minValue: lo, maxValue: hi }, margins: { above: 0, below: 0 } }; };
    seriesList.forEach(function (s) { s.applyOptions({ autoscaleInfoProvider: provider }); });
    var scale = seriesList[0].priceScale();
    scale.applyOptions({ autoScale: false, scaleMargins: { top: margin, bottom: margin } });
    fixedScales.push({ scale: scale, lo: lo, hi: hi });
  }
  function applyFixedScales() {
    fixedScales.forEach(function (f) { try { f.scale.setVisibleRange({ from: f.lo, to: f.hi }); } catch (e) {} });
  }
  // 영역 음영: BaselineSeries(baseValue=임계값). 위 구간(side='above')은 top 채움만, 아래 구간은 bottom 채움만
  // 켜고 선은 숨긴다 → 시리즈와 임계선 사이만 채워져 plotly 의 add_masked_fill_segments 와 같은 모양.
  var TRANSPARENT = 'rgba(0,0,0,0)';
  function zoneFill(data, base, side, color, pane) {
    var above = side === 'above';
    var s = chart.addSeries(LWC.BaselineSeries, Object.assign({}, LINE_BASE, {
      baseValue: { type: 'price', price: base }, lineVisible: false, lineWidth: 1,
      topLineColor: TRANSPARENT, bottomLineColor: TRANSPARENT,
      topFillColor1: above ? color : TRANSPARENT, topFillColor2: above ? color : TRANSPARENT,
      bottomFillColor1: above ? TRANSPARENT : color, bottomFillColor2: above ? TRANSPARENT : color,
    }), pane);
    s.setData(data);
    return s;
  }
  var paneOf = {};
  PANES.forEach(function (p, i) { paneOf[p.kind] = i; });

  // ---- pane 0: 가격 + 이평 + 거래량 오버레이 + 구조 기준선
  var candles = chart.addSeries(LWC.CandlestickSeries, CANDLE_OPTS, 0);
  candles.setData(PAYLOAD.candles);
  var volume = chart.addSeries(LWC.HistogramSeries, {
    priceFormat: { type: 'volume' }, priceScaleId: 'volume', lastValueVisible: false, priceLineVisible: false,
  }, 0);
  volume.priceScale().applyOptions({ scaleMargins: { top: VOLUME_TOP, bottom: 0 } });
  volume.setData(PAYLOAD.volume);
  var maSeries = {};
  Object.keys(PAYLOAD.mas).forEach(function (period) {
    var s = MA_STYLES[period] || { color: '#888888', width: 1, style: 0 };
    var ser = line({ color: s.color, lineWidth: s.width, lineStyle: s.style }, 0);
    ser.setData(PAYLOAD.mas[period]);
    maSeries[period] = ser;
  });
  STRUCT_LINES.forEach(function (l) {
    candles.createPriceLine({ price: l.price, color: l.color, lineWidth: 1, lineStyle: l.style,
                              axisLabelVisible: true, title: l.title });
  });

  // ---- pane 스토캐 3중 (한 pane 에 오프셋 배치, 층당 20/80, 분리선 2)
  var stochK = {}, stochD = {}, stochZones = [], rsiZones = [];
  if (PAYLOAD.stoch && paneOf.stoch !== undefined) {
    var sp = paneOf.stoch, anchor = null;
    PAYLOAD.stoch.layers.forEach(function (L) {
      // 음영은 선보다 먼저 추가(아래 레이어) — 층별 임계값 = 20/80 + 오프셋 (guides 와 동일)
      stochZones.push(zoneFill(L.k, L.guides[1], 'above', ZONE_FILL.stoch_overbought, sp));
      stochZones.push(zoneFill(L.k, L.guides[0], 'below', ZONE_FILL.stoch_oversold, sp));
      var k = line({ color: L.k_color, lineWidth: 1 }, sp); k.setData(L.k);
      var d = line({ color: L.d_color, lineWidth: 1 }, sp); d.setData(L.d);
      L.guides.forEach(function (g) { guide(k, g, STOCH_GUIDE_COLOR, 2); });
      stochK[L.label] = k; stochD[L.label] = d;
      if (!anchor) anchor = k;
    });
    PAYLOAD.stoch.separators.forEach(function (s) { guide(anchor, s, STOCH_SEP_COLOR, 0); });
    fixedRange(Object.keys(stochK).map(function (k) { return stochK[k]; })
               .concat(Object.keys(stochD).map(function (k) { return stochD[k]; }), stochZones), 0, PAYLOAD.stoch.max_y, 0.02);
  }

  // ---- pane MACD: hist + macd/signal + 0선
  var macdLine = null, macdHist = null, macdSignal = null;
  if (PAYLOAD.macd && paneOf.macd !== undefined) {
    var mp = paneOf.macd;
    macdHist = chart.addSeries(LWC.HistogramSeries, { priceLineVisible: false, lastValueVisible: false, base: 0 }, mp);
    macdHist.setData(PAYLOAD.macd.hist);
    macdLine = line({ color: MACD_COLORS.macd, lineWidth: 1 }, mp); macdLine.setData(PAYLOAD.macd.macd);
    macdSignal = line({ color: MACD_COLORS.signal, lineWidth: 1 }, mp); macdSignal.setData(PAYLOAD.macd.signal);
    guide(macdLine, 0, STOCH_GUIDE_COLOR, 2);
    // 가격 pane 의 8%/22% 마진(거래량 띠용)을 물려받지 않게 하위 pane 은 대칭 마진
    macdLine.priceScale().applyOptions({ scaleMargins: { top: 0.1, bottom: 0.1 } });
  }

  // ---- pane RSI: 라인 + 30/50/70
  var rsiLine = null;
  if (PAYLOAD.rsi && paneOf.rsi !== undefined) {
    var rp = paneOf.rsi;
    rsiZones = [
      zoneFill(PAYLOAD.rsi.line, PAYLOAD.zones.rsi.high, 'above', ZONE_FILL.rsi_overbought, rp),
      zoneFill(PAYLOAD.rsi.line, PAYLOAD.zones.rsi.low, 'below', ZONE_FILL.rsi_oversold, rp),
    ];
    rsiLine = line({ color: RSI_COLOR, lineWidth: 1 }, rp); rsiLine.setData(PAYLOAD.rsi.line);
    PAYLOAD.rsi.guides.forEach(function (g) { guide(rsiLine, g.value, g.color, g.style); });
    fixedRange([rsiLine].concat(rsiZones), 0, 100, 0.05);
  }

  // ---- 알람 마커 (createSeriesMarkers) — 텍스트 라벨 유지, 확정 봉 위치
  var M = PAYLOAD.markers || { stoch: {}, rsi: [], macd: [] };
  Object.keys(M.stoch).forEach(function (label) {
    if (stochK[label] && M.stoch[label].length) LWC.createSeriesMarkers(stochK[label], M.stoch[label]);
  });
  if (rsiLine && M.rsi.length) LWC.createSeriesMarkers(rsiLine, M.rsi);
  if (macdLine && M.macd.length) LWC.createSeriesMarkers(macdLine, M.macd);
  // ---- 가격 pane 구조 마커(추세 구조 추적, 미검증): 스윙 고점·저점 HH/HL/LH/LL — 없으면 아무것도 안 그린다
  if (STRUCTURE_MARKERS.length) LWC.createSeriesMarkers(candles, STRUCTURE_MARKERS);

  // ---- 크로스헤어 정보 오버레이: 커서 봉의 시/고/저/종·직전 종가 대비 변화율 + 하위 pane 값.
  //      값은 PAYLOAD(시간→값 맵)에서 읽으므로 hover 와 '커서 밖 = 마지막 봉' 이 같은 경로다.
  function tmap(arr) { var m = {}; (arr || []).forEach(function (p) { m[p.time] = p.value; }); return m; }
  var candleAt = {}, candleIdx = {};
  PAYLOAD.candles.forEach(function (c, i) { candleAt[c.time] = c; candleIdx[c.time] = i; });
  var subMaps = { stoch: [], macd: null, rsi: null };
  if (PAYLOAD.stoch) PAYLOAD.stoch.layers.forEach(function (L) {
    subMaps.stoch.push({ label: L.label, offset: L.offset, k: tmap(L.k), d: tmap(L.d) });
  });
  if (PAYLOAD.macd) subMaps.macd = { macd: tmap(PAYLOAD.macd.macd), signal: tmap(PAYLOAD.macd.signal), hist: tmap(PAYLOAD.macd.hist) };
  if (PAYLOAD.rsi) subMaps.rsi = tmap(PAYLOAD.rsi.line);
  var fmtPrice = function (v) { try { return candles.priceFormatter().format(v); } catch (e) { return String(v); } };
  function fmt1(v) { return (v === undefined || v === null || isNaN(v)) ? '—' : (Math.round(v * 10) / 10).toFixed(1); }
  function span(text, color) { return '<span style="color:' + color + '">' + text + '</span>'; }
  function renderInfo(time) {
    var c = candleAt[time];
    var box = document.getElementById('lw-ohlc');
    if (!c) { box.innerHTML = ''; return; }
    var i = candleIdx[time], prev = i > 0 ? PAYLOAD.candles[i - 1].close : null;
    var chg = (prev && prev !== 0) ? (c.close - prev) / prev * 100 : null;
    var up = chg === null ? (c.close >= c.open) : chg >= 0;
    var col = up ? CANDLE_OPTS.upColor : CANDLE_OPTS.downColor;
    var chgText = chg === null ? '' : ' ' + span((chg >= 0 ? '+' : '') + chg.toFixed(2) + '%', col);
    var line1 = lwTooltipTime(time) + ' · 시 ' + fmtPrice(c.open) + ' 고 ' + fmtPrice(c.high)
              + ' 저 ' + fmtPrice(c.low) + ' 종 ' + span(fmtPrice(c.close), col) + chgText;
    var parts = [];
    if (subMaps.stoch.length && paneOf.stoch !== undefined) {
      parts.push('스토캐 K ' + subMaps.stoch.map(function (L) {
        var k = L.k[time]; return L.label + ' ' + fmt1(k === undefined ? undefined : k - L.offset);
      }).join(' · '));
    }
    if (subMaps.macd && paneOf.macd !== undefined) {
      parts.push('MACD ' + fmt1(subMaps.macd.macd[time]) + ' / 신호 ' + fmt1(subMaps.macd.signal[time])
                 + ' / 히스토 ' + fmt1(subMaps.macd.hist[time]));
    }
    if (subMaps.rsi && paneOf.rsi !== undefined) parts.push('RSI ' + fmt1(subMaps.rsi[time]));
    box.innerHTML = line1 + (parts.length ? '<br>' + parts.join(' · ') : '');
  }
  var lastTime = PAYLOAD.candles.length ? PAYLOAD.candles[PAYLOAD.candles.length - 1].time : null;
  chart.subscribeCrosshairMove(function (param) {
    var t = (param && param.time !== undefined && candleAt[param.time]) ? param.time : lastTime;
    renderInfo(t);
  });
  renderInfo(lastTime);

  // ---- pane 비중 (지표 중심 근사) — 경계 드래그로 사용자가 바꿀 수 있다
  var panes = chart.panes();
  PANES.forEach(function (p, i) { if (panes[i]) panes[i].setStretchFactor(p.stretch); });

  // ---- 세로 줌 (가격 pane): 가격축 위 휠 → 고정 범위(autoscaleInfoProvider 오버라이드),
  //      가격축 더블클릭 → autoScale 복귀. 차트 본체 휠은 건드리지 않는다(LW 시간축 줌 그대로).
  var wrap = document.getElementById('lw-wrap');
  var priceSeries = [candles].concat(Object.keys(maSeries).map(function (k) { return maSeries[k]; }));
  var vz = { active: false, lo: null, hi: null };
  function priceAxisWidth() { try { return chart.priceScale('right').width(); } catch (e) { return 0; } }
  function pricePaneHeight() { var p = chart.panes(); return p.length ? p[0].getHeight() : el.clientHeight; }
  function overPriceAxis(e) {
    var r = el.getBoundingClientRect();
    var x = e.clientX - r.left, y = e.clientY - r.top;
    return x >= r.width - priceAxisWidth() && y >= 0 && y <= pricePaneHeight();
  }
  function applyFixed(lo, hi) {
    if (!(hi > lo)) return;
    vz.active = true; vz.lo = lo; vz.hi = hi;
    var provider = function () { return { priceRange: { minValue: lo, maxValue: hi }, margins: { above: 0, below: 0 } }; };
    priceSeries.forEach(function (s) { s.applyOptions({ autoscaleInfoProvider: provider }); });
    candles.priceScale().applyOptions({ scaleMargins: { top: 0, bottom: 0 }, autoScale: true });
  }
  function resetVertical() {
    vz.active = false; vz.lo = null; vz.hi = null;
    priceSeries.forEach(function (s) { s.applyOptions({ autoscaleInfoProvider: undefined }); });
    candles.priceScale().applyOptions({ scaleMargins: OPTS.rightPriceScale.scaleMargins, autoScale: true });
  }
  wrap.addEventListener('wheel', function (e) {
    if (!overPriceAxis(e)) return;                       // 본체 휠 = LW 시간축 줌
    e.preventDefault(); e.stopPropagation();
    var h = pricePaneHeight();
    var top = candles.coordinateToPrice(0), bottom = candles.coordinateToPrice(h);
    if (top === null || bottom === null) return;
    var y = e.clientY - el.getBoundingClientRect().top;
    var at = candles.coordinateToPrice(Math.max(0, Math.min(h, y)));
    if (at === null) at = (top + bottom) / 2;
    var f = e.deltaY < 0 ? VZOOM_IN : VZOOM_OUT;        // 위로 굴리면 확대
    applyFixed(at - (at - bottom) * f, at + (top - at) * f);
  }, { capture: true, passive: false });
  wrap.addEventListener('dblclick', function (e) { if (overPriceAxis(e)) resetVertical(); }, true);

  // ---- pane 단독 확대 모드: stretch factor 만 재배분 (rerun 없음 → 줌·팬·세로 줌 상태 유지).
  //      나머지 pane 은 SOLO_COLLAPSED_PX 띠로 접는다(0 높이는 쓰지 않음). '전체' 로 초기 비중 복원.
  //      단독 진입 시 컨테이너(#lw-wrap)와 iframe 높이를 접힌 띠 합계만큼 늘려 선택 pane 이 전체 모드의
  //      pane 영역 전체를 차지하게 하고, 전체 복귀 시 원래 높이로 되돌린다. 접힌 띠 위에는 pane 이름만 얹는다(클릭 → 그 pane 단독).
  var solo = { kind: SOLO_ALL, baseHeight: wrap.clientHeight };
  var frameEl = null;
  try { frameEl = window.frameElement; } catch (e) { frameEl = null; }   // 교차 출처면 null → iframe 확장 생략
  function setContainerHeight(h) {
    wrap.style.height = h + 'px';
    if (!frameEl) return;
    frameEl.style.height = h + 'px'; frameEl.setAttribute('height', String(h));
    // Streamlit 요소 컨테이너(stElementContainer)는 flex: 0 0 <height>px 로 고정돼 있어 iframe 만 키우면 아래
    // 캡션과 겹친다 → 인라인으로 같은 값을 준다(전체 복귀 시 base 로 되돌림).
    var holder = frameEl.parentElement;
    if (holder) { holder.style.height = h + 'px'; holder.style.flexBasis = h + 'px'; }
  }
  var strips = {};
  var stripBox = document.getElementById('lw-strips');
  PANES.forEach(function (p) {
    var d = document.createElement('div');
    d.className = 'lw-strip'; d.setAttribute('data-kind', p.kind); d.textContent = PANE_LABELS[p.kind] || p.kind;
    d.style.display = 'none';
    d.addEventListener('click', function () { applySolo(p.kind); });
    stripBox.appendChild(d); strips[p.kind] = d;
  });
  function layoutStrips() {
    var panes = chart.panes(), wr = wrap.getBoundingClientRect();
    PANES.forEach(function (p, i) {
      var d = strips[p.kind];
      if (!panes[i] || solo.kind === SOLO_ALL || p.kind === solo.kind) { d.style.display = 'none'; return; }
      var r = panes[i].getHTMLElement().getBoundingClientRect();
      d.style.display = 'block';
      d.style.top = (r.top - wr.top) + 'px'; d.style.left = (r.left - wr.left) + 'px';
      d.style.width = r.width + 'px'; d.style.height = r.height + 'px'; d.style.lineHeight = r.height + 'px';
    });
  }
  function applySolo(kind) {
    var panes = chart.panes();
    var total = panes.reduce(function (a, p) { return a + p.getHeight(); }, 0);
    var others = Math.max(0, PANES.length - 1);
    var extra = kind === SOLO_ALL ? 0 : SOLO_COLLAPSED_PX * others;
    // 전체 모드의 pane 영역 = 선택 pane 이 가질 수 있는 최대 → 컨테이너를 띠 합계만큼 늘려 그 크기를 보장
    var fullArea = solo.kind === SOLO_ALL ? total : total - SOLO_COLLAPSED_PX * others;
    setContainerHeight(solo.baseHeight + extra);
    PANES.forEach(function (p, i) {
      if (!panes[i]) return;
      if (kind === SOLO_ALL) { panes[i].setStretchFactor(p.stretch); return; }
      // stretch 는 상대값 — 목표 px 를 그대로 factor 로 주면 비례 배분이 정확히 px 가 된다
      panes[i].setStretchFactor(p.kind === kind ? Math.max(1, fullArea) : SOLO_COLLAPSED_PX);
    });
    solo.kind = kind;
    var btns = document.querySelectorAll('#lw-solo button');
    for (var b = 0; b < btns.length; b++) btns[b].classList.toggle('on', btns[b].getAttribute('data-kind') === kind);
    // 가격 pane 이 접히면 캡션·버튼 줄을 띠 아래로 내려 '가격' 띠 이름과 겹치지 않게 한다
    var overlayTop = (kind !== SOLO_ALL && kind !== 'price') ? (SOLO_COLLAPSED_PX + 6) : 6;
    document.getElementById('lw-caption').style.top = overlayTop + 'px';
    document.getElementById('lw-ohlc').style.top = (overlayTop + OHLC_OFFSET) + 'px';
    document.getElementById('lw-solo').style.top = overlayTop + 'px';
    applyFixedScales();
    layoutStrips();
    requestAnimationFrame(layoutStrips);   // autoSize(ResizeObserver) 반영 뒤 한 번 더
  }
  var soloBtns = document.querySelectorAll('#lw-solo button');
  for (var bi = 0; bi < soloBtns.length; bi++) {
    soloBtns[bi].addEventListener('click', function (ev) { applySolo(ev.currentTarget.getAttribute('data-kind')); });
  }
  if (window.ResizeObserver) { new ResizeObserver(function () { requestAnimationFrame(layoutStrips); }).observe(el); }
  wrap.addEventListener('mouseup', function () { requestAnimationFrame(layoutStrips); });   // 경계 드래그 뒤 재배치

  var n = PAYLOAD.candles.length;
  if (n > WINDOW) { chart.timeScale().setVisibleLogicalRange({ from: n - WINDOW, to: n + 2 }); }
  else { chart.timeScale().fitContent(); }
  applyFixedScales();
  window.__lw = { chart: chart, candles: candles, volume: volume, mas: maSeries, panes: PANES,
                  stochK: stochK, stochD: stochD, macd: macdLine, macdHist: macdHist, macdSignal: macdSignal,
                  rsi: rsiLine, vzoom: vz, resetVertical: resetVertical, overPriceAxis: overPriceAxis,
                  solo: solo, applySolo: applySolo, stochZones: stochZones, rsiZones: rsiZones,
                  strips: strips, layoutStrips: layoutStrips, frameEl: frameEl,
                  renderInfo: renderInfo };  // 검증·측정용 핸들
})();
"""
