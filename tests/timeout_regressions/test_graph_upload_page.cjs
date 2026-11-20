'use strict';

// Execute the page's real functions with browser/network/drawing substitutes.
// No service is started, no upload occurs and no project data is written.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const root = process.env.XTY_SOURCE_ROOT || path.resolve(__dirname, '../..');
const html = fs.readFileSync(path.join(root, 'graph/modules/xintuoyin/templates/index.html'), 'utf8');
function pageFunction(name) {
  const start = new RegExp(`^(?:async )?function ${name}\\(`, 'm').exec(html);
  assert.ok(start, `page function ${name} exists`);
  const rest = html.slice(start.index);
  const next = /\n(?:async )?function \w+\(/.exec(rest);
  return rest.slice(0, next ? next.index : rest.indexOf('</script>'))
    .replace(/\ninitCanvas\(\);[\s\S]*$/, '');
}

function fixture(names) {
  const elements = new Map();
  function element(id) {
    if (!elements.has(id)) {
      let value = '';
      let innerHTML = '';
      const item = {
        disabled: false, style: {}, options: [],
        get value() { return value; }, set value(next) { value = next; },
        get innerHTML() { return innerHTML; },
        set innerHTML(next) { innerHTML = next; this.options = []; value = ''; },
        appendChild(option) {
          this.options.push(option);
          if (this.options.length === 1 || option.selected) value = option.value;
        },
      };
      elements.set(id, item);
    }
    return elements.get(id);
  }
  const calls = { fetch: [], loads: [], lists: [], alerts: [], renders: [], posts: [] };
  const chain = new Proxy(function () {}, {
    get: () => () => chain,
    apply: () => chain,
  });
  const context = vm.createContext({
    console: { error() {} },
    document: { getElementById: element, createElement: () => ({}) },
    FormData: class {
      constructor() { this.entries = []; }
      append(key, value) { this.entries.push([key, value]); }
      get(key) { return this.entries.find(([name]) => name === key)?.[1] ?? null; }
    },
    fetch: async (url, options) => {
      calls.fetch.push({ url, options });
      return { ok: true, json: async () => ({ code: 0, data: { graphId: 'selected', current_db: 'selected.json' } }) };
    },
    alert: message => calls.alerts.push(message),
    window: { location: { origin: 'http://fixture.invalid' }, parent: { postMessage: message => calls.posts.push(message) } },
    stagedFiles: [{ name: 'fixture.md' }], uploadProcessing: false,
    graphLoadSequence: 0,
    renderStaging() {}, initCanvas() {}, populateDatalists() {},
    loadGraph: async id => calls.loads.push(id),
    loadDatabases: async id => calls.lists.push(id),
    width: 100, height: 100, container: chain,
    dragstarted() {}, dragged() {}, dragended() {}, showDetails() {}, showExcelModal() {},
    d3: { values: map => { const nodes = Object.values(map); calls.renders.push(nodes); return nodes; }, layout: { force: () => chain } },
  });
  element('dbSelect').value = 'selected.json';
  for (const name of names) vm.runInContext(pageFunction(name), context, { filename: `page:${name}` });
  return { context, calls, element };
}

function deferred() {
  let resolve;
  const promise = new Promise(accept => { resolve = accept; });
  return { promise, resolve };
}

test('upload freezes selected graph ID and reloads the response graph/list', async () => {
  const { context, calls, element } = fixture(['setProcessingState', 'uploadStagedFiles']);
  const pending = deferred();
  context.fetch = async (url, options) => { calls.fetch.push({ url, options }); return pending.promise; };
  const upload = context.uploadStagedFiles();
  const form = calls.fetch[0].options.body;
  element('dbSelect').value = 'other.json';
  pending.resolve({ ok: true, json: async () => ({ code: 0, data: { graphId: 'returned', message: 'done' } }) });
  await upload;
  assert.equal(form.get('isDefault'), 'false');
  assert.equal(form.get('graphId'), 'selected');
  assert.deepEqual(calls.lists, ['returned']);
  assert.deepEqual(calls.loads, ['returned']);
  assert.equal(context.stagedFiles.length, 0);
});

test('upload refuses a missing target instead of silently creating another graph', async () => {
  const { context, calls, element } = fixture(['setProcessingState', 'uploadStagedFiles']);
  element('dbSelect').value = '';
  await context.uploadStagedFiles();
  assert.equal(calls.fetch.length, 0);
  assert.equal(context.stagedFiles.length, 1);
  assert.equal(calls.alerts.length, 1);
});

test('processing locks graph selection and prevents create/switch requests', async () => {
  const { context, calls, element } = fixture(['setProcessingState', 'switchDb', 'createDb']);
  element('newDbName').value = 'new-one';
  context.setProcessingState(true, 'working');
  assert.equal(element('dbSelect').disabled, true);
  await context.switchDb();
  await context.createDb();
  assert.equal(calls.fetch.length, 0);
  context.setProcessingState(false);
  assert.equal(element('dbSelect').disabled, false);
});

test('list refresh prefers the completed request graph over the shared current graph', async () => {
  const { context, element } = fixture(['loadDatabases']);
  context.fetch = async () => ({ ok: true, json: async () => ({ code: 0, data: {
    current_db: 'other.json', available_dbs: ['selected.json', 'other.json'],
  } }) });
  await context.loadDatabases('selected');
  assert.equal(element('dbSelect').value, 'selected.json');
});

test('graph read uses explicit identity rather than the server current pointer', async () => {
  const { context, calls } = fixture(['loadGraph']);
  context.fetch = async url => {
    calls.fetch.push({ url });
    return { json: async () => ({ code: 0, data: { nodes: [], links: [] } }) };
  };
  await context.loadGraph('target name');
  assert.equal(calls.fetch[0].url, '/get_graph?graphId=target%20name');
  await context.loadGraph();
  assert.equal(calls.fetch[1].url, '/get_graph?graphId=selected.json');
});

test('a late graph response cannot replace a more recent requested graph', async () => {
  const { context, calls } = fixture(['loadGraph']);
  const first = deferred(); const second = deferred();
  context.fetch = async url => ({ json: () => url.includes('first') ? first.promise : second.promise });
  const a = context.loadGraph('first'); const b = context.loadGraph('second');
  second.resolve({ code: 0, data: { nodes: [{ id: 'second', attrs: {} }], links: [] } });
  await b;
  first.resolve({ code: 0, data: { nodes: [{ id: 'first', attrs: {} }], links: [] } });
  await a;
  assert.equal(calls.renders.length, 1);
  assert.equal(context.window.allData.nodes[0].name, 'second');
});

test('starting a graph operation invalidates an older unfinished graph read', async () => {
  const { context, calls, element } = fixture(['loadGraph', 'setProcessingState']);
  const pending = deferred();
  context.fetch = async () => ({ json: () => pending.promise });
  const reading = context.loadGraph('old');
  element('dbSelect').value = 'selected.json';
  context.setProcessingState(true, 'uploading');
  pending.resolve({ code: 0, data: { nodes: [{ id: 'old', attrs: {} }], links: [] } });
  await reading;
  assert.equal(calls.renders.length, 0);
  context.setProcessingState(false);
});

test('switch reads the requested graph even if the dropdown changes while awaiting', async () => {
  const { context, calls, element } = fixture(['setProcessingState', 'switchDb']);
  const pending = deferred();
  context.fetch = async () => pending.promise;
  const switching = context.switchDb();
  element('dbSelect').value = 'other.json';
  pending.resolve({ json: async () => ({ code: 0, data: { current_db: 'selected.json' } }) });
  await switching;
  assert.deepEqual(calls.loads, ['selected.json']);
});

test('create refreshes and reads its own returned graph identity', async () => {
  const { context, calls, element } = fixture(['setProcessingState', 'createDb']);
  element('newDbName').value = 'new-one';
  await context.createDb();
  assert.deepEqual(calls.lists, ['selected.json']);
  assert.deepEqual(calls.loads, ['selected.json']);
});

test('failed upload keeps staged files and releases controls without reloading graphs', async () => {
  const { context, calls, element } = fixture(['setProcessingState', 'uploadStagedFiles']);
  context.fetch = async () => ({ status: 400, json: async () => ({ code: 400, msg: 'bad target' }) });
  await context.uploadStagedFiles();
  assert.equal(context.stagedFiles.length, 1);
  assert.equal(context.uploadProcessing, false);
  assert.equal(element('dbSelect').disabled, false);
  assert.equal(calls.loads.length, 0);
  assert.equal(calls.lists.length, 0);
  assert.equal(calls.alerts[0], 'bad target');
});

test('graph mutation POST binds selected graph while preserving query and JSON body', async () => {
  const { context, calls } = fixture(['graphApiRequest']);
  const body = { id: 'new-node', attrs: { kind: 'fixture' } };
  await context.graphApiRequest('/graph/node?mode=fixture', 'POST', body);
  assert.equal(calls.fetch[0].url, '/graph/node?mode=fixture&graphId=selected');
  assert.equal(calls.fetch[0].options.method, 'POST');
  assert.deepEqual(JSON.parse(calls.fetch[0].options.body), body);
});

test('bodyless graph DELETE binds and encodes the selected graph', async () => {
  const { context, calls, element } = fixture(['graphApiRequest']);
  element('dbSelect').value = 'graph A.json';
  await context.graphApiRequest('/graph/node/old-node', 'DELETE');
  assert.equal(calls.fetch[0].url, '/graph/node/old-node?graphId=graph%20A');
  assert.equal(calls.fetch[0].options.method, 'DELETE');
  assert.equal(Object.hasOwn(calls.fetch[0].options, 'body'), false);
});

test('graph mutations reject an empty selection before issuing any request', async () => {
  const { context, calls, element } = fixture(['graphApiRequest']);
  element('dbSelect').value = '';
  await assert.rejects(context.graphApiRequest('/graph/clear', 'POST'), /图谱/);
  assert.equal(calls.fetch.length, 0);
});
