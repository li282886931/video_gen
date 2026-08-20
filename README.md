# 短视频批量生成流水线

这是一个可扩展的短视频生成脚本项目，目标是：

- 根据一个故事主题或剧情输入
- 先由大模型推理出分镜脚本
- 再生成每个镜头的参考图
- 最后调用短视频大模型生成多个 15–30 秒镜头
- 用 FFmpeg 将镜头按顺序拼接成完整短视频
- 支持批量输入多条故事，并并发生成成百上千集视频

这个项目适合做：

- AI 生成短视频脚本
- 批量创作故事视频
- 选题内容扩展与自动化产出
- 低代码 / 可扩展的短视频制作工作流

## 1. 功能概览

- 单条故事生成：支持一条剧情 -> 多个镜头 -> 最终视频
- 剧本推理：LLM 自动生成 scenes / 分镜 / 场景描述 / 图片 prompt
- 图像生成：为每个 scene 生成参考图
- 视频生成：支持 mock / Replicate 等 provider
- 批量生成：读取 stories 文件或 JSON 列表，批量产出多个视频
- 并发生成：使用线程池并发处理多个故事，适合成百上千集任务
- FFmpeg 拼接：自动将多个片段拼成一个完整视频

## 2. 技术架构

核心模块如下：

- `app/config.py`：读取环境变量和通用配置
- `app/models.py`：`SceneSpec` 和 `ShotSpec` 数据结构
- `app/planner.py`：把故事切成若干 shot
- `app/script_writer.py`：LLM 剧本推理，输出分镜列表
- `app/image_generator.py`：生成 scene 的参考图
- `app/story_pipeline.py`：串联脚本生成 + 图片生成 + shot 生成
- `app/generator.py`：短视频模型生成客户端
- `app/assembler.py`：FFmpeg 拼接
- `app/batch_pipeline.py`：批量视频生成与并发执行
- `app/cli.py`：命令行入口
- `run_pipeline.py`：启动入口

## 3. 项目目录

前端演示（可选）已添加在 frontend/，包含 Vite + React 示例项目。

```text
video_gen/
├── app/
│   ├── __init__.py
│   ├── assembler.py
│   ├── batch_pipeline.py
│   ├── cli.py
│   ├── config.py
│   ├── generator.py
│   ├── image_generator.py
│   ├── models.py
│   ├── planner.py
│   ├── script_writer.py
│   ├── story_pipeline.py
│   └── __init__.py
├── examples/
│   └── stories.txt
├── output/
├── .env.example
├── requirements.txt
├── run_pipeline.py
├── README.md
└── .env
```

## 4. 安装依赖

在项目根目录执行：

```bash
python -m pip install -r requirements.txt
```

要求环境中已安装 FFmpeg，因为最终视频拼接依赖它。

如果没有 FFmpeg，可参考安装：

- Windows：可使用 winget 安装 Gyan.FFmpeg
- Linux/macOS：通常可用 apt / brew 安装

## 5. 环境变量配置

复制示例文件：

```bash
copy .env.example .env
```

示例配置：

```bash
VIDEO_PROVIDER=replicate
VIDEO_API_BASE_URL=https://api.example.com
VIDEO_API_TOKEN=your_api_token
VIDEO_MODEL_NAME=your-video-model
VIDEO_OUTPUT_DIR=./output
VIDEO_FPS=24
VIDEO_ASPECT_RATIO=16:9
VIDEO_MIN_DURATION=15
VIDEO_MAX_DURATION=30
VIDEO_DEFAULT_SHOTS=4
VIDEO_TIMEOUT_SECONDS=180
FFMPEG_BIN=ffmpeg

LLM_API_BASE_URL=https://api.example.com/v1
LLM_API_TOKEN=your_llm_token
LLM_MODEL_NAME=gpt-4o-mini

IMAGE_PROVIDER=mock
IMAGE_API_BASE_URL=https://api.example.com/v1
IMAGE_API_TOKEN=your_image_token
IMAGE_MODEL_NAME=flux-dev
```

说明：

- `VIDEO_PROVIDER`：视频生成 provider，当前支持 `mock` / `replicate`
- `LLM_*`：脚本生成 / 分镜 reasoning 接口
- `IMAGE_*`：参考图生成接口
- `VIDEO_*`：视频生成配置

## 6. 快速开始

### 6.1 单条故事：mock 测试

```bash
python run_pipeline.py --story "一名创业者在夜晚高楼间发布新产品，镜头展示城市灯光、人物情绪和产品细节" --shots 4 --provider mock
```

运行逻辑：

1. `ScriptWriter` 生成分镜脚本
2. `ImageGenerationClient` 生成每个 scene 的参考图
3. 把 scene 转成 shot
4. 使用 mock / real 视频模型生成片段
5. FFmpeg 拼接最终短视频

输出会写入 `output/` 目录，最终文件为：

```text
output/final_story.mp4
```

### 6.2 单条故事：跳过脚本推理

如果你不想继续使用自动剧情推理，可直接保留老模式：

```bash
python run_pipeline.py --story "城市夜景中的产品发布会" --shots 4 --provider mock --no-script
```

### 6.3 批量生成：多条故事并发生成

支持从文本文件或 JSON 文件中读取一批故事：

```bash
python run_pipeline.py --stories-file ./examples/stories.txt --batch-name my_collection --provider mock --batch-limit 10 --workers 4
```

说明：

- `--stories-file`：支持文本文件或 JSON 文件
- `--batch-name`：输出目录名
- `--batch-limit`：限制处理故事数量
- `--workers`：并发线程数

输出示例：

```text
output/
└── my_collection/
    ├── story_0001_城市夜景中的新品发布会/
    │   ├── final_story.mp4
    │   ├── manifest.json
    │   └── images/
    ├── story_0002_一个山间小屋...
    └── manifest.json
```

## 7. 批量故事文件格式

## 8. 新增：FastAPI 后端与 React 聊天 UI（演示）

项目已新增一个轻量后端 API（FastAPI）和一个本地示例聊天 UI，用于与 LLM 交互。主要文件：

- [app/api.py](D:/code/video_gen/app/api.py) — FastAPI 服务，包含 /api/chat, /api/plan, /api/health 及一个简单的 UI 路由。
- [app/harness.py](D:/code/video_gen/app/harness.py) — 一个轻量 harness，封装 OpenAI 聊天调用并提供 plan_shots() 功能。
- [app/chat_ui.html](D:/code/video_gen/app/chat_ui.html) — 使用 React（CDN）实现的简易聊天页面，默认请求 /api/chat。

快速运行（示例）：

1. 安装依赖：

```bash
python -m pip install -r requirements.txt
```

2. 在 `.env` 或系统环境中设置 OpenAI Key：

```bash
set OPENAI_API_KEY=your_key_here
# 或者使用仓库已有的 LLM_API_TOKEN / LLM_MODEL_NAME 配置
```

3. 启动服务：

```bash
python -m uvicorn app.api:app --reload --port 8000
```

4. 在浏览器打开 http://localhost:8000/ 使用聊天 UI，或用 curl / Postman 访问 /api/chat 和 /api/plan。

说明：当前 UI 使用 CDN 上的 React，因此无需安装 node 即可本地快速预览（适合开发/演示）。如果需要完整的 React/Vite 前端工程，可后续添加。 

## 9. 变更依赖

在 requirements.txt 中新增：

- fastapi
- uvicorn
- openai


### 文本文件

`examples/stories.txt`：

```text
# 每行一条故事，# 开头的行会被忽略
城市夜景中的新品发布会
一个山间小屋里晨光破晓的治愈故事
未来城市中机器人和人类共创生活
```

### JSON 文件

```json
[
  "城市夜景中的新品发布会",
  "一个山间小屋里晨光破晓的治愈故事",
  "未来城市中机器人和人类共创生活"
]
```

## 8. 运行流程说明

整体流程如下：

1. `ScriptWriter` 读取主题，生成多个 scene
2. 每个 scene 包含：
   - scene title
   - scene description
   - image prompt
   - duration_seconds
   - camera style
3. `ImageGenerationClient` 生成 scene 参考图
4. `SceneStoryboardPipeline` 把 scene 转换成 `ShotSpec`
5. `VideoGenerationClient` 为每个 shot 生成视频片段
6. `VideoAssembler` 使用 FFmpeg 拼接所有片段
7. 输出最终视频，以及批量 manifest

## 9. 真实模型接入方式

当前项目采用统一 HTTP 适配方案：

- LLM：可以接 OpenAI 兼容接口 / 本地大模型服务
- 图像模型：可以接 OpenAI image API / SDXL / Flux / 自定义图片服务
- 视频模型：可以接 Replicate / Runway / Fal / ModelScope / 自定义 API

对应文件：

- `app/script_writer.py`
- `app/image_generator.py`
- `app/generator.py`

只要服务支持以下能力：

- 提交推理任务
- 查询任务状态
- 返回 URL / base64 / 文件二进制

即可无缝接入当前流水线。

## 10. 扩展建议

建议后续方向：

- 增加字幕与 TTS 配音
- 统一分辨率和画幅标准化处理
- 增加镜头转场和关键帧控制
- 写入任务日志和重试机制
- 引入 Redis / Celery 做真正的大规模队列任务
- 支持视频后期剪辑、音效、BGM 和封面图生成

## 11. 现在已支持的输出

- 单条故事视频：`output/final_story.mp4`
- 批量故事输出：`output/{batch_name}/story_xxxx_.../final_story.mp4`
- 批量索引文件：`output/{batch_name}/manifest.json`

## 12. 说明

当前代码默认不会强绑定某个特定模型，而是通过环境变量配置模型调用方式。这样可以很方便地接入不同的大模型厂商，而不需要改动核心业务逻辑。

如果你需要真正的生产环境部署版本，我也可以继续为你补充：

- 配置中心
- 日志系统
- 重试与失败回放
- 数据库任务表
- 分布式并发队列
- Web 可视化管理页
