import request from '@/utils/request'

export const API_BASE = import.meta.env.VITE_API_BASE || '/api'

function accessToken() {
  return localStorage.getItem('token') || import.meta.env.VITE_DEV_TOKEN || ''
}

function buildUrl(path) {
  if (/^https?:\/\//.test(path)) return path
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`
}

function buildHeaders(extraHeaders = {}) {
  const headers = { ...extraHeaders }
  const token = accessToken()
  if (token) headers.accessToken = token
  return headers
}

async function readErrorPayload(response, fallbackMessage = '请求失败') {
  try {
    const payload = await response.json()
    return payload?.msg || fallbackMessage
  } catch (error) {
    return response.statusText || fallbackMessage
  }
}

function parseSSEEventBlock(block) {
  const lines = block.split(/\r?\n/)
  const dataLines = []
  for (const line of lines) {
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart())
    }
  }
  if (!dataLines.length) return null
  try {
    return JSON.parse(dataLines.join('\n'))
  } catch (error) {
    return null
  }
}

function parseFilenameFromDisposition(disposition, fallback = 'download.bin') {
  if (!disposition) return fallback
  // 优先匹配 RFC 5987: filename*=UTF-8''xxx
  const rfc5987 = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (rfc5987?.[1]) {
    try { return decodeURIComponent(rfc5987[1]) } catch { /* ignore */ }
  }
  // 回退：filename="xxx"
  const basic = disposition.match(/filename="?([^";]+)"?/i)
  return basic?.[1] || fallback
}


async function consumeSSEStream(response, onEvent) {
  if (!response.body) {
    throw new Error('浏览器不支持流式读取')
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })

    let boundary = buffer.indexOf('\n\n')
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      const event = parseSSEEventBlock(block)
      if (event) onEvent?.(event)
      boundary = buffer.indexOf('\n\n')
    }

    if (done) {
      if (buffer.trim()) {
        const event = parseSSEEventBlock(buffer)
        if (event) onEvent?.(event)
      }
      break
    }
  }
}

async function consumeTextStream(response, onChunk) {
  if (!response.body) {
    return response.text()
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let fullText = ''

  while (true) {
    const { value, done } = await reader.read()
    const chunk = decoder.decode(value || new Uint8Array(), { stream: !done })
    if (chunk) {
      fullText += chunk
      onChunk?.(chunk, fullText)
    }
    if (done) break
  }
  return fullText
}

export function unwrapResponse(response, fallbackMessage = '请求失败') {
  if (!response || typeof response !== 'object') {
    throw new Error(fallbackMessage)
  }
  if (response.code !== 0) {
    throw new Error(response.msg || fallbackMessage)
  }
  return response.data ?? {}
}

export function formatTimestamp(value, fallback = '-') {
  if (value === null || value === undefined || value === '') return fallback
  const num = Number(value)
  if (!Number.isNaN(num) && num > 0) {
    return new Date(num).toLocaleString()
  }
  return String(value)
}

export function buildHistoryFileDownloadUrl(conversationId, messageIndex, fileId) {
  if (!conversationId || messageIndex === null || messageIndex === undefined || !fileId) return ''
  return `/history/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageIndex)}/files/${encodeURIComponent(fileId)}/download`
}

export function flattenHistoryMessages(historyData) {
  const rounds = Array.isArray(historyData?.messages) ? historyData.messages : []
  return rounds.flatMap((item) => {
    const messageIndex = item?.message_index ?? null
    return [
      {
        role: 'user',
        content: item?.question || '',
        files: item?.files || [],
        uploadedFiles: item?.uploaded_files || [],
        messageIndex,
      },
      {
        role: 'assistant',
        content: item?.answer || '',
        sources: item?.resource || [],
        recommendations: item?.recommend_answer || [],
        thinkingText: item?.thinking_text || '',
        thinkingVisible: Boolean(item?.thinking_text),
        thinkingLoading: false,
        thinkingError: false,
        liked: item?.feedback === 'like',
        disliked: item?.feedback === 'dislike',
        feedback: item?.feedback ?? null,
        messageIndex,
      },
    ]
  })
}

export async function getPlainText(path) {
  const response = await fetch(buildUrl(path), { headers: buildHeaders() })
  if (!response.ok) {
    throw new Error(await readErrorPayload(response))
  }
  return response.text()
}

async function postJsonStream(path, payload, onEvent, options = {}) {
  const response = await fetch(buildUrl(path), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...buildHeaders(options.headers),
    },
    body: JSON.stringify(payload),
    signal: options.signal,
  })

  if (!response.ok) {
    throw new Error(await readErrorPayload(response, '发送对话失败'))
  }

  let donePayload = null
  let streamError = null
  await consumeSSEStream(response, (event) => {
    if (event?.type === 'done') {
      donePayload = event.data || {}
    }
    if (event?.type === 'error') {
      streamError = event.message || '流式请求失败'
    }
    onEvent?.(event)
  })

  if (streamError) {
    throw new Error(streamError)
  }
  return donePayload || {}
}

async function getTextStream(path, onChunk, options = {}) {
  const response = await fetch(buildUrl(path), {
    method: 'GET',
    headers: buildHeaders(options.headers),
    signal: options.signal,
  })
  if (!response.ok) {
    throw new Error(await readErrorPayload(response, '获取思考过程失败'))
  }
  return consumeTextStream(response, onChunk)
}

export const aiApi = {
  getEnums() {
    return request.get('/config/enums').then((res) => unwrapResponse(res, '获取系统配置失败'))
  },
  createChatSession() {
    return request.get('/chat/new_session').then((res) => unwrapResponse(res, '新建对话失败'))
  },
  async uploadFiles(files) {
    const list = Array.isArray(files) ? files : [files]
    if (!list.length) return { files: [] }
    const formData = new FormData()
    for (const file of list) {
      formData.append('files', file)
    }
    const response = await fetch(buildUrl('/upload'), {
      method: 'POST',
      headers: buildHeaders(),
      body: formData,
    })
    if (!response.ok) {
      throw new Error(await readErrorPayload(response, '上传文件失败'))
    }
    return unwrapResponse(await response.json(), '上传文件失败')
  },
  sendChatStream(payload, onEvent, options = {}) {
    return postJsonStream('/chat', payload, onEvent, options)
  },
  getChatThinking(conversationId, messageIndex) {
    return getTextStream(`/chat/${encodeURIComponent(conversationId)}/thinking?message_index=${encodeURIComponent(messageIndex)}`)
  },
  getChatThinkingStream(conversationId, messageIndex, onChunk, options = {}) {
    return getTextStream(`/chat/${encodeURIComponent(conversationId)}/thinking?message_index=${encodeURIComponent(messageIndex)}`, onChunk, options)
  },
  submitChatFeedback(payload) {
    return request.post('/chat/feedback', payload).then((res) => unwrapResponse(res, '提交反馈失败'))
  },
  listHistories(params = {}) {
    return request.get('/history/list', { params }).then((res) => unwrapResponse(res, '获取历史记录失败'))
  },
  getHistoryDetail(conversationId) {
    return request.get(`/history/${encodeURIComponent(conversationId)}`).then((res) => unwrapResponse(res, '获取历史详情失败'))
  },
  deleteConversation(conversationId) {
    return request.delete(`/chat/${encodeURIComponent(conversationId)}`).then((res) => unwrapResponse(res, '删除历史对话失败'))
  },
  batchDeleteHistories(ids) {
    return request.post('/history/batch_delete', { ids }).then((res) => unwrapResponse(res, '批量删除历史对话失败'))
  },
  async exportHistoryDetails(ids, searchParams) {
    const payload = ids ? { ids } : (searchParams || {})
    const response = await fetch(buildUrl('/history/export'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...buildHeaders(),
      },
      body: JSON.stringify(payload),
    })
    if (!response.ok) {
      throw new Error(await readErrorPayload(response, '导出历史记录失败'))
    }
    const blob = await response.blob()
    const disposition = response.headers.get('content-disposition') || ''
    return {
      blob,
      filename: parseFilenameFromDisposition(disposition, '对话日志.xlsx'),
    }
  },
  async downloadByUrl(url, fallbackMessage = '下载失败') {
    const response = await fetch(url.startsWith('http') ? url : buildUrl(url), {
      method: 'GET',
      headers: buildHeaders(),
    })
    if (!response.ok) {
      throw new Error(await readErrorPayload(response, fallbackMessage))
    }
    const blob = await response.blob()
    const disposition = response.headers.get('content-disposition') || ''
    return {
      blob,
      filename: parseFilenameFromDisposition(disposition, 'download.bin'),
    }
  },
  getFeedbackOptions() {
    return request.get('/feedback/reason_options').then((res) => unwrapResponse(res, '获取反馈选项失败'))
  },
  listFeedbacks(params = {}) {
    return request.get('/feedback/list', { params }).then((res) => unwrapResponse(res, '获取反馈列表失败'))
  },
  getFeedbackDetail(feedbackId) {
    return request.get(`/feedback/${encodeURIComponent(feedbackId)}`).then((res) => unwrapResponse(res, '获取反馈详情失败'))
  },
  processFeedback(payload) {
    return request.post('/feedback/process', payload).then((res) => unwrapResponse(res, '处理反馈失败'))
  },
  batchDeleteFeedback(ids) {
    return request.post('/feedback/batch_delete', { ids }).then((res) => unwrapResponse(res, '批量删除反馈失败'))
  },
  listKnowledgeBases(params = {}) {
    return request.get('/kb/list', { params }).then((res) => unwrapResponse(res, '获取知识库列表失败'))
  },
  createKnowledgeBase(payload) {
    return request.post('/kb/create', payload).then((res) => unwrapResponse(res, '创建知识库失败'))
  },
  updateKnowledgeBase(payload) {
    return request.post('/kb/update', payload).then((res) => unwrapResponse(res, '更新知识库失败'))
  },
  deleteKnowledgeBase(id) {
    return request.delete(`/kb/${encodeURIComponent(id)}`).then((res) => unwrapResponse(res, '删除知识库失败'))
  },
  getKnowledgeBaseDetail(id) {
    return request.get(`/kb/${encodeURIComponent(id)}`).then((res) => unwrapResponse(res, '获取知识库详情失败'))
  },
  listKnowledgeBaseFiles(id) {
    return request.get(`/kb/${encodeURIComponent(id)}/files`).then((res) => unwrapResponse(res, '获取知识库文件失败'))
  },
  getDbOptions() {
    return request.get('/db/options').then((res) => unwrapResponse(res, '获取数据库选项失败'))
  },
  selectDb(id) {
    return request.post('/db/select', { id }).then((res) => unwrapResponse(res, '切换数据库失败'))
  },
  addDatabase(payload) {
    return request.post('/db/add', payload).then((res) => unwrapResponse(res, '新增数据库失败'))
  },
  getDepartmentUsers() {
    return request.get('/department_users').then((res) => unwrapResponse(res, '获取部门人员失败'))
  },
  toggleKnowledgeBaseEnabled(id, enabled) {
    return request.post('/kb/toggle_enabled', { id, enabled }).then((res) => unwrapResponse(res, '切换知识库状态失败'))
  },
}
