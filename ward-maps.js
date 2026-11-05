/* Interactive 2026 municipal ward map. Boundary data: MDB 2026.
 * Vote shares: ESP's preliminary IEC-derived ward ballot via results.json.
 * A leading party here is NOT a declared winning councillor.
 */
(function () {
  'use strict';

  const spec = {
    'Cape Town': {slug: 'cape-town', count: 118, query: 'Cape Town', centre: [-33.925, 18.5], zoom: 10},
    'Tshwane': {slug: 'tshwane', count: 107, query: 'Tshwane', centre: [-25.75, 28.23], zoom: 10},
    'Johannesburg': {slug: 'johannesburg', count: 135, query: 'Johannesburg', centre: [-26.20, 28.05], zoom: 10},
    'Hermanus': {slug: 'overstrand', count: 15, query: 'Overstrand', centre: [-34.4200, 19.2420], zoom: 10}
  };
  const endpoints = [
    'https://services7.arcgis.com/oeoyTUJC8HEeYsRB/arcgis/rest/services/MDBWards2026/FeatureServer/0/query',
    'https://hips-gis.health.gov.za/server/rest/services/Hosted/MDB_Wards_2026/FeatureServer/0/query'
  ];
  const palette = {
    'ANC': '#32b567', 'DA': '#2386e5', 'EFF': '#e24c63', 'ActionSA': '#20b6b0',
    'PA': '#e6a144', 'FF+': '#b882e9', 'MK': '#8094e2',
    'IFP': '#e2c35a', 'GOOD': '#e581c9', 'ACDP': '#7c85f7',
    'Al Jama-ah': '#7bb5a0', 'CCC': '#d6ac76', 'UDM': '#c07abf',
    'BOSA': '#87acda'
  };
  const unknown = '#8897a8';
  const statusColors = {complete: '#39b99c', partial: '#e6ae45', none: '#8897a8'};
  const els = {
    map: document.getElementById('ward-detail-map'),
    side: document.getElementById('ward-map-detail'),
    status: document.getElementById('ward-map-status'),
    legend: document.getElementById('ward-map-legend'),
    choice: document.getElementById('map-ward-select'),
    mode: document.getElementById('map-mode'),
    reset: document.getElementById('map-reset'),
    drag: document.getElementById('map-drag-toggle'),
    legendToggle: document.getElementById('map-legend-toggle')
  };
  if (!els.map || !els.side || typeof L === 'undefined') {
    if (els.status) els.status.textContent = 'Interactive map unavailable. The results and ward list below remain available.';
    return;
  }
  const touchMode = typeof window.matchMedia === 'function' && window.matchMedia('(pointer: coarse)').matches;
  let city = window.initialMetro && spec[window.initialMetro] ? window.initialMetro : 'Cape Town';
  let mode = 'leading';
  let selectedNumber = null;
  let polygonLayer = null;
  let polygonByWard = {};
  let loadVersion = 0;
  const cache = {};
  const inFlight = {};

  const map = L.map(els.map, {
    preferCanvas: true,
    scrollWheelZoom: false,
    tap: true,
    zoomControl: true
  }).setView(spec[city].centre, spec[city].zoom);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(map);

  // Mobile screens default to page scrolling, rather than accidentally
  // dragging the map. Tapping a ward still opens its results immediately.
  if (touchMode && els.drag && map.dragging) {
    map.dragging.disable();
    els.drag.hidden = false;
    els.drag.addEventListener('click', function () {
      const enabled = map.dragging.enabled();
      if (enabled) map.dragging.disable();
      else map.dragging.enable();
      const nowEnabled = map.dragging.enabled();
      els.drag.setAttribute('aria-pressed', String(nowEnabled));
      els.drag.textContent = nowEnabled ? 'Done moving map' : 'Move map';
      els.drag.setAttribute('aria-label', nowEnabled
        ? 'Stop moving the map by dragging' : 'Enable moving the map by dragging');
    });
  }
  if (els.legendToggle) {
    els.legendToggle.addEventListener('click', function () {
      const expanded = els.legend.classList.toggle('is-visible');
      els.legendToggle.setAttribute('aria-expanded', String(expanded));
      els.legendToggle.textContent = expanded ? 'Hide map colour key ▴' : 'Show map colour key ▾';
    });
  }

  function safe(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c];
    });
  }
  function metro() {
    return (typeof data !== 'undefined' && data && data.metros && data.metros[city]) || {};
  }
  function wardAreasFor(name) {
    return (typeof wardAreas !== 'undefined' && wardAreas && wardAreas.metros && wardAreas.metros[name]) || {};
  }
  function listOfWards() {
    return Array.isArray(metro().wards) ? metro().wards : [];
  }
  function wardAt(number) {
    return listOfWards().find(function (w) {return Number(w.number) === Number(number);}) || null;
  }
  function areaAt(number) {
    return String(wardAreasFor(city)[String(number)] || '').trim();
  }
  function leadAt(number) {
    const ward = wardAt(number);
    if (!ward || !Array.isArray(ward.parties)) return null;
    const lead = ward.parties
      .filter(function (p) {return p && typeof p.name === 'string' && Number.isFinite(p.share) && p.share >= 0 && p.share <= 100;})
      .sort(function (a, b) {return b.share - a.share;})[0];
    return lead || null;
  }
  function wardHistory(number) {
    const previous = typeof history2021 !== 'undefined' && history2021 && history2021.metros && history2021.metros[city];
    const row = previous && previous.wards && previous.wards[String(number)];
    return row && row.year === 2021 && row.ballot_type === 'Ward' ? row : null;
  }
  function historicalPct(number, party) {
    const row = wardHistory(number);
    const pct = row && row.parties && row.parties[party];
    return Number.isFinite(pct) && pct >= 0 && pct <= 100 ? pct.toFixed(1) + '%' : '';
  }
  function progressAt(number) {
    const ward = wardAt(number);
    const reportingText=String(ward && ward.reporting || '');
    const direct=/^(\d+)\s+voting districts with votes/i.exec(reportingText);
    if (direct) return Number(direct[1]) > 0 ? 'partial' : 'none';
    const result = /^(\d+)\s+of\s+(\d+)\s+districts/i.exec(reportingText);
    if (!result) return 'none';
    const done = Number(result[1]), total = Number(result[2]);
    if (!total || !done) return 'none';
    return done >= total ? 'complete' : 'partial';
  }
  function colourAt(number) {
    if (mode === 'reporting') return statusColors[progressAt(number)];
    const lead = leadAt(number);
    return lead ? (palette[lead.name] || '#b879bb') : unknown;
  }
  function styleFor(feature) {
    const number = Number(feature.properties.ward);
    const active = number === selectedNumber;
    return {
      color: active ? '#fff' : '#21334a',
      weight: active ? 3.2 : 1.05,
      fillColor: colourAt(number),
      fillOpacity: active ? 0.87 : 0.69,
      opacity: 0.96
    };
  }
  function areaLabel() {return city === 'Hermanus' ? 'Hermanus / Overstrand Municipality' : city;}
  function wardTitle(number) {
    const area = areaAt(number);
    return 'Ward ' + number + (area ? ' · ' + area : '');
  }
  function tipFor(number, showDetailsLink = false) {
    const result = wardAt(number);
    const area = areaAt(number);
    const ranked = result && Array.isArray(result.parties) ? result.parties
      .filter(function (p) {return p && typeof p.name === 'string' && Number.isFinite(p.share) && p.share >= 0 && p.share <= 100;})
      .sort(function (a, b) {return b.share - a.share;}).slice(0, 3) : [];
    const ranking = ranked.length
      ? ranked.map(function (party, index) {
          const previous = historicalPct(number, party.name);
          return '<div class="ward-quick-party"><span class="ward-quick-name">' +
            (index + 1) + '. ' + safe(party.name) + '</span>' +
            '<span class="ward-quick-value"><strong>' + party.share.toFixed(1) + '%</strong>' +
            (previous ? '<small>(2021: ' + previous + ')</small>' : '') + '</span></div>';
        }).join('')
      : '<p class="ward-quick-empty">No reported ward-ballot results yet</p>';
    return '<div class="ward-quick-preview">' +
      '<div class="ward-quick-title">Ward ' + number + '</div>' +
      (area ? '<div class="ward-quick-area">' + safe(area) + '</div>' : '') +
      '<div class="ward-quick-parties">' + ranking + '</div>' +
      (result && result.reporting ? '<div class="ward-quick-status">' + safe(result.reporting) + '</div>' : '') +
      (showDetailsLink
        ? '<a href="#ward-map-detail" class="ward-quick-link">See full ward breakdown</a>'
        : '<div class="ward-quick-hint">Tap the ward for full results</div>') + '</div>';
  }
  function validateGeoJSON(value, name) {
    const expected = spec[name].count;
    if (!value || value.type !== 'FeatureCollection' || !Array.isArray(value.features)) {
      throw new Error('No valid 2026 ward boundary dataset returned.');
    }
    const found = new Set();
    const features = value.features.map(function (feature) {
      const p = feature && feature.properties || {};
      const id = Number(p.ward != null ? p.ward : (p.WardNo != null ? p.WardNo : p.wardno));
      const g = feature && feature.geometry;
      if (!Number.isInteger(id) || id < 1 || id > expected || found.has(id) ||
          !g || !['Polygon', 'MultiPolygon'].includes(g.type) || !Array.isArray(g.coordinates) || !g.coordinates.length) {
        throw new Error('Source ward shapes do not match 2026 ward identifiers.');
      }
      found.add(id);
      if (p.MUNICNAME && !String(p.MUNICNAME).toLowerCase().includes(spec[name].query.toLowerCase())) {
        throw new Error('Boundary source returned a different municipality.');
      }
      return {type: 'Feature', properties: {ward: id}, geometry: g};
    });
    if (found.size !== expected) throw new Error('Only ' + found.size + ' of ' + expected + ' ward boundaries were returned.');
    return {type: 'FeatureCollection', features: features};
  }
  async function requestJSON(url) {
    const response = await fetch(url, {cache: 'no-store'});
    if (!response.ok) throw new Error('HTTP ' + response.status);
    return response.json();
  }
  async function loadGeoJSON(name) {
    if (cache[name]) return cache[name];
    if (inFlight[name]) return inFlight[name];
    inFlight[name] = (async function () {
      let lastError;
      try {
        const local = await requestJSON('./ward-boundaries/' + spec[name].slug + '.geojson');
        const verified = validateGeoJSON(local, name);
        cache[name] = verified;
        return verified;
      } catch (error) {
        lastError = error;
      }
      // Fallback while Pages is deploying its local validated boundary copy.
      const parameters = new URLSearchParams({
        where: "MUNICNAME LIKE '%" + spec[name].query + "%'",
        outFields: 'WardNo,WardID,MUNICNAME',
        outSR: '4326',
        geometryPrecision: '5',
        maxAllowableOffset: '0.00015',
        returnGeometry: 'true',
        f: 'geojson'
      });
      for (const endpoint of endpoints) {
        try {
          const geojson = await requestJSON(endpoint + '?' + parameters.toString());
          const verified = validateGeoJSON(geojson, name);
          cache[name] = verified;
          return verified;
        } catch (error) {
          lastError = error;
        }
      }
      throw lastError || new Error('2026 ward boundaries could not be loaded');
    })();
    try {
      return await inFlight[name];
    } finally {
      delete inFlight[name];
    }
  }
  function showMapMessage(message) {
    els.status.textContent = message;
  }
  function repaint() {
    if (!polygonLayer) return;
    polygonLayer.eachLayer(function (layer) {
      layer.setStyle(styleFor(layer.feature));
      const number = layer.feature.properties.ward;
      if (layer.getTooltip()) layer.setTooltipContent(tipFor(number));
      if (layer.getPopup()) layer.setPopupContent(tipFor(number, true));
    });
  }
  function panelFor(number) {
    const ward = wardAt(number);
    const name = areaAt(number);
    const progress = progressAt(number);
    const reporting = ward && ward.reporting && progress !== 'none' ? ward.reporting : 'Not yet reported';
    const source = ward && typeof ward.source_url === 'string' && /^https:\/\//.test(ward.source_url) ? ward.source_url : '';
    const detailStamp = ward && ward.detail_at || ward && ward.snapshot_at;
    const snapshot = detailStamp && !Number.isNaN(Date.parse(detailStamp))
      ? new Intl.DateTimeFormat('en-ZA', {dateStyle: 'medium', timeStyle: 'short', timeZone: 'Africa/Johannesburg'}).format(new Date(detailStamp)) + ' SAST'
      : 'Not available';
    const historical = wardHistory(number);
    const ranked = ward && Array.isArray(ward.parties) ? ward.parties
      .filter(function (p) {return p && typeof p.name === 'string' && Number.isFinite(p.share) && p.share >= 0 && p.share <= 100;})
      .sort(function (a,b) {return b.share-a.share;}).slice(0,3) : [];
    const partyRows = ranked.map(function (p, index) {
      const accent = palette[p.name] || '#b879bb';
      const votes = Number.isSafeInteger(p.votes) && p.votes >= 0
        ? new Intl.NumberFormat('en-ZA').format(p.votes) + ' votes' : '';
      const previousShare = historicalPct(number, p.name);
      return '<div class="ward-map-party-row">' +
        '<div class="ward-map-party-line"><span class="ward-map-rank">' + (index+1) + '</span>' +
        '<span class="ward-map-party-name">' + safe(p.name) + '</span>' +
        '<span class="ward-map-share-pair"><strong>' + p.share.toFixed(1) + '%</strong>' +
        (previousShare ? '<small class="history-share">(2021: ' + previousShare + ')</small>' : '') + '</span></div>' +
        '<div class="ward-map-party-track"><span style="width:' + p.share + '%;background:' + accent + '"></span></div>' +
        (votes ? '<div class="ward-map-party-votes">' + safe(votes) + '</div>' : '') +
        '</div>';
    }).join('');
    els.side.innerHTML =
      '<div class="ward-map-subtitle">' + safe(city) + ' · 2026 ward</div>' +
      '<h3>Ward ' + number + '</h3>' +
      '<p class="ward-map-area">' + safe(name || 'Area description unavailable') + '</p>' +
      '<h4 class="ward-map-parties-title">Top 3 · ward ballot</h4>' +
      (partyRows || '<p class="ward-map-note">No reported ward-ballot results yet.</p>') +
      (ranked.length > 0 && ranked.length < 3
        ? '<p class="ward-map-note">Additional parties will appear when this ward\'s results are validated. The leader shown is provisional.</p>'
        : '') +
      (ward && Number.isSafeInteger(ward.valid_votes) && ward.valid_votes >= 0
        ? '<div class="ward-map-stat"><span>Valid ward-ballot votes</span><strong>' + new Intl.NumberFormat('en-ZA').format(ward.valid_votes) + '</strong></div>'
        : '') +
      '<div class="ward-map-stat"><span>Counting progress</span><strong>' + safe(reporting) + '</strong></div>' +
      '<div class="ward-map-stat"><span>Last source snapshot</span><strong>' + safe(snapshot) + '</strong></div>' +
      (historical && Number.isInteger(historical.matched_districts) && Number.isInteger(historical.districts_in_2026_ward)
        ? '<p class="ward-map-note">2021 brackets are matched historic ward-ballot votes in ' + historical.matched_districts + '/' + historical.districts_in_2026_ward + ' current ward voting districts, not necessarily the old ward boundary.</p>'
        : '') +
      '<p class="ward-map-note">Preliminary ward-ballot votes are not final declared councillors or council seats.</p>' +
      '<button type="button" class="ward-map-view" id="ward-map-jump">See ward in results list</button>' +
      (source ? '<a class="ward-map-source" href="' + safe(source) + '" target="_blank" rel="noopener noreferrer">Ward ballot source</a>' +
        '<a class="ward-map-source" href="' + safe(source + '?ballot=pr') + '" target="_blank" rel="noopener noreferrer">View this ward’s PR ballot on ESP</a>' : '');
    const action = document.getElementById('ward-map-jump');
    if (action) action.addEventListener('click', function () {
      const metroSelect = document.getElementById('metro');
      const search = document.getElementById('wardSearch');
      const explorer = document.getElementById('ward-explorer');
      if (metroSelect && search && explorer && typeof renderWards === 'function') {
        metroSelect.value = city;
        search.value = 'ward ' + number;
        renderWards();
        const detail = explorer.querySelector('details.ward[data-ward-number="' + number + '"]');
        if (detail) detail.open = true;
        explorer.scrollIntoView({behavior: 'smooth', block: 'start'});
      }
    });
  }
  function resetPanel() {
    els.side.innerHTML = '<div class="ward-map-subtitle">' + safe(city) +
      ' · 2026 ward map</div><h3>Select a ward</h3>' +
      '<p>Tap a coloured area on the map, or choose a ward above, to see its reported vote share and counting progress.</p>' +
      '<p class="ward-map-note">Grey = no reported result yet. All party leads are preliminary.</p>';
  }
  function chooseWard(number, shouldZoom) {
    const layer = polygonByWard[Number(number)];
    if (!layer) return;
    selectedNumber = Number(number);
    els.choice.value = String(number);
    repaint();
    if (shouldZoom) {
      const bounds = layer.getBounds();
      if (bounds && bounds.isValid()) map.fitBounds(bounds, {padding: [35, 35], maxZoom: 14, animate: true});
    }
    layer.bringToFront();
    panelFor(selectedNumber);
  }
  function updateChoices() {
    const previouslySelected = selectedNumber;
    let choices = '<option value="">Choose a ward to zoom into…</option>';
    const areas = wardAreasFor(city);
    for (let n = 1; n <= spec[city].count; n++) {
      choices += '<option value="' + n + '">Ward ' + n +
        (areas[String(n)] ? ' · ' + safe(areas[String(n)]) : '') + '</option>';
    }
    els.choice.innerHTML = choices;
    els.choice.value = previouslySelected != null ? String(previouslySelected) : '';
  }
  function updateTabs() {
    document.querySelectorAll('[data-ward-map-metro]').forEach(function (button) {
      const name = button.getAttribute('data-ward-map-metro');
      const isActive = name === city;
      button.setAttribute('aria-selected', String(isActive));
      button.tabIndex = isActive ? 0 : -1;
      const m = (typeof data !== 'undefined' && data.metros && data.metros[name]) || {};
      const num = Array.isArray(m.wards) ? m.wards.filter(function (w) {return Array.isArray(w.parties) && w.parties.length;}).length : null;
      const count = spec[name].count;
      const counter = button.querySelector('.map-metro-count');
      if (counter) counter.textContent = num != null ? num + ' of ' + count + ' wards reporting' : count + ' wards';
    });
  }
  function updateLegend() {
    if (mode === 'reporting') {
      els.legend.innerHTML =
        '<span class="map-legend-item"><i style="background:' + statusColors.complete + '"></i>Fully reported</span>' +
        '<span class="map-legend-item"><i style="background:' + statusColors.partial + '"></i>Partly reported</span>' +
        '<span class="map-legend-item"><i style="background:' + unknown + '"></i>Not reported</span>';
      return;
    }
    const seen = new Set();
    listOfWards().forEach(function (w) {
      const lead = leadAt(w.number);
      if (lead) seen.add(lead.name);
    });
    let html = Array.from(seen).sort(function (a, b) {return a.localeCompare(b);}).map(function (party) {
      return '<span class="map-legend-item"><i style="background:' + (palette[party] || '#b879bb') +
        '"></i>' + safe(party) + '</span>';
    }).join('');
    html += '<span class="map-legend-item"><i style="background:' + unknown + '"></i>Not reported</span>';
    els.legend.innerHTML = html;
  }
  async function showCity(name) {
    if (!spec[name]) return;
    const thisRequest = ++loadVersion;
    city = name;
    if (typeof window.onMetroMapSelect === 'function') window.onMetroMapSelect(name);
    selectedNumber = null;
    if (polygonLayer) map.removeLayer(polygonLayer);
    polygonLayer = null;
    polygonByWard = {};
    resetPanel();
    updateTabs();
    updateChoices();
    updateLegend();
    showMapMessage('Loading 2026 ward boundaries for ' + name + '…');
    map.setView(spec[name].centre, spec[name].zoom, {animate: false});
    try {
      const polygons = await loadGeoJSON(name);
      if (thisRequest !== loadVersion) return;
      const polygonsLayer = L.geoJSON(polygons, {
        style: styleFor,
        onEachFeature: function (feature, layer) {
          const id = Number(feature.properties.ward);
          polygonByWard[id] = layer;
          if (!touchMode) layer.bindTooltip(tipFor(id), {sticky: true, direction: 'top', className: 'ward-map-tooltip'});
          // A tap opens a larger, auto-panning popup rather than forcing people to
          // read the narrow hover tooltip. Leave the full results panel in place.
          layer.bindPopup(tipFor(id, true), {
            className: 'ward-map-popup',
            maxWidth: 370,
            minWidth: Math.max(180, Math.min(300, map.getSize().x - 75)),
            autoPan: true,
            autoPanPadding: [14, 14],
            closeButton: true
          });
          layer.on('mouseover', function () {
            if (id !== selectedNumber) layer.setStyle({color: '#ffffff', weight: 2.5, fillOpacity: .85});
            layer.bringToFront();
          });
          layer.on('mouseout', function () {layer.setStyle(styleFor(feature));});
          layer.on('click', function () {
            if (layer.getTooltip()) layer.closeTooltip();
            chooseWard(id, false);
          });
        }
      }).addTo(map);
      polygonLayer = polygonsLayer;
      map.fitBounds(polygonLayer.getBounds(), {padding: [15, 15], animate: false});
      showMapMessage(spec[name].count + ' validated 2026 ward boundaries · tap a ward to drill down.' +
        (touchMode ? ' To scroll the page, dragging starts off; tap Move map when you want to pan.' : ' Ward-ballot figures update automatically.'));
      repaint();
    } catch (error) {
      if (thisRequest !== loadVersion) return;
      showMapMessage('Ward boundaries could not load: ' + error.message + '. You can still use the ward results list below.');
      els.side.innerHTML = '<h3>Map temporarily unavailable</h3><p>Ward-by-ward voting figures remain available in the searchable list below.</p>';
    }
  }
  function refresh() {
    updateTabs();
    updateLegend();
    updateChoices();
    repaint();
    if (selectedNumber != null) panelFor(selectedNumber);
  }
  document.querySelectorAll('[data-ward-map-metro]').forEach(function (button) {
    button.addEventListener('click', function () {showCity(button.getAttribute('data-ward-map-metro'));});
    button.addEventListener('keydown', function (event) {
      if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
      event.preventDefault();
      const names = Object.keys(spec), index = names.indexOf(city);
      const direction = event.key === 'ArrowRight' ? 1 : -1;
      const next = names[(index + direction + names.length) % names.length];
      showCity(next);
      document.querySelector('[data-ward-map-metro="' + next + '"]').focus();
    });
  });
  els.choice.addEventListener('change', function () {
    if (els.choice.value) chooseWard(Number(els.choice.value), true);
  });
  els.mode.addEventListener('change', function () {
    mode = els.mode.value === 'reporting' ? 'reporting' : 'leading';
    updateLegend();
    repaint();
    if (selectedNumber != null) panelFor(selectedNumber);
  });
  els.reset.addEventListener('click', function () {
    selectedNumber = null;
    els.choice.value = '';
    repaint();
    resetPanel();
    if (polygonLayer) map.fitBounds(polygonLayer.getBounds(), {padding: [15, 15]});
    else map.setView(spec[city].centre, spec[city].zoom);
  });
  window.metroWardMaps = {refresh: refresh, selectMetro: showCity};
  showCity(city);
})();
