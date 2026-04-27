# 全局公共参数

**全局Header参数**

| 参数名 | 示例值 | 参数类型 | 是否必填 | 参数描述 |
| --- | --- | ---- | ---- | ---- |
| 暂无参数 |

**全局Query参数**

| 参数名 | 示例值 | 参数类型 | 是否必填 | 参数描述 |
| --- | --- | ---- | ---- | ---- |
| 暂无参数 |

**全局Body参数**

| 参数名 | 示例值 | 参数类型 | 是否必填 | 参数描述 |
| --- | --- | ---- | ---- | ---- |
| 暂无参数 |

**全局认证方式**

> 无需认证

# 状态码说明

| 状态码 | 中文描述 |
| --- | ---- |
| 暂无参数 |

# 企业端

> 创建人: LMC

> 更新人: LMC

> 创建时间: 2026-03-23 15:58:32

> 更新时间: 2026-03-23 15:58:32

```text
暂无描述
```

**目录Header参数**

| 参数名 | 示例值 | 参数类型 | 是否必填 | 参数描述 |
| --- | --- | ---- | ---- | ---- |
| 暂无参数 |

**目录Query参数**

| 参数名 | 示例值 | 参数类型 | 是否必填 | 参数描述 |
| --- | --- | ---- | ---- | ---- |
| 暂无参数 |

**目录Body参数**

| 参数名 | 示例值 | 参数类型 | 是否必填 | 参数描述 |
| --- | --- | ---- | ---- | ---- |
| 暂无参数 |

**目录认证信息**

> 继承父级

**Query**

## 获取个人信息

> 创建人: LMC

> 更新人: LMC

> 创建时间: 2026-03-23 16:02:33

> 更新时间: 2026-03-23 16:02:33

```text
暂无描述
```

**接口状态**

> 开发中

**接口URL**

> personal/center/my/info

**请求方式**

> GET

**Content-Type**

> none

**请求Header参数**

| 参数名 | 示例值 | 参数类型 | 是否必填 | 参数描述 |
| --- | --- | ---- | ---- | ---- |
| accessToken | {{accessTokenValue}} | string | 是 | - |

**认证方式**

> 继承父级

**响应示例**

* 成功(200)

```javascript
{
	"code": 0,
	"msg": "成功",
	"data": {
		"fullName": "张美琴琴",//员工姓名
		"phones": "19923719837",//员工电话
		"headSculpture": "r-d-local/e1/head-sculpture/1762076149836.png",//员工头像
		"enableStatusName": null,
		"roleStatusName": null,
		"lockStatusName": null,
		"initStatusName": null,
		"existWorkStatusName": null,
		"returneeStatusName": null,
		"foreignStatusName": null,
		"talentPlanStatusName": null,
		"categoryName": null,
		"employmentMethodName": null,
		"channelLogoOpenStatus": null,//渠道logo打开状态   7777=否， 9999=是
		"channelLogoAnnexUrl": null//渠道logo图片地址
	},
	"timeStamp": 1762409348329
}
```

| 参数名 | 示例值 | 参数类型 | 参数描述 |
| --- | --- | ---- | ---- |
| isStatus | true | boolean | - |
| code | 0 | string | - |
| msg | 成功 | string | - |
| data | - | object | - |
| data.id | 1 | integer | - |
| data.staffStatus | 7777 | integer | 员工状态(777=否,9999=是) |
| data.channelStatus | 9999 | integer | 渠道状态(777=否,9999=是) |
| data.account | 17762662 | string | 帐号 |
| data.phone | 13984687602 | string | 手机号 |
| data.mail | 12@qq.com | string | 邮箱 |
| data.promotionCode | - | string | 关联推广码 |
| data.protocol | true | boolean | 协议 |
| data.fullName | 1 | string | 姓名 |
| data.nickname | 1 | string | 昵称 |
| data.sex | 1 | integer | 性别 |
| data.age | 1 | integer | 年龄 |
| data.headPortraitUrl | - | string | 头像路径 |
| data.invitationStatus | 7777 | integer | 邀请权限(777=否,9999=是) |
| data.rebateRatioStatus | 7777 | integer | 设置返利比例权限(777=否,9999=是) |
| timeStamp | 1716169907656 | integer | - |

* 失败(404)

```javascript
暂无数据
```

**请求Header参数**

| 参数名 | 示例值 | 参数类型 | 是否必填 | 参数描述 |
| --- | --- | ---- | ---- | ---- |
| accessToken | {{accessTokenValue}} | string | 是 | - |

**Query**

# 管理端

> 创建人: LMC

> 更新人: LMC

> 创建时间: 2026-03-23 16:02:45

> 更新时间: 2026-03-23 16:04:09

```text
暂无描述
```

**目录Header参数**

| 参数名 | 示例值 | 参数类型 | 是否必填 | 参数描述 |
| --- | --- | ---- | ---- | ---- |
| 暂无参数 |

**目录Query参数**

| 参数名 | 示例值 | 参数类型 | 是否必填 | 参数描述 |
| --- | --- | ---- | ---- | ---- |
| 暂无参数 |

**目录Body参数**

| 参数名 | 示例值 | 参数类型 | 是否必填 | 参数描述 |
| --- | --- | ---- | ---- | ---- |
| 暂无参数 |

**目录认证信息**

> 继承父级

**Query**

## 获取个人信息

> 创建人: LMC

> 更新人: LMC

> 创建时间: 2026-03-23 16:03:10

> 更新时间: 2026-03-23 16:03:10

```text
暂无描述
```

**接口状态**

> 开发中

**接口URL**

> personal/center/my/info

**请求方式**

> GET

**Content-Type**

> none

**请求Header参数**

| 参数名 | 示例值 | 参数类型 | 是否必填 | 参数描述 |
| --- | --- | ---- | ---- | ---- |
| accessToken | {{accessTokenValue}} | string | 是 | - |

**认证方式**

> 继承父级

**响应示例**

* 成功(200)

```javascript
{
	"isStatus": true,
	"code": "0",
	"msg": "成功",
	"data": {
		"id": 1,
		"staffStatus": 7777,
		"channelStatus": 9999,
		"account": "17762662",
		"phone": "13984687602",
		"mail": "12@qq.com",
		"promotionCode": "",
		"protocol": true,
		"fullName": "1",
		"nickname": "1",
		"sex": 1,
		"age": 1,
		"headPortraitUrl": "",
		"invitationStatus": 7777,
		"rebateRatioStatus": 7777
	},
	"timeStamp": 1716169907656
}
```

| 参数名 | 示例值 | 参数类型 | 参数描述 |
| --- | --- | ---- | ---- |
| isStatus | true | boolean | - |
| code | 0 | string | - |
| msg | 成功 | string | - |
| data | - | object | - |
| data.id | 1 | integer | - |
| data.staffStatus | 7777 | integer | 员工状态(777=否,9999=是) |
| data.channelStatus | 9999 | integer | 渠道状态(777=否,9999=是) |
| data.account | 17762662 | string | 帐号 |
| data.phone | 13984687602 | string | 手机号 |
| data.mail | 12@qq.com | string | 邮箱 |
| data.promotionCode | - | string | 关联推广码 |
| data.protocol | true | boolean | 协议 |
| data.fullName | 1 | string | 姓名 |
| data.nickname | 1 | string | 昵称 |
| data.sex | 1 | integer | 性别 |
| data.age | 1 | integer | 年龄 |
| data.headPortraitUrl | - | string | 头像路径 |
| data.invitationStatus | 7777 | integer | 邀请权限(777=否,9999=是) |
| data.rebateRatioStatus | 7777 | integer | 设置返利比例权限(777=否,9999=是) |
| timeStamp | 1716169907656 | integer | - |

* 失败(404)

```javascript
暂无数据
```

**请求Header参数**

| 参数名 | 示例值 | 参数类型 | 是否必填 | 参数描述 |
| --- | --- | ---- | ---- | ---- |
| accessToken | {{accessTokenValue}} | string | 是 | - |

**Query**
