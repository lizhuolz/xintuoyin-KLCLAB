<template>
 <el-menu :default-active="activeMenu" class="el-menu-vertical-demo" background-color="#fff" text-color="#333"
    active-text-color="#1677ff" unique-opened router>
    <MenuItem :menu-list="menuList" />
  </el-menu>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { defineProps } from 'vue'
import MenuItem from './MenuItem.vue'

const props = defineProps({
  menuList: {
    type: Array,
    default: () => []
  }
})
const route = useRoute()
const activeMenu = ref(route.path)
</script>

<style scoped>
.el-menu-vertical-demo {
  min-height: 200px;
  border-right: 1px solid #f0f0f0;
}

</style>