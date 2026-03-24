import request from '@/utils/request'

export const API_BASE = import.meta.env.VITE_API_BASE || '/api'

function accessToken() {
  return localStorage.getItem('token') || ''
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

export function inferDateString(detail) {
  const candidates = [detail?.time, detail?.update_time, detail?.createdAt, detail?.updatedAt]
  for (const value of candidates) {
    if (value === null || value === undefined || value === '') continue
    const num = Number(value)
    if (!Number.isNaN(num) && num > 0) {
      const date = new Date(num)
      const y = date.getFullYear()
      const m = String(date.getMonth() + 1).padStart(2, '0')
      const d = String(date.getDate()).padStart(2, '0')
      return `${y}-${m}-${d}`
    }
    const text = String(value)
    const match = text.match(/(\d{4})[\/-](\d{2})[\/-](\d{2})/)
    if (match) {
      return `${match[1]}-${match[2]}-${match[3]}`
    }
  }
  return ''
}

export function buildFeedbackPictureUrl(detail, filename) {
  const date = inferDateString(detail)
  if (!detail?.id || !date || !filename) return ''
  return buildUrl(`/static/feedbacks/${date}/${detail.id}/${encodeURIComponent(filename)}`)
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

async function postFormStream(path, formData, onEvent, options = {}) {
  const streamFormData = new FormData()
  formData.forEach((value, key) => {
    streamFormData.append(key, value)
  })
  streamFormData.set('stream', 'true')

  const response = await fetch(buildUrl(path), {
    method: 'POST',
    headers: buildHeaders(options.headers),
    body: streamFormData,
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
  createChatSession() {
    return request.get('/chat/new_session').then((res) => unwrapResponse(res, '新建对话失败'))
  },
  sendChat(formData) {
    const payload = new FormData()
    formData.forEach((value, key) => payload.append(key, value))
    payload.set('stream', 'false')
    return request.post('/chat', payload, { timeout: 120000 }).then((res) => unwrapResponse(res, '发送对话失败'))
  },
  sendChatStream(formData, onEvent, options = {}) {
    return postFormStream('/chat', formData, onEvent, options)
  },
  getChatThinking(conversationId, messageIndex) {
    return getPlainText(`/chat/${encodeURIComponent(conversationId)}/thinking?message_index=${encodeURIComponent(messageIndex)}&stream=false`)
  },
  getChatThinkingStream(conversationId, messageIndex, onChunk, options = {}) {
    return getTextStream(`/chat/${encodeURIComponent(conversationId)}/thinking?message_index=${encodeURIComponent(messageIndex)}&stream=true`, onChunk, options)
  },
  submitChatFeedback(formData) {
    return request.post('/chat/feedback', formData).then((res) => unwrapResponse(res, '提交反馈失败'))
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
  listKnowledgeBases() {
    return request.get('/kb/list').then((res) => unwrapResponse(res, '获取知识库列表失败'))
  },
  createKnowledgeBase(formData) {
    return request.post('/kb/create', formData).then((res) => unwrapResponse(res, '创建知识库失败'))
  },
  updateKnowledgeBase(formData) {
    return request.post('/kb/update', formData).then((res) => unwrapResponse(res, '更新知识库失败'))
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
  uploadKnowledgeBaseFiles(id, files) {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    return request.post(`/kb/${encodeURIComponent(id)}/upload`, formData).then((res) => unwrapResponse(res, '上传知识库文档失败'))
  },
  deleteKnowledgeBaseFile(id, filename) {
    const formData = new FormData()
    formData.append('filename', filename)
    return request.post(`/kb/${encodeURIComponent(id)}/delete_file`, formData).then((res) => unwrapResponse(res, '删除知识库文档失败'))
  },
  deleteKnowledgeBaseFiles(id, filenames) {
    return request.post(`/kb/${encodeURIComponent(id)}/delete_files`, { filenames }).then((res) => unwrapResponse(res, '删除知识库文档失败'))
  },
}
