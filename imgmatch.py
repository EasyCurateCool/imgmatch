"""imgmatch - 图像模板匹配CLI工具

在全屏截图中查找图案图片的坐标位置，支持多尺度模糊匹配。
坐标系：截图左上角为 (0, 0)，输出匹配区域中心点坐标。
"""

import argparse
import datetime
import logging
import os
import sys
from typing import Tuple

import cv2
import numpy as np

# ── 日志配置 ──────────────────────────────────────────────
logger = logging.getLogger("imgmatch")


def _setup_logging(verbose: bool = False) -> None:
    """配置日志：stderr 按 verbose 控制级别，文件始终记录 INFO 级别。

    日志文件存放于 exe/脚本同目录的 logs/ 下，按日期命名：
      logs/imgmatch_2026-04-22.log
    """
    # 文件日志：始终 INFO 级别，追加写入
    log_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"imgmatch_{datetime.date.today().isoformat()}.log")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                                datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(file_handler)

    # stderr 日志：verbose 控制 DEBUG / WARNING
    stderr_level = logging.DEBUG if verbose else logging.WARNING
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(stderr_level)
    stderr_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(stderr_handler)

    # logger 总级别取两者最低
    logger.setLevel(min(stderr_level, logging.INFO))

    logger.info("========== imgmatch 启动 ==========")


class ImageMatchError(Exception):
    """图像匹配相关错误"""


# 常见标准屏幕分辨率 (宽x高)
STANDARD_RESOLUTIONS = [
    (1920, 1080),  # Full HD
    (2560, 1440),  # QHD
    (3840, 2160),  # 4K UHD
    (1366, 768),   # 常见笔记本
    (1536, 864),   # 常见笔记本缩放
    (1440, 900),   # MacBook
    (1280, 720),   # HD
    (1280, 800),   # 常见笔记本
    (1024, 768),   # 经典分辨率
]


def _imread(path: str, flags: int = cv2.IMREAD_GRAYSCALE) -> np.ndarray:
    """读取图片，支持中文路径。"""
    # cv2.imread 不支持中文路径，使用 numpy + cv2.imdecode 替代
    buf = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(buf, flags)
    if img is None:
        logger.debug("图片读取失败: %s (文件可能不存在或格式不支持)", path)
    else:
        logger.debug("图片读取成功: %s, 尺寸: %s", path, img.shape)
    return img


def capture_screen() -> Tuple[np.ndarray, np.ndarray]:
    """截取全屏，返回灰度和彩色 numpy 数组。

    使用 Win32 API BitBlt 截屏，调用 SetProcessDPIAware() 确保获取物理分辨率。

    Returns:
        (灰度截图 numpy 数组 (H, W), 彩色截图 numpy 数组 (H, W, 3) BGR)

    Raises:
        ImageMatchError: 截屏失败时提示以管理员身份运行
    """
    import ctypes
    import ctypes.wintypes

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    # 声明 DPI 感知，确保获取物理像素分辨率
    user32.SetProcessDPIAware()
    logger.debug("已调用 SetProcessDPIAware()")

    # 获取屏幕尺寸
    width = user32.GetSystemMetrics(0)  # SM_CXSCREEN
    height = user32.GetSystemMetrics(1)  # SM_CYSCREEN

    if width == 0 or height == 0:
        raise ImageMatchError("无法获取屏幕尺寸")

    logger.debug("屏幕物理分辨率: %dx%d", width, height)

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

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", ctypes.wintypes.DWORD),
            ("biWidth", ctypes.wintypes.LONG),
            ("biHeight", ctypes.wintypes.LONG),
            ("biPlanes", ctypes.wintypes.WORD),
            ("biBitCount", ctypes.wintypes.WORD),
            ("biCompression", ctypes.wintypes.DWORD),
            ("biSizeImage", ctypes.wintypes.DWORD),
            ("biXPelsPerMeter", ctypes.wintypes.LONG),
            ("biYPelsPerMeter", ctypes.wintypes.LONG),
            ("biClrUsed", ctypes.wintypes.DWORD),
            ("biClrImportant", ctypes.wintypes.DWORD),
        ]

    header = BITMAPINFOHEADER()
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

    logger.debug("截屏成功: %dx%d 灰度+彩色", width, height)
    return img_gray, img_bgr


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
    scale = round(dpi / 96 * 100)
    logger.debug("系统DPI: %d, 显示缩放: %d%%", dpi, scale)
    return scale


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
    source_gray, source_bgr = capture_screen()
    template = _imread(template_path)

    if template is None:
        raise ImageMatchError(f"无法读取模板文件: {template_path}")

    scale_percent = get_display_scale()
    sh, sw = source_gray.shape[:2]

    # 保存截图到当前工作目录的 testdata 下
    import datetime
    import os
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    save_dir = os.path.join(os.getcwd(), "testdata")
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, f"live_screenshot_{timestamp}.png")
    cv2.imwrite(save_path, source_bgr)
    logger.debug("截图已保存: %s", save_path)

    x, y, confidence = _match_core(source_gray, template, scale_range, scale_step, threshold)

    return (x, y, confidence, scale_percent, (sw, sh))


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

    logger.debug("源图: %dx%d, 模板: %dx%d", sw, sh, tw, th)

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
    logger.debug("多尺度搜索: %.2f~%.2f, 步长%.2f, 共%d个尺度", scale_range[0], scale_range[1], scale_step, num_steps)

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

    logger.debug("匹配完成: 最高置信度=%.4f, 最佳尺度=%.2f, 阈值=%.2f", best_val, best_scale, threshold)

    if best_val < threshold or best_loc is None:
        raise ImageMatchError(f"图案在截图中不存在（最高置信度: {best_val:.4f}，阈值: {threshold}）")

    center_x = best_loc[0] + int(tw * best_scale / 2)
    center_y = best_loc[1] + int(th * best_scale / 2)

    return (center_x, center_y, best_val)


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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="imgmatch - 图像模板匹配CLI工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  文件模式: imgmatch.exe --source screenshot.png --template button.png
  Live模式: imgmatch.exe --live --template button.png
  详细日志: imgmatch.exe --live --template button.png --verbose
  自定义阈值: imgmatch.exe --live --template button.png --threshold 0.8""",
    )
    parser.add_argument("--source", "-s", help="全屏截图文件路径")
    parser.add_argument("--template", "-t", required=True, help="图案图片文件路径")
    parser.add_argument("--live", action="store_true", help="自动截屏模式：截取当前屏幕后匹配")
    parser.add_argument("--threshold", type=float, default=None, help="最低匹配置信度阈值 (文件模式默认: 0.6, live模式默认: 0.75)")
    parser.add_argument("--scale-min", type=float, default=0.5, help="最小缩放比例 (默认: 0.5)")
    parser.add_argument("--scale-max", type=float, default=2.0, help="最大缩放比例 (默认: 2.0)")
    parser.add_argument("--scale-step", type=float, default=0.05, help="缩放步长 (默认: 0.05)")
    parser.add_argument("--verbose", "-v", action="store_true", help="输出详细日志（用于排障）")
    args = parser.parse_args()

    # 初始化日志
    _setup_logging(args.verbose)

    # 互斥校验
    if args.live and args.source:
        print("错误: --live 和 --source 不能同时使用", file=sys.stderr)
        sys.exit(1)
    if not args.live and not args.source:
        print("错误: 必须指定 --live 或 --source", file=sys.stderr)
        sys.exit(1)

    # live 模式默认阈值 0.75（防止误匹配），文件模式默认 0.6
    if args.threshold is None:
        args.threshold = 0.75 if args.live else 0.6

    logger.info("运行参数: mode=%s, template=%s, threshold=%.2f, scale_range=%.2f~%.2f, step=%.2f",
                "live" if args.live else "file", args.template, args.threshold,
                args.scale_min, args.scale_max, args.scale_step)

    try:
        if args.live:
            x, y, confidence, scale_percent, (w, h) = find_template_live(
                args.template,
                scale_range=(args.scale_min, args.scale_max),
                scale_step=args.scale_step,
                threshold=args.threshold,
            )
            print(f"x={x}, y={y}, scale={scale_percent}%, resolution={w}x{h}")
            logger.info("匹配成功: x=%d, y=%d, confidence=%.4f, scale=%d%%, resolution=%dx%d",
                        x, y, confidence, scale_percent, w, h)
        else:
            x, y, confidence = find_template(
                args.source,
                args.template,
                scale_range=(args.scale_min, args.scale_max),
                scale_step=args.scale_step,
                threshold=args.threshold,
            )
            print(f"x={x}, y={y}")
            logger.info("匹配成功: x=%d, y=%d, confidence=%.4f", x, y, confidence)
    except ImageMatchError as e:
        logger.info("匹配失败: %s", e)
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        logger.info("参数错误: %s", e)
        print(f"参数错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.error("未预期的异常", exc_info=True)
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
