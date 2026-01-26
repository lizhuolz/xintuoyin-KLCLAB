import request from "@/utils/request";

//获取文件前缀
export const getPrefixAddress = (params = {}) => {
    return request({
      url: "",
      method: "GET",
      params, 
    });
  };