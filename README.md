# imgmatch

图像模板匹配 CLI 工具 —— 在截图中查找按钮/图标等图案的坐标位置，支持多尺度模糊匹配和自动截屏。

## 快速开始

```bash
# 文件模式：在已知截图中查找图案
imgmatch.exe --source screenshot.png --template button.png

# Live 模式：自动截取当前屏幕后查找图案
imgmatch.exe --live --template button.png
```

## 输出格式

| 模式 | 输出示例 | 说明 |
|------|----------|------|
| 文件模式 | `x=787, y=263` | 匹配区域中心坐标 |
| Live 模式 | `x=787, y=263, scale=125%, resolution=1920x1080` | 坐标 + 显示缩放 + 截屏分辨率 |

- **scale**：Windows 显示缩放百分比（100%/125%/150%），供桌面自动化软件做坐标转换
- **resolution**：截屏物理像素分辨率

## 参数说明

| 参数 | 缩写 | 说明 | 默认值 |
|------|------|------|--------|
| `--source` | `-s` | 全屏截图文件路径（与 `--live` 互斥） | - |
| `--template` | `-t` | 图案图片文件路径 | **必填** |
| `--live` | - | 自动截屏模式（与 `--source` 互斥） | - |
| `--threshold` | - | 最低匹配置信度阈值 | 文件模式 0.6 / Live 模式 0.75 |
| `--scale-min` | - | 最小缩放比例 | 0.5 |
| `--scale-max` | - | 最大缩放比例 | 2.0 |
| `--scale-step` | - | 缩放搜索步长 | 0.05 |
| `--verbose` | `-v` | 输出详细日志（排障用） | 关闭 |

## 使用示例

```bash
# 基本用法
imgmatch.exe --source screen.png --template icon.png

# Live 模式自动截屏
imgmatch.exe --live --template icon.png

# 降低阈值以匹配模糊图案
imgmatch.exe --live --template icon.png --threshold 0.5

# 缩小搜索范围加速匹配
imgmatch.exe --live --template icon.png --scale-min 0.8 --scale-max 1.2 --scale-step 0.02

# 排障：查看详细日志
imgmatch.exe --live --template icon.png --verbose
```

## 坐标系

- 截图左上角为原点 `(0, 0)`
- x 向右递增，y 向下递增
- 输出坐标为**匹配区域中心点**

## Live 模式说明

- 自动截取当前屏幕（使用 Win32 API，零额外依赖）
- 截图自动保存为 `testdata/live_screenshot_{时间戳}.png`（彩色）
- 需确保目标窗口在屏幕最前面，截屏会包含所有可见内容
- 截屏失败时提示以管理员身份运行
- 默认阈值 0.75（高于文件模式的 0.6），防止真实屏幕复杂纹理导致误匹配

## 常见问题

### 匹配失败：图案在截图中不存在

1. 加 `--verbose` 查看最高置信度和阈值
2. 如果置信度接近阈值，用 `--threshold` 适当降低
3. 确认图案图片确实是当前屏幕上可见的
4. Live 模式下检查 `testdata/` 下保存的截图，确认截到了正确内容

### 截屏失败

以管理员身份运行 `imgmatch.exe`。截屏可能因权限不足而失败（如目标窗口以管理员身份运行）。

### 截图分辨率非标准

工具仅支持常见分辨率（1920x1080、2560x1440 等），不支持的分辨率会报错并列出允许值。

## 依赖

- Python 3.11+（开发时需要）
- opencv-python
- numpy

打包后的 exe 无需 Python 环境。
