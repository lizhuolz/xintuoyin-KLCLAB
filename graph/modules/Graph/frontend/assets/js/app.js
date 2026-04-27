import { fetchCurrentUser, fetchGraph } from './api.js';
import { TreeGraphRenderer } from './graph.js';

const state = {
  rawGraph: null,
  nodes: [],
  links: [],
  selectedNodeId: null,
  nodeById: new Map(),
  edgeMeta: [],
};

const currentUserText = document.getElementById('currentUserText');
const graphStatus = document.getElementById('graphStatus');
const attrContent = document.getElementById('attrContent');

const renderer = new TreeGraphRenderer({
  svgSelector: '#graphSvg',
  emptySelector: '#graphEmpty',
  onNodeClick: (node) => {
    onNodeSelected(node.id);
  },
});

function setStatus(message, isError = false) {
  graphStatus.textContent = message;
  graphStatus.style.color = isError ? '#ff7875' : '#91d5ff';
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function stringifyValue(value) {
  if (value === null || value === undefined) return '';
  if (Array.isArray(value)) return value.map((item) => String(item)).join('、');
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

function renderRelatedInfo(node) {
  const attrs = node?.attrs && typeof node.attrs === 'object' ? node.attrs : {};
  const rawBlocks = Array.isArray(node?.attrs_blocks) ? node.attrs_blocks : [];
  const blocks = rawBlocks
    .map((block) => {
      const blockAttrs = block?.attrs && typeof block.attrs === 'object' ? block.attrs : {};
      const entries = Object.entries(blockAttrs).filter(([, val]) => val !== null && val !== undefined && val !== '');
      return {
        title: String(block?.title || '相关信息'),
        entries,
      };
    })
    .filter((block) => block.entries.length > 0);

  if (!blocks.length) {
    const fallbackEntries = Object.entries(attrs).filter(([, val]) => val !== null && val !== undefined && val !== '');
    if (fallbackEntries.length) {
      blocks.push({ title: '相关信息', entries: fallbackEntries });
    }
  }

  if (!blocks.length) {
    attrContent.innerHTML = `
      <div class="detail-item">
        <div class="detail-key">相关信息</div>
        <div class="detail-value">当前节点暂无相关信息。</div>
      </div>
    `;
    return;
  }

  attrContent.innerHTML = `
    <div class="detail-item">
      <div class="detail-key">相关信息</div>
      <div class="detail-value">${escapeHtml(node.name || node.id)}</div>
    </div>
    ${blocks.map((block) => `
      <div class="detail-block">
        <div class="detail-block-title">${escapeHtml(block.title)}</div>
        ${block.entries.map(([key, value]) => `
          <div class="detail-item">
            <div class="detail-key">${escapeHtml(key)}</div>
            <div class="detail-value">${escapeHtml(stringifyValue(value))}</div>
          </div>
        `).join('')}
      </div>
    `).join('')}
  `;
}

function onNodeSelected(nodeId) {
  const node = state.nodeById.get(nodeId);
  if (!node) return;
  state.selectedNodeId = nodeId;
  renderer.setSelected(nodeId);
  renderRelatedInfo(node);
}

function buildIndex() {
  state.nodeById = new Map();
  state.nodes.forEach((node) => {
    const normalized = {
      ...node,
      id: node.id,
      name: node.name || node.id,
      attrs: node.attrs && typeof node.attrs === 'object' ? node.attrs : {},
      attrs_blocks: Array.isArray(node.attrs_blocks) ? node.attrs_blocks : [],
    };
    state.nodeById.set(normalized.id, normalized);
  });

  state.edgeMeta = [];
  let edgeIndex = 0;
  for (const link of state.links) {
    if (!link?.source || !link?.target) continue;
    const relation = link.relation || link.label || '';
    state.edgeMeta.push({
      source: link.source,
      target: link.target,
      relation,
      key: `${link.source}|||${link.target}|||${relation}|||${edgeIndex}`,
    });
    edgeIndex += 1;
  }
}

function renderGraph() {
  renderer.render({ nodes: state.nodes, links: state.links });
  if (state.selectedNodeId) {
    renderer.setSelected(state.selectedNodeId);
  }
}

function optionHtml(values) {
  return values.map((value) => `<option value="${escapeHtml(value)}"></option>`).join('');
}

function populateDatalists() {
  const nodeNames = new Set();
  const relations = new Set();
  const attrKeys = new Set();
  const attrVals = new Set();

  for (const node of state.nodes) {
    const name = String(node.name || '').trim();
    if (name) nodeNames.add(name);
    const attrs = node.attrs && typeof node.attrs === 'object' ? node.attrs : {};
    for (const [key, value] of Object.entries(attrs)) {
      if (String(key).trim()) attrKeys.add(String(key));
      const strVal = stringifyValue(value).trim();
      if (strVal) attrVals.add(strVal);
    }
  }

  for (const link of state.links) {
    const relation = String(link.relation || link.label || '').trim();
    if (relation) relations.add(relation);
  }

  const nodeOptions = optionHtml(Array.from(nodeNames));
  const relationOptions = optionHtml(Array.from(relations));
  const attrKeyOptions = optionHtml(Array.from(attrKeys));
  const attrValOptions = optionHtml(Array.from(attrVals));

  document.getElementById('nodeNameList').innerHTML = nodeOptions;
  document.getElementById('pathNodeList').innerHTML = nodeOptions;
  document.getElementById('relationNameList').innerHTML = relationOptions;
  document.getElementById('pathRelationList').innerHTML = relationOptions;
  document.getElementById('attrKeyList').innerHTML = attrKeyOptions;
  document.getElementById('pathAttrKeyList').innerHTML = attrKeyOptions;
  document.getElementById('attrValList').innerHTML = attrValOptions;
  document.getElementById('pathAttrValList').innerHTML = attrValOptions;
}

function normalizeText(value) {
  return String(value || '').trim().toLowerCase();
}

function findNodeIdByNameOrId(keyword) {
  const target = normalizeText(keyword);
  if (!target) return null;

  let fuzzy = null;
  for (const node of state.nodeById.values()) {
    const id = normalizeText(node.id);
    const name = normalizeText(node.name);
    if (id === target || name === target) return node.id;
    if (!fuzzy && (id.includes(target) || name.includes(target))) {
      fuzzy = node.id;
    }
  }
  return fuzzy;
}

function searchAction() {
  const keyword = document.getElementById('searchNode').value.trim();
  if (!keyword) {
    setStatus('请输入节点名称。', true);
    return;
  }

  const nodeId = findNodeIdByNameOrId(keyword);
  if (!nodeId) {
    renderer.setHighlight(null);
    setStatus(`未找到匹配节点：${keyword}`, true);
    return;
  }

  renderer.clearPathFocus();
  renderer.setHighlight(nodeId);
  onNodeSelected(nodeId);
  const pos = renderer.positions.get(nodeId);
  renderer.focusNode(pos, 1.08);
  setStatus(`已定位节点：${state.nodeById.get(nodeId)?.name || nodeId}`);
}

function clearSearch() {
  document.getElementById('searchNode').value = '';
  renderer.setHighlight(null);
  setStatus('已清空节点搜索。');
}

function buildAdjacency() {
  const adj = new Map();
  const pushEdge = (from, to, edge) => {
    if (!adj.has(from)) adj.set(from, []);
    adj.get(from).push({ to, ...edge });
  };

  for (const edge of state.edgeMeta) {
    pushEdge(edge.source, edge.target, edge);
    pushEdge(edge.target, edge.source, edge);
  }
  return adj;
}

function getMiddleNodeFilters() {
  return [...document.querySelectorAll('input[name="midNode"]')]
    .map((input) => input.value.trim())
    .filter(Boolean);
}

function getRelationFilters() {
  return [...document.querySelectorAll('input[name="relaInput"]')]
    .map((input) => input.value.trim())
    .filter(Boolean);
}

function getAttrFilters() {
  const rows = [...document.querySelectorAll('.attr-input-group')];
  const filters = [];
  for (const row of rows) {
    const key = row.querySelector('input[name="attrKey"]')?.value?.trim() || '';
    const val = row.querySelector('input[name="attrVal"]')?.value?.trim() || '';
    if (!key && !val) continue;
    filters.push({ key, val });
  }
  return filters;
}

function matchByLogic(items, conditions, mode) {
  if (!conditions.length) return true;
  const normalizedItems = items.map((item) => normalizeText(item));
  const normalizedConditions = conditions.map((cond) => normalizeText(cond));
  if (mode === 'AND') return normalizedConditions.every((cond) => normalizedItems.includes(cond));
  return normalizedConditions.some((cond) => normalizedItems.includes(cond));
}

function matchAttrByLogic(pathNodeIds, filters, mode) {
  if (!filters.length) return true;

  const oneFilterMatched = (filter) => {
    const targetKey = normalizeText(filter.key);
    const targetVal = normalizeText(filter.val);
    for (const nodeId of pathNodeIds) {
      const node = state.nodeById.get(nodeId);
      if (!node) continue;
      const attrs = node.attrs || {};
      for (const [key, value] of Object.entries(attrs)) {
        const attrKey = normalizeText(key);
        const attrVal = normalizeText(stringifyValue(value));
        const keyOk = targetKey ? attrKey === targetKey : true;
        const valOk = targetVal ? attrVal === targetVal : true;
        if (keyOk && valOk) return true;
      }
    }
    return false;
  };

  if (mode === 'AND') return filters.every(oneFilterMatched);
  return filters.some(oneFilterMatched);
}

function findPathAction() {
  const startRaw = document.getElementById('pathStart').value.trim();
  const endRaw = document.getElementById('pathEnd').value.trim();
  const pathLimit = Math.max(2, Number(document.getElementById('pathLimit').value) || 4);

  if (!startRaw || !endRaw) {
    setStatus('路径分析请填写起点与终点。', true);
    return;
  }

  const startId = findNodeIdByNameOrId(startRaw);
  const endId = findNodeIdByNameOrId(endRaw);
  if (!startId || !endId) {
    setStatus('起点或终点不存在，请从下拉建议中选择。', true);
    return;
  }

  const adj = buildAdjacency();
  const paths = [];

  const dfs = (currentId, visited, pathNodes, pathEdges) => {
    if (pathNodes.length > pathLimit) return;
    if (currentId === endId && pathNodes.length > 1) {
      paths.push({ nodes: [...pathNodes], edges: [...pathEdges] });
      return;
    }

    const neighbors = adj.get(currentId) || [];
    for (const edge of neighbors) {
      if (visited.has(edge.to)) continue;
      visited.add(edge.to);
      pathNodes.push(edge.to);
      pathEdges.push(edge);
      dfs(edge.to, visited, pathNodes, pathEdges);
      pathEdges.pop();
      pathNodes.pop();
      visited.delete(edge.to);
    }
  };

  dfs(startId, new Set([startId]), [startId], []);

  const middleFilters = getMiddleNodeFilters();
  const relationFilters = getRelationFilters();
  const attrFilters = getAttrFilters();
  const middleMode = document.getElementById('filterType').value;
  const relationMode = document.getElementById('relaFilterType').value;
  const attrMode = document.getElementById('attrFilterType').value;

  const filtered = paths.filter((path) => {
    const middleNames = path.nodes
      .slice(1, -1)
      .map((id) => state.nodeById.get(id)?.name)
      .filter(Boolean);
    const relationNames = path.edges.map((edge) => edge.relation).filter(Boolean);

    return (
      matchByLogic(middleNames, middleFilters, middleMode)
      && matchByLogic(relationNames, relationFilters, relationMode)
      && matchAttrByLogic(path.nodes, attrFilters, attrMode)
    );
  });

  if (!filtered.length) {
    renderer.clearPathFocus();
    setStatus('未找到满足条件的路径。', true);
    return;
  }

  const focusNodeIds = new Set();
  const focusLinkKeys = new Set();
  for (const path of filtered) {
    path.nodes.forEach((id) => focusNodeIds.add(id));
    path.edges.forEach((edge) => focusLinkKeys.add(edge.key));
  }

  renderer.setPathFocus(focusNodeIds, focusLinkKeys);
  const first = filtered[0];
  const focusId = first.nodes[first.nodes.length - 1];
  onNodeSelected(focusId);
  renderer.setHighlight(focusId);
  renderer.focusNode(renderer.positions.get(focusId), 1.06);
  setStatus(`路径分析完成：共找到 ${filtered.length} 条满足条件的路径。`);
}

function resetPathAction() {
  renderer.clearPathFocus();
  renderer.setHighlight(null);
  renderer.resetView();
  setStatus('已重置路径分析高亮与视图。');
}

function createInputGroup(type) {
  if (type === 'middle') {
    const div = document.createElement('div');
    div.className = 'mid-input-group toolbar-inline';
    div.innerHTML = `
      <input type="text" name="midNode" placeholder="中间实体名" list="pathNodeList" />
      <button data-remove-row class="btn-secondary">-</button>
    `;
    return div;
  }

  if (type === 'rela') {
    const div = document.createElement('div');
    div.className = 'rela-input-group toolbar-inline';
    div.innerHTML = `
      <input type="text" name="relaInput" placeholder="关系名称" list="pathRelationList" />
      <button data-remove-row class="btn-secondary">-</button>
    `;
    return div;
  }

  const div = document.createElement('div');
  div.className = 'attr-input-group toolbar-inline';
  div.innerHTML = `
    <input type="text" name="attrKey" placeholder="属性名" list="pathAttrKeyList" />
    <span class="equal">=</span>
    <input type="text" name="attrVal" placeholder="属性值" list="pathAttrValList" />
    <button data-remove-row class="btn-secondary">-</button>
  `;
  return div;
}

async function loadGraph() {
  setStatus('正在加载图谱...');
  try {
    const graphResp = await fetchGraph();
    const graphPayload =
      graphResp && typeof graphResp === 'object' && Array.isArray(graphResp.nodes) && Array.isArray(graphResp.links)
        ? graphResp
        : (graphResp?.data || {});
    state.rawGraph = graphPayload;
    state.nodes = Array.isArray(state.rawGraph.nodes) ? state.rawGraph.nodes : [];
    state.links = Array.isArray(state.rawGraph.links) ? state.rawGraph.links : [];
    buildIndex();
    populateDatalists();
    renderGraph();

    const defaultNodeId = state.rawGraph.root?.id || state.nodes[0]?.id || null;
    if (defaultNodeId) {
      onNodeSelected(defaultNodeId);
      renderer.focusNode(renderer.positions.get(defaultNodeId), 1.0);
    } else {
      attrContent.textContent = '点击节点查看相关信息...';
    }

    setStatus(`图谱加载成功：节点 ${state.nodes.length} 个，关系 ${state.links.length} 条`);
  } catch (error) {
    state.rawGraph = null;
    state.nodes = [];
    state.links = [];
    state.selectedNodeId = null;
    state.nodeById = new Map();
    state.edgeMeta = [];
    renderer.clear();
    setStatus(`图谱加载失败：${error.message}`, true);
  }
}

async function loadCurrentUser() {
  try {
    const user = await fetchCurrentUser();
    currentUserText.textContent = `当前用户：${user.username || '--'} / ${user.enterprise_name || '--'}`;
  } catch (error) {
    currentUserText.textContent = '当前用户：加载失败';
  }
}

function bindEvents() {
  document.getElementById('btnReloadGraph').addEventListener('click', loadGraph);
  document.getElementById('btnSearchNode').addEventListener('click', searchAction);
  document.getElementById('btnClearSearch').addEventListener('click', clearSearch);
  document.getElementById('btnFindPath').addEventListener('click', findPathAction);
  document.getElementById('btnResetPath').addEventListener('click', resetPathAction);

  document.addEventListener('click', (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;

    if (target.dataset.addMiddle !== undefined) {
      document.getElementById('middleNodesContainer').appendChild(createInputGroup('middle'));
      return;
    }
    if (target.dataset.addRela !== undefined) {
      document.getElementById('relaContainer').appendChild(createInputGroup('rela'));
      return;
    }
    if (target.dataset.addAttr !== undefined) {
      document.getElementById('attrContainer').appendChild(createInputGroup('attr'));
      return;
    }
    if (target.dataset.removeRow !== undefined) {
      target.closest('.mid-input-group,.rela-input-group,.attr-input-group')?.remove();
      return;
    }
  });

  document.getElementById('searchNode').addEventListener('keydown', (event) => {
    if (event.key === 'Enter') searchAction();
  });

  window.addEventListener('resize', () => renderGraph());
}

bindEvents();
loadCurrentUser();
loadGraph();
