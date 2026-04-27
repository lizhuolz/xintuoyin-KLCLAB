async function requestJson(url) {
  const response = await fetch(url, {
    headers: {
      'Accept': 'application/json',
    },
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(`请求失败：${response.status} ${message}`);
  }
  return response.json();
}

export async function fetchGraph() {
  return requestJson('/api/combined_graph');
}

export async function fetchCurrentUser() {
  const response = await requestJson('/api/current-user');
  return response.data || response;
}

export async function fetchNodeDetail(nodeId) {
  return requestJson(`/api/node/${encodeURIComponent(nodeId)}`);
}

export async function searchNodes(keyword) {
  const query = new URLSearchParams({ keyword });
  return requestJson(`/api/search?${query.toString()}`);
}
