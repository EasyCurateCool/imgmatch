# CODEBUDDY.md — OpenCV 图像匹配项目 Agent 行为规范

## 1. 项目概述

本项目是一个基于 OpenCV 的图像模板匹配 CLI 工具（`imgmatch`），用于在全屏截图中查找图案的坐标位置，支持多尺度模糊匹配和自动截屏模式。

- **语言**: Python 3.11+
- **核心依赖**: opencv-python, numpy
- **入口**: `imgmatch.py`
- **坐标系**: 截图左上角 (0,0)，输出匹配区域中心点
- **两种模式**: 文件模式（传入截图路径）和 Live 模式（自动截屏）

## 2. 强制引用的 Skills

本项目的开发必须遵循以下 Skills 的行为规范，不可绕过、不可忽略：

### 2.1 @karpathy-guidelines — 编码行为准则
- **Think Before Coding**: 动手前必须明确假设，有歧义时必须提出，不可默默选择
- **Simplicity First**: 只写解决问题所需的最少代码，不添加未要求的功能、抽象、配置
- **Surgical Changes**: 只改必须改的，不顺手"改进"周围代码，不改已有风格
- **Goal-Driven Execution**: 每个任务必须有可验证的成功标准，循环直到验证通过

### 2.2 @superpowers — 技能调度规范
- 遇到任何任务时，先检查是否有适用的 Skill，哪怕只有 1% 的可能性也必须调用
- 流程型 Skill（brainstorming, debugging）优先于实现型 Skill
- 在做出任何响应（包括澄清问题）之前，先调用相关 Skill

### 2.3 @pua — 穷尽式问题解决
- **三条红线**: (1) 闭环意识——声称完成前必须有验证证据；(2) 事实驱动——未验证的归因等于甩锅；(3) 穷尽一切——说"无法解决"前必须走完通用方法论 5 步
- **Owner 意识**: 发现问题主动处理，谁痛苦谁改变，端到端交付
- **压力升级**: 失败 2 次 L1 换方案 → 3 次 L2 搜索+读源码 → 4 次 L3 检查清单 → 5 次+ L4 拼命模式

## 3. 开发规则

### 3.1 代码风格
- 单文件项目，保持简洁
- 函数必须有清晰的 docstring
- 类型注解必须完整
- 错误信息输出到 stderr，正常结果输出到 stdout

### 3.2 验证规则
- 修改 `imgmatch.py` 后必须用测试图片运行验证，确保匹配结果正确
- 不允许只做存在性检查（"代码看起来没问题"），必须实际运行验证
- 验证时使用包含随机纹理的测试图片，避免纯色背景导致的误匹配
- Live 模式验证时需注意：截取的是当前屏幕，不是 testdata 的截图

### 3.3 匹配算法
- 使用 `cv2.matchTemplate` + `TM_CCOEFF_NORMED`
- 默认多尺度范围 0.5x~2.0x，步长 0.05
- 文件模式默认置信度阈值 0.6，Live 模式默认阈值 0.75（防止误匹配）
- 输出匹配区域中心坐标，不是左上角

### 3.4 Live 模式规则
- 截屏使用 Win32 API (BitBlt) + ctypes，零新增依赖
- 必须调用 `SetProcessDPIAware()` 确保获取物理像素分辨率
- Live 模式输出包含 `scale=...%, resolution=...x...`
- `--live` 与 `--source` 互斥
- 截屏失败时提示用户以管理员身份运行
- 截屏自动保存彩色 PNG 到 `testdata/live_screenshot_{timestamp}.png`

## 4. 项目结构

```
opencv/
├── imgmatch.py              # 主程序（CLI入口 + 匹配逻辑 + 截屏）
├── requirements.txt          # opencv-python, numpy
├── README.md                 # 使用说明
├── Rules.md                  # 开发规则
├── CODEBUDDY.md              # Agent 行为规范（本文件）
├── testdata/                 # 测试图片
│   ├── 全屏截图.png
│   └── 待识别图案.png
└── docs/superpowers/
    ├── specs/                # 设计文档
    │   ├── 2026-04-21-imgmatch-design.md
    │   └── 2026-04-21-imgmatch-live-mode-design.md
    └── plans/                # 实现计划
        ├── 2026-04-21-imgmatch.md
        └── 2026-04-21-imgmatch-live-mode.md
```

## 5. 禁止事项

- 禁止未经运行验证就声称修改完成
- 禁止添加未要求的 GUI/Web 功能
- 禁止引入不必要的依赖（如 Pillow、matplotlib 等）
- 禁止在输出坐标时使用非 (x, y) 格式
- 禁止 Live 模式截屏时写临时文件到磁盘（正式截图保存到 testdata/ 不算临时文件）
