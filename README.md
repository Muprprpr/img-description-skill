# 图片描述技能集 (Image Description Skills)

> 基于dHash聚类与Claude多模态AI的图片处理中间组件

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Go](https://img.shields.io/badge/go-1.24+-00ADD8?logo=go)](https://golang.org/)

## 简介

本项目是一个可复用的图片处理技能集，专门用于大规模图片的智能聚类、分级和描述。作为中间组件，可以轻松集成到其他大型AI技能或工作流中。

### 核心功能

- **三层聚类分级**：基于dHash汉明距离进行智能分组
- **自动拼图生成**：为每个聚类组生成可视化拼图
- **AI多模态描述**：使用Claude模型进行智能内容分析
- **并发处理**：支持高并发图片哈希计算和AI描述
- **自动清理**：描述完成后自动清理临时文件

## 项目结构

```
img-description-skill/
├── LICENSE                 # MIT许可证
├── .gitignore             # Git忽略配置
├── README.md              # 项目说明（本文件）
├── .github/               # GitHub配置
│   └── marketplace.json   # Marketplace插件配置
├── .claude/               # Claude Code技能目录
│   └── skills/
│       └── img-hamming-skill/
│           ├── skill.json         # Skill元数据
│           ├── main.py            # Python入口脚本
│           ├── requirements.txt   # Python依赖
│           ├── bin/               # 可执行文件
│           │   └── hamming.exe    # 编译后的Go程序
│           └── src/               # Go源代码
│               ├── main.go        # Go源码
│               └── go.mod         # Go模块配置
└── skills/                # 旧版目录（保留用于直接Python调用）
    └── img_hamming_skill/
        └── README.md          # Skill详细说明
```

## 快速开始

### 环境要求

- Python 3.9+
- Go 1.24+（如需重新编译）
- Anthropic API密钥

### 安装

```bash
# 克隆仓库
git clone https://github.com/Muprprpr/img-description-skill.git
cd img-description-skill

# 安装Python依赖
pip install -r .claude/skills/img-hamming-skill/requirements.txt

# 设置API密钥
export ANTHROPIC_API_KEY=your_api_key_here
```

### Claude Code Plugin 安装

在 Claude Code 中使用 `/plugin` 命令安装此技能：

```bash
# 步骤1：添加到 Marketplace
/plugin marketplace add Muprprpr/img-description-skill

# 步骤2：安装技能
/plugin install img-hamming-skill@img-description-skill
```

安装后，即可在 Claude Code 中直接调用此技能：

```
请使用 img-hamming-skill 处理 /path/to/images 目录下的图片
```

### 手动安装

如果自动安装失败，可以手动复制文件：

```bash
# 复制技能目录到 .claude
cp -r .claude ~/.claude/

# 或在 Windows 上
xcopy .claude %USERPROFILE%\.claude\ /E /I
```

### 使用

```bash
# 处理图片目录
python .claude/skills/img-hamming-skill/main.py -d /path/to/images

# 保留拼图文件
python .claude/skills/img-hamming-skill/main.py -d /path/to/images --keep-collages

# 自定义描述提示
python .claude/skills/img-hamming-skill/main.py -d /path/to/images -p "分析这些图片的商业价值"
```

### Python集成

```python
from .claude.skills.img_hamming_skill.main import ImageHammingSkill

skill = ImageHammingSkill()
result = skill.process_images(
    image_dir="/path/to/images",
    description_prompt="请详细描述图片内容"
)

# 访问结果
for group in result.groups:
    print(f"组 {group.group_id}: {group.collage_description}")
```

## 技术原理

### dHash聚类算法

| 层级 | 名称 | 汉明距离阈值 | 说明 |
|------|------|-------------|------|
| L1 | 完全重合 | ≤ 1 | 几乎完全相同的图片 |
| L2 | 高度相似 | ≤ 9 | 内容高度相似的图片 |
| L3 | 弱相关 | ≤ 24 | 内容相关的图片 |

### 处理流程

```
输入图片目录
    ↓
Go程序计算dHash（并发）
    ↓
三层分级聚类
    ↓
生成2x2拼图 (1024x1024)
    ↓
Claude多模态描述（并发）
    ↓
自动清理临时文件
    ↓
输出JSON结果
```

## 输出格式

```json
{
  "total_images": 150,
  "groups": [
    {
      "group_id": 1,
      "l3_collage_path": "./collages/group_1_l3_collage.jpg",
      "collage_description": "这组图片主要展示户外风景...",
      "total_images": 45,
      "high_sim_subgroups": [
        {
          "sub_leader_path": "/path/to/leader.jpg",
          "total_images": 20,
          "exact_variants": [
            {
              "count": 15,
              "images": ["/path/to/img1.jpg", ...]
            }
          ]
        }
      ]
    }
  ],
  "processing_time_seconds": 12.5
}
```

## 性能指标

| 指标 | 数值 |
|------|------|
| 处理速度 | ~1000张/分钟 |
| 内存占用 | ~200MB (1000张图片) |
| L1准确率 | >99% |
| L2准确率 | >95% |

## 贡献

欢迎提交Issue和Pull Request！

## 许可证

[MIT License](LICENSE)

---

Made with ❤️ by 壹五
