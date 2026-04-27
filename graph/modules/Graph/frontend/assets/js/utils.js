export function deepClone(data) {
  return structuredClone(data);
}

export function walkTree(node, callback) {
  if (!node) return;
  callback(node);
  (node.children || []).forEach((child) => walkTree(child, callback));
}

export function findNodeById(node, nodeId) {
  if (!node) return null;
  if (node.id === nodeId) return node;
  for (const child of node.children || []) {
    const result = findNodeById(child, nodeId);
    if (result) return result;
  }
  return null;
}

export function findPathById(node, nodeId, path = []) {
  if (!node) return null;
  const nextPath = [...path, node.id];
  if (node.id === nodeId) return nextPath;
  for (const child of node.children || []) {
    const result = findPathById(child, nodeId, nextPath);
    if (result) return result;
  }
  return null;
}

export function expandAll(node) {
  walkTree(node, (item) => {
    item._collapsed = false;
  });
}

export function collapseToLevel(node, level) {
  walkTree(node, (item) => {
    item._collapsed = item.level >= level && !item.leaf;
  });
  node._collapsed = false;
}

export function ensureVisiblePath(root, nodeId) {
  const path = findPathById(root, nodeId);
  if (!path) return;
  for (const id of path) {
    const current = findNodeById(root, id);
    if (current) {
      current._collapsed = false;
    }
  }
}

export function buildVisibleTree(node) {
  const nextNode = {
    ...node,
    children: [],
    _childCount: (node.children || []).length,
    _hasHiddenChildren: !!node._collapsed && (node.children || []).length > 0,
  };
  if (!node._collapsed) {
    nextNode.children = (node.children || []).map((child) => buildVisibleTree(child));
  }
  return nextNode;
}
