const form = document.getElementById('settings');
const preset = document.getElementById('preset');
const references = document.getElementById('references');
const frames = document.getElementById('frames');
const algorithm = document.getElementById('algorithm');
const run = document.getElementById('run');
const engine = document.getElementById('engine');
const status = document.getElementById('status');
const error = document.getElementById('error');
const stale = document.getElementById('stale');
const empty = document.getElementById('empty');
const content = document.getElementById('result-content');
const details = document.getElementById('run-details');
const summary = document.getElementById('summary');
const previousStep = document.getElementById('previous-step');
const nextStep = document.getElementById('next-step');
const stepPosition = document.getElementById('step-position');
const stepPage = document.getElementById('step-page');
const stepOutcome = document.getElementById('step-outcome');
const stepReason = document.getElementById('step-reason');
const stepFrames = document.getElementById('step-frames');
const traceTitle = document.getElementById('trace-title');
const traceCount = document.getElementById('trace-count');
const table = document.getElementById('trace-table');
const faultsOnly = document.getElementById('faults-only');
const fields = { references, frames };

const examples = {
  classic: references.defaultValue,
  belady: '1 2 3 4 1 2 5 1 2 3 4 5',
  locality: '2 3 2 1 5 2 4 5 3 2 5 2',
};

let python;
let results = [];
let selected = 0;
let stepIndex = 0;
let engineReady = false;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function showError(message) {
  error.textContent = message;
  error.hidden = !message;
}

function showFieldError(name, message) {
  for (const [key, input] of Object.entries(fields)) {
    const note = document.getElementById(key + '-error');
    const active = key === name;
    note.textContent = active ? message : '';
    note.hidden = !active;
    if (active) input.setAttribute('aria-invalid', 'true');
    else input.removeAttribute('aria-invalid');
  }
}

function setStale(isStale) {
  stale.hidden = !isStale;
  content.classList.toggle('is-stale', isStale);
}

function showInputChange() {
  if (!engineReady) return;
  showError('');
  showFieldError(null);
  status.textContent = '';
  setStale(results.length > 0);
}

preset.addEventListener('change', () => {
  if (preset.value in examples) {
    references.value = examples[preset.value];
    frames.value = frames.defaultValue;
  }
  showInputChange();
});

form.addEventListener('input', (event) => {
  if (event.target === preset) return;
  if (event.target === references || event.target === frames) preset.value = 'custom';
  showInputChange();
});

form.addEventListener('reset', () => {
  results = [];
  faultsOnly.checked = false;
  summary.replaceChildren();
  table.replaceChildren();
  details.textContent = '';
  content.hidden = true;
  empty.hidden = false;
  showInputChange();
});

function selectTrace(index) {
  selected = index;
  Array.from(summary.children).forEach((card, cardIndex) => {
    card.setAttribute('aria-pressed', String(index === cardIndex));
  });
  renderStep();
  renderTrace();
}

function markCurrentRow() {
  const previous = table.querySelector('tr.current');
  previous?.classList.remove('current');
  previous?.removeAttribute('aria-current');
  const row = table.querySelector('tr[data-step="' + stepIndex + '"]');
  if (row) {
    row.classList.add('current');
    row.setAttribute('aria-current', 'step');
  }
}

function renderStep() {
  const { algorithm, steps } = results[selected];
  const [page, slots, hit, reason, victim] = steps[stepIndex];
  stepPosition.textContent = algorithm + ' · Step ' + (stepIndex + 1) + ' of ' + steps.length;
  stepPage.textContent = page;
  stepOutcome.textContent = hit ? 'Hit' : 'Fault';
  stepOutcome.className = hit ? 'badge hit' : 'badge fault';
  stepReason.textContent = reason;
  previousStep.setAttribute('aria-disabled', String(stepIndex === 0));
  nextStep.setAttribute('aria-disabled', String(stepIndex === steps.length - 1));

  const frameTiles = slots.map((slot, index) => {
    let state = slot === null ? 'vacant' : 'resident';
    let label = slot === null ? 'Empty' : 'Resident';
    if (slot === page) {
      state = hit ? 'hit' : 'loaded';
      label = hit ? 'Hit' : victim === null ? 'Loaded' : 'Replaced ' + victim;
    }
    const tile = element('div', undefined, 'step-frame ' + state);
    const name = 'Frame ' + (index + 1);
    const value = slot ?? '—';
    tile.setAttribute('aria-label', name + ': ' + (slot === null ? 'empty' : 'page ' + slot + ', ' + label.replace('Replaced ', 'loaded, evicted page ').toLowerCase()));
    tile.title = slot === null ? name + ' empty' : name + ': page ' + slot;
    tile.append(element('dt', 'F' + String(index + 1).padStart(2, '0'), 'frame-id'), element('dd', value, 'frame-value'));
    tile.append(element('dd', label, 'frame-state'));
    return tile;
  });
  stepFrames.replaceChildren(...frameTiles);
  markCurrentRow();
}

function moveStep(offset) {
  const nextIndex = stepIndex + offset;
  if (nextIndex < 0 || nextIndex >= results[selected].steps.length) return;
  stepIndex = nextIndex;
  renderStep();
}

previousStep.addEventListener('click', () => moveStep(-1));
nextStep.addEventListener('click', () => moveStep(1));

document.addEventListener('keydown', (event) => {
  if (content.hidden || event.altKey || event.ctrlKey || event.metaKey) return;
  // Arrow keys still move the caret, change selects, or scroll the trace inside these.
  if (event.target.closest('input, textarea, select, .table-scroll')) return;
  if (event.key === 'ArrowLeft') moveStep(-1);
  else if (event.key === 'ArrowRight') moveStep(1);
  else return;
  event.preventDefault();
});

function renderSummary(fewestFaults) {
  summary.replaceChildren();
  summary.classList.toggle('single', results.length === 1);
  results.forEach((result, index) => {
    const card = element('button', undefined, 'result-card');
    card.type = 'button';
    const heading = element('span', undefined, 'card-heading');
    heading.append(element('span', result.algorithm, 'card-name'));
    if (results.length > 1 && result.faults === fewestFaults) {
      heading.append(element('span', '★ Fewest faults', 'best'));
    }
    const rate = 100 * result.hits / result.steps.length;
    const metrics = element('span', undefined, 'metrics');
    for (const [value, label, kind] of [[result.faults, 'Faults', 'fault'], [result.hits, 'Hits', 'hit'], [rate.toFixed(1) + '%', 'Hit rate', 'rate']]) {
      const metric = element('span', undefined, 'metric ' + kind);
      metric.append(element('strong', value, 'mono'), element('span', label));
      metrics.append(metric);
    }
    const bar = element('span', undefined, 'hit-bar');
    bar.setAttribute('aria-hidden', 'true');
    const fill = element('span');
    fill.style.width = rate + '%';
    bar.append(fill);
    card.append(heading, metrics, bar);
    card.addEventListener('click', () => selectTrace(index));
    summary.append(card);
  });
}

function renderTrace() {
  const result = results[selected];
  if (!result) return;

  const headings = ['Step', 'Page', 'Outcome'];
  for (let frame = 1; frame <= result.frames; frame += 1) headings.push('F' + String(frame).padStart(2, '0'));
  headings.push('Decision');
  const head = document.createElement('thead');
  const header = head.insertRow();
  for (const label of headings) {
    const cell = element('th', label);
    cell.scope = 'col';
    header.append(cell);
  }

  const body = document.createElement('tbody');
  let visibleSteps = 0;
  result.steps.forEach(([page, slots, hit, reason], index) => {
    if (faultsOnly.checked && hit) return;
    visibleSteps += 1;
    const row = body.insertRow();
    row.dataset.step = index;
    const step = element('th', index + 1);
    step.scope = 'row';
    const outcome = element('td');
    outcome.append(element('span', hit ? 'Hit' : 'Fault', hit ? 'badge hit' : 'badge fault'));
    row.append(step, element('td', page, 'page'), outcome);
    for (const slot of slots) {
      row.append(element('td', slot ?? '–', !hit && slot === page ? 'frame loaded' : 'frame'));
    }
    row.append(element('td', reason, 'reason'));
  });

  const total = result.steps.length;
  traceTitle.textContent = result.algorithm + ' frame trace';
  traceCount.textContent = faultsOnly.checked
    ? 'Showing ' + visibleSteps + (visibleSteps === 1 ? ' fault' : ' faults') + ' of ' + total + ' requests'
    : 'Showing all ' + total + (total === 1 ? ' request' : ' requests');
  table.replaceChildren(head, body);
  table.parentElement.scrollTop = 0;
  table.parentElement.scrollLeft = 0;
  markCurrentRow();
}

faultsOnly.addEventListener('change', renderTrace);

const simulate = [
  'import json',
  'field = "references"',
  'try:',
  "    refs = sim['parse_reference_string'](reference_input)",
  '    if len(refs) > 500:',
  '        raise ValueError("Enter at most 500 page references.")',
  '    field = "frames"',
  "    count = sim['validate_frames'](frame_input)",
  '    if count > 64:',
  '        raise ValueError("Choose at most 64 memory frames.")',
  "    runs = sim['run_all'](refs, count) if algorithm_input == 'all' else [sim['ALGORITHMS'][algorithm_input](refs, count)]",
  '    response = {"results": [',
  '        {"algorithm": r.algorithm, "frames": r.num_frames, "hits": r.hits, "faults": r.faults,',
  '         "steps": [[str(s.page), [str(p) if p is not None else None for p in s.frames], s.hit, s.reason,',
  '                    str(s.replaced) if s.replaced is not None else None]',
  '                   for s in r.steps]} for r in runs]}',
  'except ValueError as exc:',
  '    response = {"error": str(exc), "field": field}',
  'json.dumps(response)',
].join('\n');

form.addEventListener('submit', (event) => {
  event.preventDefault();
  if (!engineReady) return;
  showError('');
  showFieldError(null);
  status.textContent = '';
  try {
    python.globals.set('reference_input', references.value);
    python.globals.set('frame_input', String(frames.valueAsNumber));
    python.globals.set('algorithm_input', algorithm.value);
    const response = JSON.parse(python.runPython(simulate));
    if (response.error) {
      showFieldError(response.field, response.error);
      fields[response.field].focus();
      return;
    }
    results = response.results;
    stepIndex = 0;
    const referenceCount = results[0].steps.length;
    const frameCount = results[0].frames;
    details.textContent = referenceCount + (referenceCount === 1 ? ' reference' : ' references') +
      ' · ' + frameCount + (frameCount === 1 ? ' frame' : ' frames');
    const fewestFaults = Math.min(...results.map((result) => result.faults));
    renderSummary(fewestFaults);
    selectTrace(results.findIndex((result) => result.faults === fewestFaults));
    empty.hidden = true;
    content.hidden = false;
    setStale(false);
    status.textContent = 'Simulation complete.';
  } catch (cause) {
    console.error(cause);
    showError('Simulation failed. Try again or reload the page.');
  }
});

function setEngine(state, text) {
  engine.dataset.state = state;
  engine.textContent = text;
}

async function load() {
  try {
    python = await loadPyodide();
    const response = await fetch('./page_replacement.py');
    if (!response.ok) throw new Error('Could not load page_replacement.py (' + response.status + ')');
    python.globals.set('source_code', await response.text());
    python.runPython('sim = {"__name__": "page_replacement"}\nexec(source_code, sim)');
    engineReady = true;
    run.disabled = false;
    setEngine('ready', 'Engine ready');
    if (form.checkValidity()) form.requestSubmit(run);
  } catch (cause) {
    console.error(cause);
    setEngine('error', 'Engine error');
    showError('Could not load the simulation engine. Check your connection and reload the page.');
  }
}

load();
