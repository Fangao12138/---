# 区块链版权管理与引用溯源系统

这是一个基于 Flask + SQLite + 自定义区块链结构的版权登记系统，支持作品上链、版权转让与引用溯源。

## 功能
- 用户注册与登录
- 作品上传与版权登记（内容哈希上链）
- 版权转让与所有权验证
- 区块链浏览器查看区块与交易
- 引用溯源：记录作品引用关系并查询上下游溯源链路

## 技术栈
- Python 3.9+
- Flask
- Flask-SQLAlchemy
- Flask-Login
- SQLite

## 快速启动
```bash
pip install -r requirements.txt
python run.py
```

打开浏览器访问：`http://localhost:5000`

## 主要路由
- 首页：`/`
- 上传作品：`/upload`
- 版权详情：`/copyright/<id>`
- 溯源接口：`/api/trace/<copyright_id>`
- 区块浏览器：`/blockchain/explorer`

## 目录结构
```text
app/
  models/        # 数据模型
  routes/        # 路由与业务逻辑
  templates/     # 页面模板
  static/        # 静态资源
run.py           # 启动入口
```
