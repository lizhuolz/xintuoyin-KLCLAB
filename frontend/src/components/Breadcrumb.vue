<template>
  <div class="breadcrumb-container">
    <el-breadcrumb separator="/">
      <el-breadcrumb-item v-if="parentLabel">{{ parentLabel }}</el-breadcrumb-item>
      <el-breadcrumb-item>{{ currentTitle }}</el-breadcrumb-item>
    </el-breadcrumb>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const currentTitle = computed(() => route.meta?.title || '')
const parentLabel = computed(() => route.meta?.parent || '')
</script>

<style scoped>
.breadcrumb-container {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  padding: 0 4px;
}
</style>
