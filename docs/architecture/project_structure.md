# Day 03 项目结构说明

## 一、今日目标

Day 03 的主要目标是理解 Campus AI Agent 项目的整体目录结构，明确前端、后端、Agent、配置、数据结构、记忆模块和测试模块分别位于哪里，为后续将原项目改造成校园智能助理打基础。

本项目基于 Agent Service Toolkit 二次开发，核心技术栈包括：

- LangGraph
- FastAPI
- Streamlit
- Pydantic
- uv
- Docker
- Tests

---

## 二、项目根目录结构

当前项目根目录主要包含以下内容：

```text
campus-ai-agent
├── src
├── tests
├── docs
├── data
├── docker
├── scripts
├── media
├── privatecredentials
├── pyproject.toml
├── uv.lock
├── compose.yaml
├── codecov.yml
├── langgraph.json
├── README.md
└── LICENSE
