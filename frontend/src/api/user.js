// src/api/user.js
import request from "@/utils/request";

// 账号密码登录
export const loginByPwd = (params = {}) => {
  return request({
    url: "",
    method: "POST",
    params, 
  });
};
//获取租户列表
export const getTenantList = (params = {}) => {
  return request({
    url: "",
    method: "GET",
    params, 
  });
};
//选择租户登录
export const tenantLogin = (tenantId) => {
  return request({
    url: ``,
    method: "GET",
  });
};
//获取菜单
export const getMenuApi = () => {
  return request({
    url: "",
    method: "GET"
  });
};

export const logout = () => {
  return request({
    url: "",
    method: "POST",
  });
};

export const getUserInfo = () => {
  return request({
    url: "",
    method: "GET",
  });
};