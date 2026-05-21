# Day 01 环境准备记录

## 今日目标

完成 Campus AI Agent 项目的本地环境准备。

## 已完成内容

- 下载 Agent Service Toolkit 原项目
- 将项目目录重命名为 campus-ai-agent
- 创建 conda 环境 campus_agent
- Python 版本：3.11.15
- 使用 uv 安装项目依赖
- uv 自动创建项目虚拟环境 .venv
- 复制 .env.example 为 .env
- 当前项目路径：/Users/dimensions/Developer/ai-agent-projects/campus-ai-agent

## 当前项目结构

项目根目录包含：

- src：核心源码
- tests：测试代码
- docs：项目文档
- data：数据目录
- docker：Docker 相关配置
- pyproject.toml：项目依赖配置
- uv.lock：uv 锁定依赖文件
- compose.yaml：Docker Compose 配置
- README.md：项目说明文档

## 项目启动方式

根据 README，目前项目推荐命令如下：

### 安装依赖

```bash
uv sync --frozen




