<template>
    <div class="sidebar-wrapper">
        <el-menu 
            :default-active="activeMenu" 
            class="el-menu-vertical-demo"
            background-color="#ffffff" 
            text-color="#444746" 
            active-text-color="#1f1f1f" 
            unique-opened 
            router
            :collapse="layoutStore.isCollapse"
            :collapse-transition="false"
        >
            <div class="el-menu-item toggle-item" @click="layoutStore.toggleCollapse">
                <div class="icon-container">
                    <el-icon size="18">
                        <Expand v-if="layoutStore.isCollapse" />
                        <Fold v-else />
                    </el-icon>
                </div>
                <span class="menu-text">收起菜单</span>
            </div>

            <el-menu-item index="/home">
                <el-icon class="fixed-icon"><HomeFilled /></el-icon>
                <template #title>
                    <span class="menu-text">首页</span>
                </template>
            </el-menu-item>

            <el-menu-item index="/ai/chat">
                <el-icon class="fixed-icon"><ChatDotRound /></el-icon>
                <template #title>
                    <span class="menu-text">AI 对话</span>
                </template>
            </el-menu-item>
        </el-menu>
    </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { HomeFilled, ChatDotRound, Fold, Expand } from '@element-plus/icons-vue'
import { useLayoutStore } from '@/stores/layout'

const route = useRoute()
const layoutStore = useLayoutStore()
const activeMenu = computed(() => route.path)
</script>

<style scoped lang="less">
.sidebar-wrapper {
    height: 100%;
    display: flex;
    flex-direction: column;
    border-right: 1px solid #e0e0e0;
}

.el-menu-vertical-demo {
    flex: 1;
    border-right: none;
    padding: 12px 0;
    width: 100% !important;
}

/* =================================================================
   1. 核心布局：通用样式
   ================================================================= */
:deep(.el-menu-item) {
    margin: 4px 10px;
    height: 44px;
    line-height: 44px;
    border-radius: 22px;
    border: none;
    font-size: 14px;
    font-weight: 500;
    padding: 0 !important; 
    display: flex;
    align-items: center;
    box-sizing: border-box;
    /* 这里的 transition 只负责 item 容器本身的背景色等，不负责文字 */
    transition: background-color 0.3s;
}

:deep(.el-icon),
.icon-container {
    width: 44px !important; 
    display: flex;
    justify-content: center;
    align-items: center;
    flex-shrink: 0; 
    margin: 0 !important;
    font-size: 18px;
    text-align: center;
}

/* =================================================================
   2. 文字动画核心逻辑 (The Magic)
   ================================================================= */
.menu-text {
    /* 默认状态 (展开) */
    opacity: 1;
    margin-left: 8px;
    white-space: nowrap;
    overflow: hidden;
    
    /* 使用 max-width 而不是 width。
       width: auto 无法做 transition 动画，必须给一个具体的像素上限。
       150px 足够容纳大多数菜单文字。
    */
    max-width: 150px; 

    /* 展开时的动画 (Fade In):
       1. max-width 先动，把空间撑开。
       2. opacity 稍微延迟 (0.1s)，等空间有了再显示文字，实现"淡入"。
    */
    transition: max-width 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                margin-left 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                opacity 0.3s cubic-bezier(0.4, 0, 0.2, 1) 0.1s;
}

.toggle-item {
    cursor: pointer;
    user-select: none;
    display: flex;
    align-items: center;
}

/* =================================================================
   3. 收起状态 (Collapse)
   ================================================================= */

/* 强制锁定容器宽度 */
:deep(.el-menu--collapse .el-menu-item),
:deep(.el-menu--collapse .toggle-item) {
    /* width: 44px !important; Removed to allow smooth shrinking */
    margin-left: 10px !important;
    margin-right: 10px !important;
}

/* 收起状态下的文字处理 
   这里是解决“一瞬间消失”的关键
*/
:deep(.el-menu--collapse .menu-text),
:deep(.el-menu--collapse .el-menu-item span) {
    /* 1. 变透明 */
    opacity: 0;
    /* 2. 宽度缩为 0 (这会产生滑动的挤压效果) */
    max-width: 0;
    /* 3. 去掉间距 */
    margin-left: 0;
    
    /* 覆盖 Element 可能的 display: none，确保动画能执行 */
    display: inline-block !important; 

    /* 收起时的动画 (Fade Out):
       1. opacity 快速变为 0 (0.15s)，实现"淡出"，避免文字挤压。
       2. max-width 正常收缩 (0.3s)。
       注意：这里必须显式重写 transition，否则会继承 .menu-text 的延迟效果。
    */
    transition: opacity 0.15s cubic-bezier(0.4, 0, 0.2, 1),
                max-width 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                margin-left 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* 针对 Element Plus 内部结构的额外修复 */
:deep(.el-menu--collapse .el-menu-item template) {
    display: block !important; 
}

/* Tooltip 修复 */
:deep(.el-menu--collapse .el-menu-tooltip__trigger) {
    padding: 0 !important;
    width: 44px !important;
    justify-content: center !important;
}
</style>