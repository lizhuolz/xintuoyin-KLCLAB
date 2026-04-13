import assert from 'node:assert/strict'

const API_BASE = process.env.API_BASE || process.env.VITE_API_BASE || 'http://127.0.0.1:8000/api'
const CHAT_TIMEOUT_MS = Number(process.env.CHAT_UPLOAD_TEST_TIMEOUT_MS || 180000)

function apiUrl(path) {
  return `${API_BASE.replace(/\/$/, '')}${path.startsWith('/') ? path : `/${path}`}`
}

async function readJson(response, fallbackMessage) {
  const text = await response.text()
  try {
    return JSON.parse(text)
  } catch {
    throw new Error(`${fallbackMessage}: ${text.slice(0, 300)}`)
  }
}

async function createSession() {
  const response = await fetch(apiUrl('/chat/new_session'))
  assert.equal(response.ok, true, `new_session failed: ${response.status}`)
  const payload = await readJson(response, 'new_session returned non-json')
  assert.equal(payload.code, 0)
  assert.equal(typeof payload.data?.conversation_id, 'string')
  assert.ok(payload.data.conversation_id.length > 0)
  return payload.data.conversation_id
}

function parseSSEBlock(block) {
  const data = block
    .split(/\r?\n/)
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart())
    .join('\n')
  if (!data) return null
  return JSON.parse(data)
}

async function readChatStream(response) {
  assert.equal(response.ok, true, `chat failed: ${response.status}`)
  assert.match(response.headers.get('content-type') || '', /text\/event-stream/)

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  const events = []
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })

    let boundary = buffer.search(/\r?\n\r?\n/)
    while (boundary !== -1) {
      const separator = buffer.match(/\r?\n\r?\n/)
      const separatorLength = separator?.[0]?.length || 2
      const block = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + separatorLength)
      const event = parseSSEBlock(block)
      if (event) events.push(event)
      boundary = buffer.search(/\r?\n\r?\n/)
    }

    if (done) {
      if (buffer.trim()) {
        const event = parseSSEBlock(buffer)
        if (event) events.push(event)
      }
      break
    }
  }

  return events
}

async function chatWithFile(conversationId) {
  const formData = new FormData()
  const file = new Blob(['项目代号：北极星。交付日期：2026-04-15。'], { type: 'text/plain' })

  formData.append('conversation_id', conversationId)
  formData.append('message', '请根据附件告诉我项目代号和交付日期')
  formData.append('web_search', 'false')
  formData.append('user_identity', 'frontend-test')
  formData.append('files', file, 'frontend-upload-probe.txt')

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), CHAT_TIMEOUT_MS)

  // This is the important part: upload + chat use /api/chat directly.
  // /api/upload is not called because it only uploads files and does not trigger model answering.
  try {
    const response = await fetch(apiUrl('/chat'), {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    })
    return await readChatStream(response)
  } finally {
    clearTimeout(timeout)
  }
}

async function main() {
  const conversationId = await createSession()
  const events = await chatWithFile(conversationId)
  const done = events.find((event) => event.type === 'done')

  assert.ok(done, 'chat stream should contain done event')
  assert.equal(done.data?.message_index, 0)
  assert.equal(Array.isArray(done.data?.uploaded_files), true)
  assert.equal(done.data.uploaded_files.length, 1)
  assert.equal(done.data.uploaded_files[0].filename, 'frontend-upload-probe.txt')
  assert.equal(Array.isArray(done.data?.file_contexts), true)
  assert.match(done.data.file_contexts[0]?.text || '', /北极星/)
  assert.match(done.data.file_contexts[0]?.text || '', /2026-04-15/)

  console.log(JSON.stringify({
    ok: true,
    api_flow: ['/api/chat/new_session', '/api/chat'],
    not_required: '/api/upload',
    conversation_id: conversationId,
    message_index: done.data.message_index,
    uploaded_files: done.data.uploaded_files.map((item) => ({
      file_id: item.file_id,
      filename: item.filename,
    })),
  }, null, 2))
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
