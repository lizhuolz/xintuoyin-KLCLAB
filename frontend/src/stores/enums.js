import { defineStore } from 'pinia'
import { ref } from 'vue'
import { aiApi } from '@/api/ai'

export const useEnumsStore = defineStore('enums', () => {
  const data = ref({})
  const loaded = ref(false)

  async function load() {
    if (loaded.value) return
    try {
      data.value = await aiApi.getEnums()
      loaded.value = true
    } catch (e) {
      console.error('加载系统配置失败:', e)
    }
  }

  return { data, loaded, load }
})
