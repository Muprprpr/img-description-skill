"""
图片聚类与描述中间组件 (Image Hamming Skill)

基于dHash进行图片分级聚类，生成拼图并提供AI多模态描述。
作为大型skills中的中间组件使用。
"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Any
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None
    print("警告: anthropic 包未安装，AI描述功能将不可用", file=sys.stderr)


@dataclass
class ExactGroup:
    """L1: 最底层的精确组"""
    count: int
    images: List[str]


@dataclass
class HighSimGroup:
    """L2: 中层的高度相似组"""
    sub_leader_path: str
    total_images: int
    exact_variants: List[ExactGroup]


@dataclass
class WeakRelGroup:
    """L3: 顶层的弱相关组"""
    group_id: int
    l3_collage_path: str
    total_images: int
    high_sim_subgroups: List[HighSimGroup]

    # 添加AI描述字段
    collage_description: Optional[str] = None

    # 拼图文件是否已被删除
    _collage_deleted: bool = False


@dataclass
class SkillResult:
    """Skill输出结果"""
    total_images: int
    groups: List[WeakRelGroup]
    processing_time_seconds: float


class ImageHammingSkill:
    """图片聚类与描述Skill"""

    def __init__(self, executable_path: str = None, api_key: str = None):
        """
        初始化Skill

        Args:
            executable_path: Go编译的可执行文件路径
            api_key: Anthropic API密钥
        """
        self.executable_path = executable_path or self._find_executable()
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

        if Anthropic and self.api_key:
            self.client = Anthropic(api_key=self.api_key)
        else:
            self.client = None

    def _find_executable(self) -> str:
        """查找可执行文件路径"""
        skill_dir = Path(__file__).parent
        bin_dir = skill_dir / "bin"
        src_dir = skill_dir / "src"

        # 按优先级查找可执行文件
        possible_paths = [
            bin_dir / "hamming.exe",
            bin_dir / "main.exe",
            bin_dir / "hashcheck.exe",
        ]

        for path in possible_paths:
            if path.exists():
                return str(path)

        # 尝试直接使用go run（开发模式）
        go_main = src_dir / "main.go"
        if go_main.exists():
            return f"go run {go_main}"

        raise FileNotFoundError(
            f"找不到可执行文件。请确保 {bin_dir} 目录下有 hamming.exe\n"
            f"编译方法: cd {src_dir} && go build -o ../bin/hamming.exe main.go"
        )

    def process_images(
        self,
        image_dir: str,
        output_dir: str = "./collages",
        description_prompt: str = "请详细描述这些图片的内容，包括主要场景、物体和活动。",
        model: str = "claude-3-5-sonnet-20241022",
        max_workers: int = 4,
        keep_collages: bool = False
    ) -> SkillResult:
        """
        处理图片：聚类、生成拼图、AI描述

        Args:
            image_dir: 图片文件夹路径
            output_dir: 拼图输出文件夹
            description_prompt: AI描述提示词
            model: 使用的Claude模型
            max_workers: 并发描述的最大worker数
            keep_collages: 是否保留拼图文件（默认False，描述完成后自动删除）

        Returns:
            SkillResult: 包含聚类结果和描述的结果对象
        """
        import time
        start_time = time.time()

        # 1. 调用Go脚本进行聚类和拼图生成
        raw_result = self._run_clustering(image_dir, output_dir)

        if not raw_result:
            return SkillResult(
                total_images=0,
                groups=[],
                processing_time_seconds=time.time() - start_time
            )

        # 2. 解析结果并创建数据对象
        groups = self._parse_result(raw_result)
        total_images = sum(g.total_images for g in groups)

        # 3. 对每个拼图进行AI描述
        if self.client and groups:
            self._describe_collages(
                groups,
                description_prompt,
                model,
                max_workers
            )

        # 4. 清理拼图文件（如果 keep_collages=False）
        try:
            if not keep_collages:
                self._cleanup_collages(groups)
        except Exception as e:
            print(f"清理拼图文件时出错: {e}", file=sys.stderr)

        return SkillResult(
            total_images=total_images,
            groups=groups,
            processing_time_seconds=time.time() - start_time
        )

    def _run_clustering(self, image_dir: str, output_dir: str) -> List[dict]:
        """运行Go聚类脚本"""
        cmd = self.executable_path.split()

        # 检查是否是 go run 命令
        if "go run" in self.executable_path:
            cmd.extend(["-dir", image_dir, "-out", output_dir])
        else:
            cmd.extend(["-dir", image_dir, "-out", output_dir])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5分钟超时
                check=True
            )

            # 从stdout中提取JSON部分
            output_lines = result.stdout.strip().split('\n')
            json_start = -1
            for i, line in enumerate(output_lines):
                if line.strip().startswith('['):
                    json_start = i
                    break

            if json_start >= 0:
                json_str = '\n'.join(output_lines[json_start:])
                return json.loads(json_str)

            return []

        except subprocess.CalledProcessError as e:
            print(f"聚类脚本执行失败: {e.stderr}", file=sys.stderr)
            return []
        except subprocess.TimeoutExpired:
            print("聚类脚本执行超时", file=sys.stderr)
            return []
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}", file=sys.stderr)
            return []

    def _parse_result(self, raw_result: List[dict]) -> List[WeakRelGroup]:
        """解析Go脚本的输出结果"""
        groups = []

        for item in raw_result:
            # 解析L2子组
            subgroups = []
            for sub_item in item.get("high_sim_subgroups", []):
                # 解析L1变体组
                variants = []
                for variant in sub_item.get("exact_variants", []):
                    variants.append(ExactGroup(
                        count=variant["count"],
                        images=variant["images"]
                    ))

                subgroups.append(HighSimGroup(
                    sub_leader_path=sub_item["sub_leader_path"],
                    total_images=sub_item["total_images"],
                    exact_variants=variants
                ))

            groups.append(WeakRelGroup(
                group_id=item["group_id"],
                l3_collage_path=item["l3_collage_path"],
                total_images=item["total_images"],
                high_sim_subgroups=subgroups
            ))

        return groups

    def _describe_collages(
        self,
        groups: List[WeakRelGroup],
        prompt: str,
        model: str,
        max_workers: int
    ) -> None:
        """并发地对每个拼图进行AI描述"""

        def describe_group(group: WeakRelGroup) -> tuple[int, str]:
            try:
                collage_path = group.l3_collage_path
                if not os.path.exists(collage_path):
                    return group.group_id, "拼图文件不存在"

                # 读取并编码图片
                with open(collage_path, "rb") as f:
                    image_data = base64.b64encode(f.read()).decode("utf-8")

                # 构建详细提示
                full_prompt = f"""{prompt}

这是第{group.group_id}组拼图，包含{group.total_images}张相似的图片。
请从以下几个方面进行描述：
1. 整体场景和主题
2. 主要识别出的物体或人物
3. 图片间的相似性和差异（如果可见）
4. 可能的应用场景或用途

请用中文回答，保持简洁准确。"""

                # 调用Claude API
                message = self.client.messages.create(
                    model=model,
                    max_tokens=1024,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/jpeg",
                                        "data": image_data
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": full_prompt
                                }
                            ]
                        }
                    ]
                )

                description = message.content[0].text
                return group.group_id, description

            except Exception as e:
                print(f"描述组 {group.group_id} 时出错: {e}", file=sys.stderr)
                return group.group_id, f"描述生成失败: {str(e)}"

        # 并发处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(describe_group, group): group
                for group in groups
            }

            for future in as_completed(futures):
                group_id, description = future.result()
                # 找到对应的group并设置描述
                for group in groups:
                    if group.group_id == group_id:
                        group.collage_description = description
                        break

    def _cleanup_collages(self, groups: List[WeakRelGroup]) -> None:
        """清理拼图文件"""
        deleted_count = 0
        for group in groups:
            collage_path = group.l3_collage_path
            try:
                if os.path.exists(collage_path):
                    os.remove(collage_path)
                    group._collage_deleted = True
                    deleted_count += 1
            except Exception as e:
                print(f"删除拼图文件失败 {collage_path}: {e}", file=sys.stderr)

        # 尝试删除空的collages目录
        try:
            if groups:
                output_dir = os.path.dirname(groups[0].l3_collage_path)
                if os.path.exists(output_dir) and not os.listdir(output_dir):
                    os.rmdir(output_dir)
        except Exception:
            pass  # 目录删除失败不影响主流程

        print(f">> 已清理 {deleted_count} 个拼图文件", file=sys.stderr)

    def to_json(self, result: SkillResult, indent: int = 2) -> str:
        """将结果转换为JSON字符串"""
        def convert_dataclass(obj):
            if hasattr(obj, '__dataclass_fields__'):
                return asdict(obj)
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        return json.dumps(
            asdict(result),
            ensure_ascii=False,
            indent=indent,
            default=convert_dataclass
        )


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="图片聚类与描述中间组件"
    )
    parser.add_argument(
        "-d", "--dir",
        required=True,
        help="图片文件夹路径"
    )
    parser.add_argument(
        "-o", "--out",
        default="./collages",
        help="拼图输出文件夹（默认: ./collages）"
    )
    parser.add_argument(
        "-p", "--prompt",
        default="请详细描述这些图片的内容",
        help="AI描述提示词"
    )
    parser.add_argument(
        "-m", "--model",
        default="claude-3-5-sonnet-20241022",
        help="使用的Claude模型"
    )
    parser.add_argument(
        "--exe",
        help="指定可执行文件路径"
    )
    parser.add_argument(
        "--api-key",
        help="Anthropic API密钥（或通过ANTHROPIC_API_KEY环境变量）"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="并发描述的最大worker数"
    )
    parser.add_argument(
        "--output",
        help="输出JSON文件路径（默认输出到stdout）"
    )
    parser.add_argument(
        "--keep-collages",
        action="store_true",
        help="保留拼图文件（默认：AI描述完成后自动删除）"
    )

    args = parser.parse_args()

    # 初始化Skill
    try:
        skill = ImageHammingSkill(
            executable_path=args.exe,
            api_key=args.api_key
        )
    except FileNotFoundError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    # 处理图片
    print(f">> 开始处理图片目录: {args.dir}", file=sys.stderr)
    result = skill.process_images(
        image_dir=args.dir,
        output_dir=args.out,
        description_prompt=args.prompt,
        model=args.model,
        max_workers=args.max_workers,
        keep_collages=args.keep_collages
    )

    # 输出结果
    output_json = skill.to_json(result)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_json)
        print(f">> 结果已保存到: {args.output}", file=sys.stderr)
    else:
        print(output_json)

    print(f">> 处理完成，共处理 {result.total_images} 张图片，"
          f"生成 {len(result.groups)} 个聚类组，"
          f"耗时 {result.processing_time_seconds:.2f} 秒", file=sys.stderr)


if __name__ == "__main__":
    main()
