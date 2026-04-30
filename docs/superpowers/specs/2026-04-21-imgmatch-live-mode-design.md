# imgmatch --live 截屏模式设计

## 目标
为 imgmatch CLI 工具新增 `--live` 模式，自动截取当前屏幕全屏截图，用户只需传入图案图片路径即可完成匹配。

## 需求
- **新增模式**: `--live` 标志启用自动截屏模式
- **截屏方式**: 调用 Win32 API (BitBlt) 截取全屏，零新增依赖
- **DPI 感知**: 截屏前调用 `SetProcessDPIAware()` 确保获取物理像素分辨率
- **权限兜底**: 截屏失败时提示用户以管理员身份运行
- **输出增强**: live 模式下额外输出 Windows 显示缩放百分比和截屏分辨率
- **模式互斥**: `--live` 与 `--source` 不可同时使用

## 使用方式

```bash
# 原有文件模式（不变）
imgmatch.exe --source screenshot.png --template button.png
# 输出: x=787, y=263

# 新增 live 截屏模式
imgmatch.exe --live --template button.png
# 输出: x=787, y=263, scale=150%, resolution=1920x1080
```

## CLI 参数变化

| 参数 | 变化 | 说明 |
|------|------|------|
| `--live` | 新增 | 启用自动截屏模式 |
| `--source` | 调整 | `--live` 模式下不再必填，与 `--live` 互斥 |
| `--template` | 不变 | 图案图片路径，始终必填 |

互斥规则：
- `--live` + `--source` 同时使用 → 报错退出
- `--live` 未指定 → `--source` 必填（原有行为）

## 技术方案

### 截屏实现 (Win32 API via ctypes)

```python
def capture_screen() -> np.ndarray:
    """截取全屏，返回 BGR 格式 numpy 数组。"""
    # 1. SetProcessDPIAware() — 声明 DPI 感知
    # 2. GetDC(NULL) → CreateCompatibleDC → CreateCompatibleBitmap
    # 3. BitBlt 拷贝屏幕到 bitmap
    # 4. GetBitmapBits 提取像素数据
    # 5. 转为 numpy 数组 (H, W, 3) BGR 格式
    # 6. 释放资源
    # 7. 失败时 raise ImageMatchError("截屏失败，请尝试以管理员身份运行")
```

### 获取缩放百分比

```python
def get_display_scale() -> int:
    """获取 Windows 显示缩放百分比 (100/125/150/200 等)。"""
    # GetDeviceCaps(LOGPIXELSX) 获取 DPI
    # scale = round(dpi / 96 * 100)
```

### 代码架构调整

```
现有:
  find_template(source_path, template_path, ...) → (x, y, confidence)
  main() → 解析参数，调用 find_template

新增:
  capture_screen() → np.ndarray (BGR)
  get_display_scale() → int (百分比)
  find_template_from_array(source_array, template_path, ...) → (x, y, confidence)
    # 复用多尺度匹配逻辑，但 source 直接用 numpy 数组而非文件路径
  main() → 根据 --live 选择调用路径
```

`find_template_from_array` 与 `find_template` 共享核心匹配逻辑，提取为内部函数 `_match_core(source, template, ...)`。

### 分辨率校验

live 模式下截屏分辨率为物理分辨率，仍需通过 `STANDARD_RESOLUTIONS` 校验。
`SetProcessDPIAware()` 确保截屏获取的是物理分辨率（如 1920x1080）而非逻辑分辨率（如 1280x720）。

### 输出格式

| 模式 | 输出格式 | 示例 |
|------|----------|------|
| 文件模式 | `x={x}, y={y}` | `x=787, y=263` |
| live 模式 | `x={x}, y={y}, scale={scale}%, resolution={w}x{h}` | `x=787, y=263, scale=150%, resolution=1920x1080` |

## 依赖变化

零新增依赖。Win32 API 通过 Python 标准库 `ctypes` 调用。

## 限制

- 仅支持 Windows（Win32 API）
- 无法截取以管理员身份运行的窗口内容（需管理员权限运行 imgmatch）
- 无法截取 DRM 保护内容和独占全屏游戏
