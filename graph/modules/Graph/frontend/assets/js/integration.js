
const externalWorkspaceBadge = document.getElementById('externalWorkspaceBadge');
const externalTabGroup = document.getElementById('externalTabGroup');
const deleteExternalButton = document.getElementById('btnDeleteExternal');
const refreshExternalButton = document.getElementById('btnRefreshExternal');
const externalFrame = document.getElementById('externalFrame');
const externalWorkspaceSummary = document.getElementById('externalWorkspaceSummary');
const workspaceMessage = document.getElementById('workspaceMessage');
const views = {
  internal: document.getElementById('internalWorkspace'),
  external: document.getElementById('externalWorkspace'),
};
const tabButtons = [...document.querySelectorAll('.workspace-tab[data-view]')];
const internalTabButton = document.querySelector('.workspace-tab[data-view="internal"]');
const loginStateToggle = document.getElementById('loginStateToggle');
const loginStateText = document.getElementById('loginStateText');

let isLoggedIn = true;

function updateLoginStateUI() {
  if (isLoggedIn) {
    loginStateText.textContent = '登录状态';
    internalTabButton?.classList.remove('hidden');
  } else {
    loginStateText.textContent = '未登录';
    internalTabButton?.classList.add('hidden');
    if (views.internal.classList.contains('active')) {
      switchView('external');
    }
  }
}

loginStateToggle?.addEventListener('change', (e) => {
  isLoggedIn = e.target.checked;
  updateLoginStateUI();
});

function showMessage(text, isError = false) {
  workspaceMessage.textContent = text;
  workspaceMessage.classList.remove('hidden');
  workspaceMessage.style.borderColor = isError ? '#f3c7c2' : '#cfe0ff';
  workspaceMessage.style.background = isError ? '#fff3f2' : '#eff5ff';
  workspaceMessage.style.color = isError ? '#b42318' : '#22437d';
  window.clearTimeout(showMessage._timer);
  showMessage._timer = window.setTimeout(() => {
    workspaceMessage.classList.add('hidden');
  }, 4000);
}

function setWorkspaceExists(status) {
  const exists = Boolean(status?.exists);
  externalTabGroup.classList.toggle('hidden', !exists);
  externalWorkspaceBadge.textContent = exists
    ? `系统外子界面：已创建（节点 ${status.node_count ?? 0} / 关系 ${status.link_count ?? 0}）`
    : '系统外子界面：未创建';

  const files = status?.files || [];
  externalWorkspaceSummary.textContent = exists
    ? `当前已接入 ${files.length} 个上传文件：${files.join('、') || '未记录文件名'}`
    : '系统外知识图谱子界面未创建。';

  if (!exists && views.external.classList.contains('active')) {
    switchView('internal');
  }
}

function switchView(view) {
  for (const [name, node] of Object.entries(views)) {
    const active = name === view;
    node.classList.toggle('hidden', !active);
    node.classList.toggle('active', active);
  }
  for (const button of tabButtons) {
    button.classList.toggle('active', button.dataset.view === view);
  }
}

function refreshExternalFrame() {
  externalFrame.src = `/external-view?ts=${Date.now()}`;
}

async function loadWorkspaceStatus() {
  const response = await fetch('/external/workspace/status', {
    headers: { 'Accept': 'application/json' },
  });
  if (!response.ok) {
    throw new Error('获取系统外子界面状态失败');
  }
  const resJson = await response.json();
  const status = resJson.data || resJson; // Compatible with old and new format
  setWorkspaceExists(status);
  return status;
}

async function deleteExternalWorkspace() {
  deleteExternalButton.disabled = true;
  try {
    const response = await fetch('/external/workspace/clear', { method: 'POST' });
    const resJson = await response.json();
    const payload = resJson.data || resJson;
    if (!response.ok) {
      throw new Error(payload.error || payload.message || '删除失败');
    }
    setWorkspaceExists(payload);
    switchView('internal');
    refreshExternalFrame();
    showMessage(payload.message || '系统外知识图谱子界面已删除。');
  } finally {
    deleteExternalButton.disabled = false;
  }
}

for (const button of tabButtons) {
  button.addEventListener('click', () => {
    const targetView = button.dataset.view;
    if (targetView === 'external' && externalTabGroup.classList.contains('hidden')) {
      showMessage('系统外知识图谱子界面未创建。', true);
      return;
    }
    if (targetView === 'external') {
      refreshExternalFrame();
    }
    switchView(targetView);
  });
}

refreshExternalButton?.addEventListener('click', refreshExternalFrame);
deleteExternalButton?.addEventListener('click', async () => {
  const ok = window.confirm('确认删除当前系统外知识图谱子界面及其上传文件吗？');
  if (!ok) return;
  try {
    await deleteExternalWorkspace();
  } catch (error) {
    console.error(error);
    showMessage(error.message || '删除失败', true);
  }
});

loadWorkspaceStatus().catch((error) => {
  console.error(error);
  showMessage(error.message || '初始化系统外子界面状态失败', true);
});

updateLoginStateUI();
