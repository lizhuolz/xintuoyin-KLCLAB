<template>
    <div class="main-layout">
        <!-- Header Removed -->
        <div class="main-body">
            <!-- 菜单 -->
            <!-- <main-menu class="main-aside" :menu-list="menuList[0]?.childMenuList || []"  /> -->
            <AMenu class="main-aside" :style="{ width: layoutStore.isCollapse ? '64px' : '260px' }" />
            <div class="main-content-body">
                <div class="inner-header">
                    <!-- 面包屑导航 + 用户信息 -->
                    <Breadcrumb />
                </div>
                <div class="container">
                    <div class="content">
                        <router-view />
                    </div>
                    <footer class="main-footer">
                        <div class="footer-content">
                            <span style="margin-right: 20px;">©2025-新拓银（深圳）人工智能科技有限公司. All rights reserved. </span>
                            <span style="margin-right: 20px;">备案号：渝ICP备2024037824号-1</span>
                            <span style="margin-right: 20px;">公网安备 494号待定</span>
                            <span style="margin-right: 20px;">v1.0.0.20250203_Base_91320100MA25M8A78N</span>
                            <a href="#" class="footer-link">用户协议</a>
                            <a href="#" class="footer-link">隐私政策</a>
                            <a href="#" class="footer-link">联系我们</a>
                        </div>
                    </footer>
                </div>
            </div>
        </div>

    </div>
</template>

<script setup>
import AMenu from '@/components/main-menu/a-menu.vue';
import Breadcrumb from '@/components/Breadcrumb.vue';
import { useLayoutStore } from '@/stores/layout';

const layoutStore = useLayoutStore();
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
    height: 100vh; /* Full height now */
    display: flex;
    min-height: 0;
}

.main-aside {
    width: 260px;
    flex-shrink: 0;
    height: 100%;
    overflow-y: auto;
    /* Match the menu text transition curve for sync */
    transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1); 

    &::webkit-scrollbar {
        width: 0;
    }
}

.main-content-body {
    flex: 1;
    background: fff;
    /* padding: 0 24px 24px 24px; */
    overflow: auto;
    min-width: 0;
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

.content {
    width: 100%;
    height: 100%;
    /* background-color: #fff; */
}

.main-footer {
    width: 100%;
    height: 21px;
    background: transparent;
    color: #bfc6ce;
    font-size: 12px;
    line-height: 21px;
    text-align: center;
    flex-shrink: 0;
    position: relative;
    z-index: 10;
    overflow: hidden;
}

.footer-content {
    width: 100%;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
}

.footer-link {
    color: #bfc6ce;
    text-decoration: none;
    margin: 0 2px;
}

.footer-link:hover {
    text-decoration: underline;
}

.footer-version {
    color: #bfc6ce;
    margin: 0 2px;
}
</style>