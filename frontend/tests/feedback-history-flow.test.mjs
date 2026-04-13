import assert from 'node:assert/strict'

const API_BASE = process.env.API_BASE || process.env.VITE_API_BASE || 'http://127.0.0.1:8000/api'
const CHAT_TIMEOUT_MS = Number(process.env.FEEDBACK_HISTORY_TEST_TIMEOUT_MS || 180000)

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

async function createSession() {
  const response = await fetch(apiUrl('/chat/new_session'))
  assert.equal(response.ok, true, `new_session failed: ${response.status}`)
  const payload = await readJson(response, 'new_session returned non-json')
  assert.equal(payload.code, 0)
  assert.equal(typeof payload.data?.conversation_id, 'string')
  return payload.data.conversation_id
}

async function createChatRound(conversationId) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), CHAT_TIMEOUT_MS)

  try {
    const response = await fetch(apiUrl('/chat'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conversation_id: conversationId,
        message: '点赞后历史详情校验',
        web_search: false,
        user_identity: 'frontend-test',
      }),
      signal: controller.signal,
    })
    const events = await readChatStream(response)
    const done = events.find((event) => event.type === 'done')
    assert.ok(done, 'chat stream should contain done event')
    assert.equal(done.data?.message_index, 0)
    return done.data
  } finally {
    clearTimeout(timeout)
  }
}

async function submitLike(conversationId, messageIndex) {
  const response = await fetch(apiUrl('/chat/feedback'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      conversation_id: conversationId,
      message_index: messageIndex,
      type: 'like',
    }),
  })
  assert.equal(response.ok, true, `feedback failed: ${response.status}`)
  const payload = await readJson(response, 'feedback returned non-json')
  assert.equal(payload.code, 0)
  return payload.data
}

async function getHistoryDetail(conversationId) {
  const response = await fetch(apiUrl(`/history/${encodeURIComponent(conversationId)}`))
  assert.equal(response.ok, true, `history detail failed: ${response.status}`)
  const payload = await readJson(response, 'history detail returned non-json')
  assert.equal(payload.code, 0)
  return payload.data
}

async function main() {
  const conversationId = await createSession()
  const chatData = await createChatRound(conversationId)

  const firstLike = await submitLike(conversationId, chatData.message_index)
  assert.equal(firstLike.state, 'like')

  const afterLike = await getHistoryDetail(conversationId)
  assert.equal(afterLike.messages[chatData.message_index].feedback, 'like')

  const secondLike = await submitLike(conversationId, chatData.message_index)
  assert.equal(secondLike.state, null)

  const afterToggle = await getHistoryDetail(conversationId)
  assert.equal(afterToggle.messages[chatData.message_index].feedback, null)

  console.log(JSON.stringify({
    ok: true,
    api_flow: [
      '/api/chat/new_session',
      '/api/chat',
      '/api/chat/feedback',
      '/api/history/{conversation_id}',
    ],
    conversation_id: conversationId,
    message_index: chatData.message_index,
    after_like_feedback: afterLike.messages[chatData.message_index].feedback,
    after_toggle_feedback: afterToggle.messages[chatData.message_index].feedback,
  }, null, 2))
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
