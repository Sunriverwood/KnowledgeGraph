import os
import json


def merge_knowledge_graph_json(source_directory, output_filename):
    """
    遍历指定目录下的所有 JSON 文件，将它们的 'nodes' 和 'relationships'
    合并到一个统一的 JSON 文件中。

    此函数假设每个 JSON 文件都包含 'nodes' 和 'relationships' 键，
    并且它们的值都是列表。

    Args:
        source_directory (str): 包含源 JSON 文件的文件夹路径。
        output_filename (str): 合并后输出的 JSON 文件名。
    """
    # 初始化用于存储所有节点和关系的列表
    merged_nodes = []
    merged_relationships = []

    # 记录已处理的文件数量
    processed_files_count = 0

    print(f"开始扫描目录: '{source_directory}'...")

    # 遍历源目录中的所有文件
    for filename in os.listdir(source_directory):
        # 确保只处理 .json 文件
        if filename.endswith('.json'):
            file_path = os.path.join(source_directory, filename)

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                    # 检查文件结构是否符合预期
                    if 'nodes' in data and isinstance(data['nodes'], list):
                        merged_nodes.extend(data['nodes'])

                    if 'relationships' in data and isinstance(data['relationships'], list):
                        merged_relationships.extend(data['relationships'])

                    print(f"  [+] 成功处理文件: {filename}")
                    processed_files_count += 1

            except json.JSONDecodeError:
                print(f"  [!] 警告: 文件 '{filename}' 不是有效的 JSON 格式，已跳过。")
            except Exception as e:
                print(f"  [!] 错误: 处理文件 '{filename}' 时发生错误: {e}")

    # 如果没有处理任何文件，则提前退出
    if processed_files_count == 0:
        print("未找到任何 JSON 文件，程序退出。")
        return

    # 构建最终的合并后对象
    merged_graph = {
        "nodes": merged_nodes,
        "relationships": merged_relationships
    }

    # 将合并后的数据写入新的 JSON 文件
    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            # 使用 indent=2  JSON 文件格式优美，易于阅读
            json.dump(merged_graph, f, ensure_ascii=False, indent=2)

        print("\n合并完成！")
        print(f"  - 总共处理了 {processed_files_count} 个 JSON 文件。")
        print(f"  - 合并后的节点总数: {len(merged_nodes)}")
        print(f"  - 合并后的关系总数: {len(merged_relationships)}")
        print(f"  - 结果已保存至: '{output_filename}'")

    except Exception as e:
        print(f"\n[!] 错误: 无法写入输出文件 '{output_filename}': {e}")


# --- 使用示例 ---
if __name__ == "__main__":
    # 设置您的源文件夹路径。请根据实际情况修改。
    SOURCE_FOLDER = './json/'  # 使用 './' 代表当前脚本所在的文件夹

    # 设置合并后的输出文件名
    OUTPUT_FILE = 'merged_knowledge_graph.json'

    # 执行合并函数
    merge_knowledge_graph_json(SOURCE_FOLDER, OUTPUT_FILE)