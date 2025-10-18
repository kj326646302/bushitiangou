# Novel Scanner - 小说扫书工具

一个基于多AI API的小说自动扫书和评分系统。

## 功能特性

✅ **多AI池管理** - 支持OpenAI、Gemini等多个AI提供商  
✅ **智能文本分割** - 根据模型上下文自动分割文本  
✅ **任务抢占机制** - 多AI并发处理，自动负载均衡  
✅ **失败重试** - 自动重试，支持切换模型  
✅ **流水线引擎** - 可配置的多阶段处理流程  
✅ **模板引擎** - 支持Jinja2模板和变量替换  
✅ **评分与标签** - 自动评分并生成标签

## 安装

```bash
# 安装依赖
pip install -r requirements.txt

# 或使用uv
uv sync
```

## 快速开始

### 1. 配置AI提供商

复制示例配置：
```bash
cp novel_scanner/config/ai_providers.example.yaml novel_scanner/config/ai_providers.yaml
```

编辑 `ai_providers.yaml` 并填入你的API密钥：
```yaml
providers:
  - name: gpt4
    type: openai
    model: gpt-4-turbo-preview
    api_key: "your-api-key"  # 或使用 api_key_env: "OPENAI_API_KEY"
    context_length: 128000
    rpm_limit: 500
    max_concurrent: 5
    priority: 1
```

### 2. 配置处理流水线

复制示例配置：
```bash
cp novel_scanner/config/pipeline.example.yaml novel_scanner/config/pipeline.yaml
```

流水线配置示例：
```yaml
pipeline:
  name: "默认扫书流程"
  stages:
    - id: split
      type: preprocess
      description: "文本分割"
      
    - id: summary
      type: process
      description: "内容总结"
      inputs: ["split"]
      prompt: "summary.json"
      
    - id: merge
      type: aggregate
      description: "结果聚合"
      inputs: ["summary"]
      
    - id: score
      type: score
      description: "评分和打标签"
      inputs: ["merge"]
      prompt: "score.json"
```

### 3. 运行扫书

#### CLI方式

```bash
python -m novel_scanner.cli \
  --input novel.txt \
  --ai-config novel_scanner/config/ai_providers.yaml \
  --pipeline-config novel_scanner/config/pipeline.yaml \
  --prompts-dir novel_scanner/prompts \
  --output-dir ./output
```

#### Python API方式

```python
from novel_scanner import NovelScanner

scanner = NovelScanner(
    ai_config_path="novel_scanner/config/ai_providers.yaml",
    pipeline_config_path="novel_scanner/config/pipeline.yaml",
    prompts_dir="novel_scanner/prompts",
)

result = await scanner.scan_novel("novel.txt")
print(f"评分: {result['score']['score']}")
print(f"标签: {result['score']['tags']}")
```

## 提示词模板

提示词模板支持JSON和YAML格式，使用Jinja2语法：

```json
{
  "name": "内容总结",
  "system_prompt": "你是一个专业的小说分析助手。",
  "user_prompt": "请总结以下文本：\n\n{{text}}\n\n{% if world_info %}{{world_info}}{% endif %}"
}
```

### 可用变量

- `{{text}}` - 待处理的文本块
- `{{world_info}}` - 世界书/扫书规则（可选）
- 自定义变量通过metadata传递

## 高级配置

### AI Provider配置项

- `name` - Provider名称（唯一标识）
- `type` - Provider类型（openai/gemini）
- `model` - 模型名称
- `api_key` - API密钥（或使用api_key_env）
- `context_length` - 上下文长度
- `rpm_limit` - 每分钟请求限制
- `max_concurrent` - 最大并发数
- `priority` - 优先级（数字越小优先级越高）
- `retry_times` - 重试次数
- `timeout` - 超时时间（秒）

### Stage类型

1. **preprocess** - 预处理（文本分割）
2. **process** - 处理（AI推理）
3. **aggregate** - 聚合（合并结果）
4. **score** - 评分（提取评分和标签）

### Stage配置

```yaml
- id: summary
  type: process
  description: "总结内容"
  inputs: ["split"]  # 依赖的上游阶段
  prompt: "summary.json"
  ai_pool: ["gpt4", "gemini-pro"]  # 可用的AI列表
  config:
    temperature: 0.7
    max_tokens: 2000
    max_retries: 3
    max_concurrent: 5
```

## 架构设计

```
NovelScanner
├── Config Layer (配置层)
│   ├── AI Provider Config
│   └── Pipeline Config
├── Core Layer (核心层)
│   ├── AI Pool (AI池管理)
│   ├── Text Splitter (文本分割)
│   ├── Task Queue (任务队列)
│   └── Pipeline Engine (流水线引擎)
├── Provider Layer (提供商层)
│   ├── OpenAI Provider
│   ├── Gemini Provider
│   └── Base Provider
└── Prompts Layer (提示词层)
    └── Template Engine
```

## 开发路线图

- [x] Phase 1: 核心功能
  - [x] AI Provider抽象层
  - [x] AI池管理
  - [x] 文本分割
  - [x] 任务队列
  - [x] 流水线引擎
  - [x] CLI工具

- [ ] Phase 2: SillyTavern兼容
  - [ ] 酒馆格式导入
  - [ ] 世界书增强
  - [ ] 变量扩展

- [ ] Phase 3: 高级功能
  - [ ] Web UI
  - [ ] 批量处理
  - [ ] 断点续传
  - [ ] 实时监控
  - [ ] 更多AI Provider

## 贡献

欢迎提交Issue和Pull Request！

## 许可证

见主项目LICENSE文件
