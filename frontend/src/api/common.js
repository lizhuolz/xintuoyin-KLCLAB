// src/api/common.js
import request from "@/utils/request";

// 上传文件
export const uploadFile = (file) => {
  const formData = new FormData();
  formData.append("file", file);
  return request({
    url: "/upload/file",
    method: "POST",
    data: formData,
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
};

// 获取字典数据
export const getDict = (type) => {
  return request({
    url: "/dict",
    method: "GET",
    params: { type },
  });
};

// 获取地区数据
export const getRegions = () => {
  return request({
    url: "/regions",
    method: "GET",
  });
};