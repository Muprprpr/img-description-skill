# 图片聚类与描述技能 (img_hamming_skill)

> 基于dHash算法的大规模图片聚类分级与AI多模态描述组件

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Go](https://img.shields.io/badge/go-1.24+-00ADD8?logo=go)](https://golang.org/)

## 概述

本Skill是一个可复用的图片处理中间组件，专为大规模图片的智能聚类、分级和描述而设计。作为中间组件，可以轻松集成到其他大型AI技能或工作流中。

## 功能特点

### 核心能力

| 功能 | 说明 |
|------|------|
| **三层聚类分级** | 基于dHash汉明距离进行L1/L2/L3三层智能分组 |
| **自动拼图生成** | 为每个聚类组生成2x2拼图（1024x1024 JPEG） |
| **AI多模态描述** | 使用Claude模型对拼图进行智能内容分析 |
| **并发处理** | 支持高并发图片哈希计算和AI描述请求 |
| **自动清理** | AI描述完成后自动删除临时拼图文件 |

### 聚类层级说明

| 层级 | 名称 | 汉明距离 | 说明 |
|------|------|----------|------|
| **L1** | 完全重合 | ≤ 1 | 几乎完全相同的图片（如不同压缩率） |
| **L2** | 高度相似 | ≤ 9 | 内容高度相似的图片（如轻微编辑） |
| **L3** | 弱相关 | ≤ 24 | 内容相关的图片（如同一场景不同角度） |

## 目录结构

```
img_hamming_skill/
├── README.md              # 本文件
├── marketplace.json       # Marketplace配置
├── skill.json             # Skill元数据
├── requirements.txt       # Python依赖
├── main.py                # Python入口脚本
├── bin/                   # 可执行文件
│   └── hamming.exe        # 编译后的Go聚类程序
└── src/                   # Go源代码
    ├── main.go            # 聚类算法实现
    └── go.mod             # Go模块配置
```

## 安装配置

### 1. 环境要求

- Python 3.9+
- Anthropic API密钥

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置API密钥

```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

## 使用方式

### 命令行调用

```bash
# 基本用法（自动清理拼图）
python main.py -d /path/to/images

# 保留拼图文件
python main.py -d /path/to/images --keep-collages

# 自定义描述提示词
python main.py -d /path/to/images -p "分析这些图片的商业价值"

# 指定输出文件
python main.py -d /path/to/images --output result.json

# 使用其他Claude模型
python main.py -d /path/to/images -m claude-3-opus-20240229
```

### 参数说明

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--dir` | `-d` | 图片文件夹路径（必填） | - |
| `--out` | `-o` | 拼图输出文件夹 | `./collages` |
| `--prompt` | `-p` | AI描述提示词 | `请详细描述这些图片的内容` |
| `--model` | `-m` | Claude模型 | `claude-3-5-sonnet-20241022` |
| `--exe` | - | 可执行文件路径 | `./bin/hamming.exe` |
| `--api-key` | - | Anthropic API密钥 | 从环境变量读取 |
| `--max-workers` | - | 并发描述worker数 | `4` |
| `--output` | - | 输出JSON文件路径 | stdout |
| `--keep-collages` | - | 保留拼图文件 | `false` |

### Python代码集成

```python
from main import ImageHammingSkill

# 初始化Skill
skill = ImageHammingSkill(
    executable_path="./bin/hamming.exe",
    api_key="your_api_key"
)

# 处理图片
result = skill.process_images(
    image_dir="/path/to/images",
    output_dir="./collages",
    description_prompt="请分析图片内容和应用场景",
    model="claude-3-5-sonnet-20241022",
    max_workers=4,
    keep_collages=False  # 默认自动删除拼图
)

# 访问结果
print(f"处理了 {result.total_images} 张图片")
print(f"耗时 {result.processing_time_seconds:.2f} 秒")

for group in result.groups:
    print(f"\n--- 组 {group.group_id} ({group.total_images}张) ---")
    print(f"描述: {group.collage_description}")

# 获取JSON输出
json_output = skill.to_json(result)
```

## 输出格式

```json
{
  "total_images": 150,
  "groups": [
    {
      "group_id": 1,
      "l3_collage_path": "./collages/group_1_l3_collage.jpg",
      "collage_description": "这组图片主要展示户外风景，包括山脉、湖泊和森林...",
      "total_images": 45,
      "high_sim_subgroups": [
        {
          "sub_leader_path": "/path/to/leader.jpg",
          "total_images": 20,
          "exact_variants": [
            {
              "count": 15,
              "images": ["/path/to/img1.jpg", "/path/to/img2.jpg"]
            },
            {
              "count": 5,
              "images": ["/path/to/img3.jpg", "/path/to/img4.jpg"]
            }
          ]
        }
      ]
    }
  ],
  "processing_time_seconds": 12.5
}
```

## 作为中间组件集成

本Skill设计为可被其他Skills调用的中间组件：

```python
# 在其他Skill中调用
import subprocess
import json

def analyze_image_clusters(image_dir: str) -> dict:
    """调用img_hamming_skill进行图片聚类分析"""
    result = subprocess.run(
        ["python", "img_hamming_skill/main.py",
         "-d", image_dir,
         "--keep-collages"],  # 根据需要设置
        capture_output=True,
        text=True,
        timeout=600
    )

    if result.returncode == 0:
        return json.loads(result.stdout)
    else:
        raise Exception(f"处理失败: {result.stderr}")
```

## 性能指标

| 指标 | 数值 | 说明 |
|------|------|------|
| 处理速度 | ~1000张/分钟 | 取决于硬件配置 |
| 内存占用 | ~200MB | 1000张图片的典型值 |
| L1准确率 | >99% | 完全重合检测 |
| L2准确率 | >95% | 高度相似检测 |
| 拼图尺寸 | 1024x1024 | 每个拼图包含4张缩略图 |

## 技术架构

### 处理流程

```
┌─────────────────────────────────────────────────────────────┐
│                        输入图片目录                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Go程序: dHash计算（并发）+ 三层Union-Find聚类              │
│  • L1: 汉明距离 ≤ 1 (完全重合)                               │
│  • L2: 汉明距离 ≤ 9 (高度相似)                               │
│  • L3: 汉明距离 ≤ 24 (弱相关)                                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  生成2x2拼图 (1024x1024 JPEG)                               │
│  • 每个L3组生成一个拼图                                      │
│  • 取组内前4张图片作为代表                                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Claude多模态API（并发描述）                                 │
│  • 将拼图以base64编码发送                                    │
│  • 使用自定义提示词进行描述                                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  自动清理临时拼图文件                                        │
│  • 可通过 --keep-collages 参数保留                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                        输出JSON结果                          │
└─────────────────────────────────────────────────────────────┘
```

## 编译Go程序（可选）

如果需要重新编译Go程序：

```bash
cd src
go build -o ../bin/hamming.exe main.go
```

## 依赖项

### Python依赖

```txt
anthropic>=0.40.0
pillow>=11.0.0
pydantic>=2.0.0
```

### Go依赖

无外部依赖，仅使用标准库。

## 许可证

[MIT License](../../../LICENSE)

---

**作者**: ASUS | **版本**: 1.0.0
