# imgmatch - 图像模板匹配CLI工具设计

## 目标
开发一个命令行工具，输入全屏截图和图案图片，输出图案在截图中最佳匹配位置的坐标。

## 需求
- **输入**: 全屏截图路径 + 图案图片路径
- **输出**: 最佳匹配位置的坐标 (x, y)，以截图左上角为 (0,0) 原点
- **匹配方式**: 模糊匹配，支持不同缩放比例（多尺度模板匹配）
- **形式**: CLI 命令行工具

## 技术方案
- Python + OpenCV + NumPy
- 多尺度模板匹配：对模板图按 0.5x~2.0x 生成多个缩放变体
- 每个缩放级别执行 `cv2.matchTemplate(TM_CCOEFF_NORMED)`
- 取所有缩放级别中置信度最高的匹配位置
- 输出匹配区域中心的 (x, y) 坐标

## 项目结构
```
opencv/
├── imgmatch.py        # 主程序（CLI入口 + 匹配逻辑）
├── requirements.txt   # opencv-python, numpy
└── README.md
```

## 使用方式
```bash
python imgmatch.py --source screenshot.png --template button.png
# 输出: x=320, y=240
```

## 坐标系
- 截图左上角为 (0, 0)
- x 向右递增，y 向下递增
- 输出坐标为匹配区域中心点
