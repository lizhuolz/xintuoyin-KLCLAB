<template>
  <div class="app">
    <router-view />
  </div>
</template>
<script setup>


</script>
<style>
.app {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100vw;
  height: 100vh;
}

.el-menu .el-sub-menu__title+.el-menu .el-menu-item {
  padding-left: 70px !important;
}

.el-drawer__header {
  margin-bottom: 0 !important;
  border-bottom: 1px solid #eee;
  padding: 16px 16px 16px 24px !important;
}

.el-drawer__footer {
  border-top: 1px solid #eee;
}

.el-pagination.is-background .btn-next.is-active,
.el-pagination.is-background .btn-prev.is-active,
.el-pagination.is-background .el-pager li.is-active {
  background-color: var(--primary-blue) !important;
}

.el-radio__input.is-checked .el-radio__inner {
  background-color: var(--primary-blue) !important;
  border-color: var(--primary-blue) !important;
}

.el-radio__input.is-checked+.el-radio__label {
  color: var(--primary-blue) !important;
  ;
}

/* .el-dialog{
  padding: 24px 0 !important;
} */
.el-dialog__footer {
  padding: 12px 24px !important;
}

.el-dialog__header {
  padding-bottom: 0 !important;
}

.el-drawer__title {
  font-weight: 500;
  font-size: 16px;
  color: #3D3D3D;
}

</style>
