<template>
  <div class="ai-dashboard">
    <div class="hero-card">
      <div>
        <p class="eyebrow">AI Workspace</p>
        <h1>后端契约已切换到 `code / msg / data`，这里是适配后的前端入口。</h1>
        <p class="summary">聊天、历史、反馈、知识库 4 个模块现在都按新的后端 API 结构工作，并统一了错误处理与状态回写。</p>
      </div>
      <router-link to="/ai/chat" class="hero-action">进入对话</router-link>
    </div>

    <div class="module-grid">
      <router-link v-for="item in modules" :key="item.to" :to="item.to" class="module-card">
        <div class="module-tag">{{ item.tag }}</div>
        <h3>{{ item.title }}</h3>
        <p>{{ item.desc }}</p>
      </router-link>
    </div>
  </div>
</template>

<script setup>
const modules = [
  { to: '/ai/chat', tag: 'Chat', title: 'AI 对话', desc: '新会话、历史切换、反馈提交、思考过程展示。' },
  { to: '/ai/history', tag: 'History', title: '历史记录', desc: '按时间与关键字检索，并导出对话清单。' },
  { to: '/ai/feedback-positive', tag: 'Feedback', title: '正向反馈', desc: '查看点赞记录，处理并收录优秀回答。' },
  { to: '/ai/feedback-negative', tag: 'Feedback', title: '负向反馈', desc: '查看点踩详情、图片附件和处理状态。' },
  { to: '/ai/kb', tag: 'Knowledge', title: '知识库管理', desc: '创建、编辑、上传与删除知识库文件。' },
]
</script>

<style scoped lang="less">
.ai-dashboard { min-height: 100vh; padding: 28px; background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%); }
.hero-card { display: flex; justify-content: space-between; gap: 24px; padding: 28px; border-radius: 28px; background: linear-gradient(135deg, #11243f 0%, #1f4a86 54%, #5ca1f5 100%); color: #fff; box-shadow: 0 24px 48px rgba(17, 36, 63, 0.18); }
.eyebrow { margin: 0 0 12px; font-size: 12px; letter-spacing: 0.16em; text-transform: uppercase; opacity: 0.76; }
.hero-card h1 { margin: 0; max-width: 760px; font-size: 32px; line-height: 1.3; }
.summary { margin: 16px 0 0; max-width: 760px; color: rgba(255, 255, 255, 0.82); line-height: 1.7; }
.hero-action { align-self: flex-end; display: inline-flex; align-items: center; justify-content: center; padding: 12px 18px; border-radius: 999px; background: #fff; color: #163661; text-decoration: none; font-weight: 600; min-width: 120px; }
.module-grid { margin-top: 24px; display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 18px; }
.module-card { display: flex; flex-direction: column; gap: 12px; padding: 22px; border-radius: 22px; background: #fff; border: 1px solid #e7edf6; text-decoration: none; color: #24344c; box-shadow: 0 10px 24px rgba(20, 40, 80, 0.05); transition: transform 0.2s ease, box-shadow 0.2s ease; }
.module-card:hover { transform: translateY(-4px); box-shadow: 0 16px 28px rgba(20, 40, 80, 0.1); }
.module-tag { display: inline-flex; width: fit-content; padding: 6px 10px; border-radius: 999px; background: #edf4ff; color: #2f6de6; font-size: 12px; font-weight: 600; }
.module-card h3 { margin: 0; font-size: 20px; }
.module-card p { margin: 0; color: #5a6982; line-height: 1.7; }
@media (max-width: 900px) {
  .hero-card { flex-direction: column; }
  .hero-action { align-self: flex-start; }
}
</style>
