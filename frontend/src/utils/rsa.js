/**TS*/
import { JSEncrypt } from "jsencrypt"
// rsa加密
export const rsaEncryption = function (data) {
  const Je = new JSEncrypt({ default_key_size: "1024" })
  Je.setPublicKey("MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAiMcFUQYWUy9qVFkFVrJhk0GLMJerV11CWycB/Io+2OOYaBtLxxN+vpKKbZSaTAobJ/fSnJEOwc4CJooluBR770E9HfWyAeVk+4lqy1oFckFuN8L0RvfLCTtvUK1V+71EF5efDUY1JOtQPACsB1uqQrBn4vqI98eXjfMx5ACgTpwKt95v1bJaFO9+SdIxZ/VAJc0Q4nPiwda30Vq9cxGaGQGoXRtdvBvL3Nee2XgtVy/NUInqGw5/c9Xoeu+5qyIqy8S9aFz+5dXjLpGIpkHLeXvyzzkPJ1QQPz20jv+FRmG47uFYmkrPhpUpnC+sgcCTVf5JbCI3Ky0cXkUomPtWbwIDAQAB"
  )
  if (data instanceof Object) {
    data = JSON.stringify(data)
  }
  return Je.encrypt(data)
}
