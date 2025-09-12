import os
import json


def flatten_properties(obj, parent_key='', sep='.'):
    """
    递归地将一个可能包含嵌套字典的字典扁平化。
    """
    items = []
    for k, v in obj.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_properties(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def merge_and_flatten_knowledge_graph_json(source_directory, output_filename):
    """
    遍历指定目录下的所有 JSON 文件，将它们的 'nodes' 和 'relationships'
    合并并扁平化到一个统一的 JSON 文件中。

    Args:
        source_directory (str): 包含源 JSON 文件的文件夹路径。
        output_filename (str): 合并后输出的 JSON 文件名。
    """
    merged_nodes = []
    merged_relationships = []
    processed_files_count = 0
    filtered_rels_count = 0

    print(f"开始扫描目录: '{source_directory}'...")

    for filename in os.listdir(source_directory):
        if filename.endswith('.json'):
            file_path = os.path.join(source_directory, filename)

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                    if 'nodes' in data and isinstance(data['nodes'], list):
                        for node in data['nodes']:
                            if 'properties' in node and isinstance(node['properties'], dict):
                                node['properties'] = flatten_properties(node['properties'])
                        merged_nodes.extend(data['nodes'])

                    if 'relationships' in data and isinstance(data['relationships'], list):
                        for rel in data['relationships']:
                            # 校验 type 字段，只有存在且不为 None 的关系才处理
                            if not rel.get('type'):
                                filtered_rels_count += 1
                                continue
                            if 'properties' in rel and isinstance(rel['properties'], dict):
                                rel['properties'] = flatten_properties(rel['properties'])
                            merged_relationships.append(rel)

                    print(f"  [+] 成功处理文件: {filename}")
                    processed_files_count += 1

            except json.JSONDecodeError:
                print(f"  [!] 警告: 文件 '{filename}' 不是有效的 JSON 格式，已跳过。")
            except Exception as e:
                print(f"  [!] 错误: 处理文件 '{filename}' 时发生错误: {e}")

    if processed_files_count == 0:
        print("未找到任何 JSON 文件，程序退出。")
        return

    merged_graph = {
        "nodes": merged_nodes,
        "relationships": merged_relationships
    }

    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(merged_graph, f, ensure_ascii=False, indent=2)

        print("\n合并并扁平化完成！")
        print(f"  - 总共处理了 {processed_files_count} 个 JSON 文件。")
        if filtered_rels_count > 0:
            print(f"  - 总共过滤了 {filtered_rels_count} 个无效关系。")
        print(f"  - 合并后的节点总数: {len(merged_nodes)}")
        print(f"  - 合并后的关系总数: {len(merged_relationships)}")
        print(f"  - 结果已保存至: '{output_filename}'")

    except Exception as e:
        print(f"\n[!] 错误: 无法写入输出文件 '{output_filename}': {e}")


# --- 使用示例 ---
if __name__ == "__main__":
    SOURCE_FOLDER = './json/'  # 使用 './' 代表当前脚本所在的文件夹
    OUTPUT_FILE = 'merged_knowledge_graph.json'

    merge_and_flatten_knowledge_graph_json(SOURCE_FOLDER, OUTPUT_FILE)