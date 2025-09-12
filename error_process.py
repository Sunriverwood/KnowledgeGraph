import json
import os
from collections import defaultdict
from google import genai
from google.api_core import exceptions

# ================================
# 配置区
# ================================
# 与其他脚本保持一致，配置代理（如果需要）
os.environ["http_proxy"] = "http://127.0.0.1:7890"
os.environ["https_proxy"] = "http://127.0.0.1:7890"

STATE_FILE = "processing_state.json"

# ================================
# 核心功能函数
# ================================

def load_state(state_file):
    """从JSON文件加载状态。"""
    with open(state_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_state(state, state_file):
    """将状态保存到JSON文件。"""
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def print_error_md_table(error_dict):
    """以Markdown表格形式打印错误分类报告。"""
    print("\n| 错误类型 | 文件数 | 文件名 |")
    print("|---|---|---|")
    for error, files in sorted(error_dict.items()):
        # 使用<br>换行以在Markdown单元格内显示多行
        file_list = '<br>'.join(sorted(files))
        print(f"| {error} | {len(files)} | {file_list} |")

def delete_cloud_files(client, state, files_to_delete):
    """根据状态文件中的信息，删除云端的出错文件。"""
    print("\n" + "=" * 50)
    print("🔥 开始删除云端出错文件...")
    print("=" * 50)

    if not files_to_delete:
        print("✅ 无需删除云端文件。")
        return

    deleted_count = 0
    for filename in files_to_delete:
        file_info = state.get(filename, {})
        # 用于API删除的ID是 'uploaded_file_name' (例如 'files/xxxxxx')
        cloud_file_id = file_info.get('uploaded_file_name')

        if cloud_file_id:
            try:
                print(f"  - 准备删除: {filename} (ID: {cloud_file_id})")
                client.files.delete(name=cloud_file_id)
                print(f"    - ✅ 删除成功。")
                deleted_count += 1
            except exceptions.NotFound:
                # 文件在云端已不存在，这不是一个严重错误，直接跳过
                print(f"    - ⚠️ 警告：文件 {cloud_file_id} 在云端未找到，可能已被手动删除。")
            except Exception as e:
                print(f"    - ❌ 删除失败: {filename} (ID: {cloud_file_id})，原因: {e}")
        else:
            # 如果文件在上传阶段就失败了，它不会有云端ID
            print(f"  - ℹ️ 跳过: {filename} (没有关联的云端文件ID，可能在上传阶段已失败)。")

    print(f"\n✅ 云端文件删除操作完成，共删除 {deleted_count} 个文件。")


# ================================
# 主处理逻辑
# ================================
def main():
    """主执行函数，完成错误处理的全流程。"""
    # 1. 初始化 Gemini 客户端
    print("⚙️ 初始化 Gemini Client...")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ 错误：请设置 GEMINI_API_KEY 环境变量后重试。")
        return
    try:
        client = genai.Client(api_key=api_key)
        print("✅ Client 初始化成功。")
    except Exception as e:
        print(f"❌ Client 初始化失败: {e}")
        return

    # 2. 加载状态文件
    print(f"\n" + "=" * 50)
    print(f"🔍 开始处理错误文件，正在读取状态文件 '{STATE_FILE}'...")
    print("=" * 50)
    if not os.path.exists(STATE_FILE):
        print(f"❌ 错误：状态文件 '{STATE_FILE}' 不存在。请先运行 `gemini_json_batch.py`。")
        return
    state = load_state(STATE_FILE)

    # 3. 识别出错文件并分类
    error_type_dict = defaultdict(list)
    files_with_errors = []
    for filename, data in state.items():
        status = data.get('status', '')
        # 只要状态包含'failed'或'error'关键字，就认为是失败项
        if 'failed' in status or 'error' in data:
            error_message = data.get('error', '未知错误')
            error_type_dict[error_message].append(filename)
            files_with_errors.append(filename)

    if not files_with_errors:
        print("\n🎉 恭喜！状态文件中没有发现任何出错的文件。无需任何操作。")
        return

    # 4. 生成并打印错误报告
    print("\n📋 生成错误类型清单 (Markdown 格式):")
    print_error_md_table(error_type_dict)

    # 5. 从云端删除对应的失败文件
    delete_cloud_files(client, state, files_with_errors)

    # 6. 重置本地状态文件中的失败项
    print("\n" + "=" * 50)
    print("🔄 正在重置本地状态文件，以便重新处理...")
    print("=" * 50)
    reset_count = 0
    for filename in files_with_errors:
        if filename in state:
            # 将失败条目完全重置为一个干净的待上传状态
            state[filename] = {'status': 'pending_upload'}
            reset_count += 1
            print(f"  - 已重置状态: {filename}")

    # 7. 保存更新后的状态
    save_state(state, STATE_FILE)
    print(f"\n✅ 状态重置完成，共 {reset_count} 个文件被标记为 'pending_upload'。")
    print(f"💾 新的状态已保存到 '{STATE_FILE}'。")
    print("\n➡️ 下次运行 `gemini_json_batch.py` 时将自动重新处理这些文件。")

if __name__ == '__main__':
    main()