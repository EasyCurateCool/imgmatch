# imgmatch --live 截屏模式 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 imgmatch CLI 工具新增 `--live` 模式，自动截取当前屏幕全屏截图并匹配图案位置。

**Architecture:** 新增 `capture_screen()` 和 `get_display_scale()` 函数通过 ctypes 调用 Win32 API 截屏和获取缩放比例；提取 `_match_core()` 内部函数复用多尺度匹配逻辑；`main()` 根据 `--live` 标志选择调用路径。

**Tech Stack:** Python 3.11+, OpenCV, NumPy, ctypes (标准库)

---

### Task 1: 提取匹配核心逻辑 `_match_core()`

**Files:**
- Modify: `imgmatch.py:41-126`

- [ ] **Step 1: 提取 `_match_core` 内部函数**

将 `find_template` 中的多尺度匹配逻辑（参数校验之后、文件读取之后的部分）提取为 `_match_core(source, template, scale_range, scale_step, threshold)`，接收 numpy 数组而非文件路径。

```python
def _match_core(
    source: np.ndarray,
    template: np.ndarray,
    scale_range: Tuple[float, float] = (0.5, 2.0),
    scale_step: float = 0.05,
    threshold: float = 0.6,
) -> Tuple[int, int, float]:
    """核心匹配逻辑，接收 numpy 数组。"""
    if scale_range[0] >= scale_range[1]:
        raise ValueError(f"scale_range 最小值必须小于最大值，当前: {scale_range}")
    if scale_step <= 0:
        raise ValueError(f"scale_step 必须大于 0，当前: {scale_step}")
    if not 0 < threshold <= 1.0:
        raise ValueError(f"threshold 必须在 (0, 1] 范围内，当前: {threshold}")

    th, tw = template.shape[:2]
    sh, sw = source.shape[:2]

    if th > sh or tw > sw:
        raise ImageMatchError("模板图片比截图还大，无法匹配")

    if (sw, sh) not in STANDARD_RESOLUTIONS:
        allowed = ", ".join(f"{w}x{h}" for w, h in STANDARD_RESOLUTIONS)
        raise ImageMatchError(f"截图分辨率 {sw}x{sh} 非标准分辨率，允许: {allowed}")

    best_val = float("-inf")
    best_loc = None
    best_scale = 1.0

    num_steps = int(round((scale_range[1] - scale_range[0]) / scale_step)) + 1
    scales = np.linspace(scale_range[0], scale_range[1], num_steps)

    for scale in scales:
        scaled_h = int(th * scale)
        scaled_w = int(tw * scale)

        if scaled_h > sh or scaled_w > sw:
            continue
        if scaled_h < 3 or scaled_w < 3:
            continue

        interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
        scaled_template = cv2.resize(template, (scaled_w, scaled_h), interpolation=interp)

        result = cv2.matchTemplate(source, scaled_template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val > best_val:
            best_val = max_val
            best_loc = max_loc
            best_scale = scale

    if best_val < threshold or best_loc is None:
        raise ImageMatchError(f"图案在截图中不存在（最高置信度: {best_val:.4f}，阈值: {threshold}）")

    center_x = best_loc[0] + int(tw * best_scale / 2)
    center_y = best_loc[1] + int(th * best_scale / 2)

    return (center_x, center_y, best_val)
```

- [ ] **Step 2: 改写 `find_template` 调用 `_match_core`**

```python
def find_template(
    source_path: str,
    template_path: str,
    scale_range: Tuple[float, float] = (0.5, 2.0),
    scale_step: float = 0.05,
    threshold: float = 0.6,
) -> Tuple[int, int, float]:
    """在截图中查找模板图案的最佳匹配位置（文件路径模式）。"""
    source = _imread(source_path)
    template = _imread(template_path)

    if source is None:
        raise ImageMatchError(f"无法读取截图文件: {source_path}")
    if template is None:
        raise ImageMatchError(f"无法读取模板文件: {template_path}")

    return _match_core(source, template, scale_range, scale_step, threshold)
```

- [ ] **Step 3: 运行验证原有功能不变**

Run: `cd e:/AI2.0/EzGlean/CODEBUDDY/opencv && python imgmatch.py --source "testdata/全屏截图.png" --template "testdata/待识别图案.png"`
Expected: `x=787, y=263`

---

### Task 2: 实现 `capture_screen()` 和 `get_display_scale()`

**Files:**
- Modify: `imgmatch.py` (在 `_imread` 之后新增两个函数)

- [ ] **Step 1: 新增 `capture_screen()` 函数**

```python
def capture_screen() -> np.ndarray:
    """截取全屏，返回灰度 numpy 数组。

    使用 Win32 API BitBlt 截屏，调用 SetProcessDPIAware() 确保获取物理分辨率。

    Returns:
        灰度截图 numpy 数组 (H, W)

    Raises:
        ImageMatchError: 截屏失败时提示以管理员身份运行
    """
    import ctypes
    import ctypes.wintypes

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    # 声明 DPI 感知，确保获取物理像素分辨率
    user32.SetProcessDPIAware()

    # 获取屏幕尺寸
    width = user32.GetSystemMetrics(0)  # SM_CXSCREEN
    height = user32.GetSystemMetrics(1)  # SM_CYSCREEN

    if width == 0 or height == 0:
        raise ImageMatchError("无法获取屏幕尺寸")

    # 获取屏幕 DC
    src_dc = user32.GetDC(None)
    if not src_dc:
        raise ImageMatchError("截屏失败，请尝试以管理员身份运行")

    mem_dc = gdi32.CreateCompatibleDC(src_dc)
    bitmap = gdi32.CreateCompatibleBitmap(src_dc, width, height)
    gdi32.SelectObject(mem_dc, bitmap)

    # BitBlt 截屏
    success = gdi32.BitBlt(mem_dc, 0, 0, width, height, src_dc, 0, 0, 0x00CC0020)  # SRCCOPY
    if not success:
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(None, src_dc)
        raise ImageMatchError("截屏失败，请尝试以管理员身份运行")

    # 提取像素数据
    buf_size = height * width * 4  # BGRA
    buf = ctypes.create_string_buffer(buf_size)
    header = ctypes.wintypes.BITMAPINFOHEADER()
    header.biSize = ctypes.sizeof(header)
    header.biWidth = width
    header.biHeight = -height  # 自顶向下
    header.biPlanes = 1
    header.biBitCount = 32
    header.biCompression = 0  # BI_RGB

    gdi32.GetDIBits(mem_dc, bitmap, 0, height, buf, ctypes.byref(header), 0)

    # 转为 numpy 数组 BGR → 灰度
    img = np.frombuffer(buf.raw, dtype=np.uint8).reshape(height, width, 4)
    img_bgr = img[:, :, :3]  # 去掉 Alpha 通道
    img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # 释放资源
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(None, src_dc)

    return img_gray
```

- [ ] **Step 2: 新增 `get_display_scale()` 函数**

```python
def get_display_scale() -> int:
    """获取 Windows 显示缩放百分比。

    Returns:
        缩放百分比 (100, 125, 150, 200 等)
    """
    import ctypes

    user32 = ctypes.windll.user32
    hdc = user32.GetDC(None)
    gdi32 = ctypes.windll.gdi32
    dpi = gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX = 88
    user32.ReleaseDC(None, hdc)
    return round(dpi / 96 * 100)
```

- [ ] **Step 3: 新增 `find_template_live()` 函数**

```python
def find_template_live(
    template_path: str,
    scale_range: Tuple[float, float] = (0.5, 2.0),
    scale_step: float = 0.05,
    threshold: float = 0.6,
) -> Tuple[int, int, float, int, Tuple[int, int]]:
    """自动截屏并查找模板图案位置（live 模式）。

    Args:
        template_path: 图案图片文件路径
        scale_range: 缩放搜索范围 (min, max)
        scale_step: 缩放步长
        threshold: 最低匹配置信度阈值

    Returns:
        (x, y, confidence, scale_percent, (width, height))

    Raises:
        ImageMatchError: 截屏失败、文件读取失败、分辨率不符或图案不存在
    """
    source = capture_screen()
    template = _imread(template_path)

    if template is None:
        raise ImageMatchError(f"无法读取模板文件: {template_path}")

    scale_percent = get_display_scale()
    sh, sw = source.shape[:2]

    x, y, confidence = _match_core(source, template, scale_range, scale_step, threshold)

    return (x, y, confidence, scale_percent, (sw, sh))
```

- [ ] **Step 4: 验证截屏功能**

Run: `cd e:/AI2.0/EzGlean/CODEBUDDY/opencv && python -c "import imgmatch; img = imgmatch.capture_screen(); print(f'截图尺寸: {img.shape}'); scale = imgmatch.get_display_scale(); print(f'缩放: {scale}%')"`
Expected: 输出截图尺寸和缩放百分比，无报错

---

### Task 3: 修改 CLI 参数和 `main()` 函数

**Files:**
- Modify: `imgmatch.py:129-159`

- [ ] **Step 1: 修改 `main()` 函数**

```python
def main() -> None:
    parser = argparse.ArgumentParser(description="在截图中查找图案的坐标位置")
    parser.add_argument("--source", "-s", help="全屏截图文件路径")
    parser.add_argument("--template", "-t", required=True, help="图案图片文件路径")
    parser.add_argument("--live", action="store_true", help="自动截屏模式：截取当前屏幕后匹配")
    parser.add_argument("--threshold", type=float, default=0.6, help="最低匹配置信度阈值 (默认: 0.6)")
    parser.add_argument("--scale-min", type=float, default=0.5, help="最小缩放比例 (默认: 0.5)")
    parser.add_argument("--scale-max", type=float, default=2.0, help="最大缩放比例 (默认: 2.0)")
    parser.add_argument("--scale-step", type=float, default=0.05, help="缩放步长 (默认: 0.05)")
    args = parser.parse_args()

    # 互斥校验
    if args.live and args.source:
        print("错误: --live 和 --source 不能同时使用", file=sys.stderr)
        sys.exit(1)
    if not args.live and not args.source:
        print("错误: 必须指定 --live 或 --source", file=sys.stderr)
        sys.exit(1)

    try:
        if args.live:
            x, y, _, scale_percent, (w, h) = find_template_live(
                args.template,
                scale_range=(args.scale_min, args.scale_max),
                scale_step=args.scale_step,
                threshold=args.threshold,
            )
            print(f"x={x}, y={y}, scale={scale_percent}%, resolution={w}x{h}")
        else:
            x, y, _ = find_template(
                args.source,
                args.template,
                scale_range=(args.scale_min, args.scale_max),
                scale_step=args.scale_step,
                threshold=args.threshold,
            )
            print(f"x={x}, y={y}")
    except ImageMatchError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"参数错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证原有文件模式不变**

Run: `cd e:/AI2.0/EzGlean/CODEBUDDY/opencv && python imgmatch.py --source "testdata/全屏截图.png" --template "testdata/待识别图案.png"`
Expected: `x=787, y=263`

- [ ] **Step 3: 验证 live 模式**

Run: `cd e:/AI2.0/EzGlean/CODEBUDDY/opencv && python imgmatch.py --live --template "testdata/待识别图案.png"`
Expected: `x=..., y=..., scale=...%, resolution=...x...`

- [ ] **Step 4: 验证互斥校验**

Run: `cd e:/AI2.0/EzGlean/CODEBUDDY/opencv && python imgmatch.py --live --source "testdata/全屏截图.png" --template "testdata/待识别图案.png" 2>&1`
Expected: `错误: --live 和 --source 不能同时使用`

---

### Task 4: 更新 README.md 和打包验证

**Files:**
- Modify: `README.md`
- Rebuild: `dist/imgmatch.exe`

- [ ] **Step 1: 更新 README.md 增加 live 模式说明**

在 README 使用方式部分新增 `--live` 模式文档。

- [ ] **Step 2: 重新打包 exe**

Run: `cd e:/AI2.0/EzGlean/CODEBUDDY/opencv && pyinstaller --onefile --name imgmatch imgmatch.py`

- [ ] **Step 3: 用 exe 验证两种模式**

Run: `.\dist\imgmatch.exe --source "testdata/全屏截图.png" --template "testdata/待识别图案.png"`
Expected: `x=787, y=263`

Run: `.\dist\imgmatch.exe --live --template "testdata/待识别图案.png"`
Expected: `x=..., y=..., scale=...%, resolution=...x...`
