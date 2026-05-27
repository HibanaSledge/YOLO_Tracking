# Tool Usage

## Read Before Edit

- 修改现有文件前必须读取当前内容。
- 当前文件被用户改过时，必须重新读取。
- 大文件优先读取相关大段，不做碎片化猜测。

## Search Strategy

- 知道文件名时用文件搜索。
- 知道关键词时用文本搜索。
- 不确定入口时用语义搜索或子 agent 探索。

## Edit Strategy

- 文本文件用 patch。
- 不用终端命令编辑文件。
- 不重排无关代码。

## Validation Strategy

- Python 相关命令前先配置 Python 环境。
- 能用静态错误检查就先检查。
- 运行耗时大的视频实验前，先说明目的和预期产物。

## Artifact Strategy

- 对运行产物优先读取 summary，再读取 frame_metrics/performance 的关键范围。
- 不把视频观感替代结构化指标。