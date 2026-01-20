---
id: img-hamming-skill
name: 图片聚类与描述技能
version: 1.0.0
author: Muprprpr
description: 基于dHash算法的大规模图片聚类分级与AI多模态描述组件
---

# 图片聚类与描述技能 (img-hamming-skill)

基于dHash算法的图片智能聚类与AI描述中间组件。

## 功能

- **三层聚类分级**：基于dHash汉明距离进行L1/L2/L3三层智能分组
- **自动拼图生成**：为每个聚类组生成2x2拼图（1024x1024 JPEG）
- **AI多模态描述**：使用Claude模型对拼图进行智能内容分析
- **自动清理**：AI描述完成后自动删除临时拼图文件

## 使用场景

当用户需要对大量图片进行分类、去重或内容分析时，此技能可以：

1. 快速识别相似或重复的图片
2. 将图片按相似度分组
3. 生成拼图供AI分析
4. 返回结构化的聚类结果和描述

## 触发关键词

图片聚类、图片分类、图片去重、图片分析、相似图片、图片分组、image clustering、duplicate detection

## 使用示例

```
请分析 /path/to/images 目录下的图片，找出相似的图片组
```

```
使用 img-hamming-skill 处理这个图片文件夹 /path/to/images
```

```
帮我把这些图片分类并描述每组的内容
```

## 输入参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| image_dir | string | 是 | - | 图片文件夹路径 |
| output_dir | string | 否 | ./collages | 拼图输出文件夹 |
| description_prompt | string | 否 | 请详细描述这些图片的内容 | AI描述提示词 |
| keep_collages | boolean | 否 | false | 是否保留拼图文件 |

## 输出格式

返回JSON格式的聚类结果，包含：

- `total_images`: 处理的图片总数
- `groups`: 聚类分组数组
  - `group_id`: 组编号
  - `collage_path`: 拼图路径
  - `collage_description`: AI生成的描述
  - `total_images`: 该组图片数量
  - `high_sim_subgroups`: 高相似度子分组
- `processing_time_seconds`: 处理耗时

## 依赖要求

- Python 3.9+
- Anthropic API密钥（多模态AI描述）
- 支持的图片格式：jpg, jpeg, png
