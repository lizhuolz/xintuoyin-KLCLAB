<template>
    <template v-for="item in menuList" :key="item.id">
      <el-sub-menu v-if="item.childMenuList && item.childMenuList.length" :index="item.id + ''">
        <template #title>
          <el-icon v-if="item.icon"><i :class="item.icon"></i></el-icon>
          <span>{{ item.name }}</span>
        </template>
        <MenuItem :menu-list="item.childMenuList" />
      </el-sub-menu>
      <el-menu-item v-else :index="item.apiUrl || item.pageUrl || (item.id + '')">
        <el-icon v-if="item.icon"><i :class="item.icon"></i></el-icon>
        <span>{{ item.name }}</span>
      </el-menu-item>
    </template>
  </template>
  
  <script setup>
  defineProps({
    menuList: {
      type: Array,
      default: () => []
    }
  });
  </script>