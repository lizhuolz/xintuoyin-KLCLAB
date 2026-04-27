<template>
    <div class="main-layout">
        <div class="main-body">
            <!-- 侧边菜单 -->
            <AMenu class="main-aside" :style="{ width: isCollapse ? '64px' : '260px' }" />
            <div class="main-content-body" :class="{ 'full-width': isFullWidth }">
                <div class="inner-header" v-if="!isFullWidth">
                    <Breadcrumb />
                </div>
                <div class="container" :class="{ 'no-header': isFullWidth }">
                    <div class="content">
                        <router-view />
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { computed, ref, reactive, provide } from 'vue'
import { useRoute } from 'vue-router'
import AMenu from '@/components/main-menu/a-menu.vue'
import Breadcrumb from '@/components/Breadcrumb.vue'

const route = useRoute()
const isCollapse = ref(false)
function toggleCollapse() { isCollapse.value = !isCollapse.value }
provide('layout', reactive({ isCollapse, toggleCollapse }))
const isFullWidth = computed(() => route.meta?.fullWidth === true)
</script>

<style scoped>
.main-layout {
    height: 100vh;
    width: 100vw;
    display: flex;
    flex-direction: column;
}

.main-body {
    flex: 1;
    height: 100vh;
    display: flex;
    min-height: 0;
}

.main-aside {
    width: 260px;
    flex-shrink: 0;
    height: 100%;
    overflow-y: auto;
    transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);

    &::webkit-scrollbar {
        width: 0;
    }
}

.main-content-body {
    flex: 1;
    background: #fff;
    overflow: auto;
    min-width: 0;
}

.main-content-body.full-width {
    display: flex;
    flex-direction: column;
}

.inner-header {
    width: 100%;
    height: 40px;
    display: flex;
    align-items: center;
    padding: 8px 16px 0 24px;
    box-sizing: border-box;
    margin-bottom: 8px;
}

.container {
    height: calc(100% - 40px - 8px);
    padding: 0 24px 24px 24px;
    border-radius: 8px;
    box-sizing: border-box;
}

.container.no-header {
    height: 100%;
    padding: 0;
}

.content {
    width: 100%;
    height: 100%;
}
</style>
