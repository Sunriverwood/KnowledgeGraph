import json
import os
import shutil
from collections import defaultdict
from google import genai
from google.api_core import exceptions

# ================================
# 配置区
# ================================
os.environ["http_proxy"] = "http://127.0.0.1:7890"
os.environ["https_proxy"] = "http://127.0.0.1:7890"

STATE_FILE = "processing_state.json"
PDF_SOURCE_FOLDER = "data"
QUARANTINE_FOLDER = "oversized_files"

# ================================
# 核心功能函数 (无变动)
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
        cloud_file_id = file_info.get('uploaded_file_name')
        if cloud_file_id:
            try:
                print(f"  - 准备删除: {filename} (ID: {cloud_file_id})")
                client.files.delete(name=cloud_file_id)
                print(f"    - ✅ 删除成功。")
                deleted_count += 1
            except exceptions.NotFound:
                print(f"    - ⚠️ 警告：文件 {cloud_file_id} 在云端未找到，可能已被手动删除。")
            except Exception as e:
                print(f"    - ❌ 删除失败: {filename} (ID: {cloud_file_id})，原因: {e}")
        else:
            print(f"  - ℹ️ 跳过: {filename} (没有关联的云端文件ID，可能在上传阶段已失败)。")
    print(f"\n✅ 云端文件删除操作完成，共删除 {deleted_count} 个文件。")

def move_oversized_local_files(files_to_move):
    """将因尺寸超限而无法处理的本地PDF文件移动到隔离文件夹。"""
    print("\n" + "=" * 50)
    print(f"📦 开始移动无法处理的本地文件到 '{QUARANTINE_FOLDER}' 文件夹...")
    print("=" * 50)
    if not files_to_move:
        print("✅ 无需移动本地文件。")
        return
    os.makedirs(QUARANTINE_FOLDER, exist_ok=True)
    moved_count = 0
    for filename in files_to_move:
        source_path = os.path.join(PDF_SOURCE_FOLDER, filename)
        destination_path = os.path.join(QUARANTINE_FOLDER, filename)
        if os.path.exists(source_path):
            try:
                shutil.move(source_path, destination_path)
                print(f"  - 🚚 已移动: {filename}")
                moved_count += 1
            except Exception as e:
                print(f"  - ❌ 移动失败: {filename}, 原因: {e}")
        else:
            print(f"  - ⚠️ 警告：本地文件未找到，无法移动: {source_path}")
    print(f"\n✅ 本地文件移动操作完成，共移动 {moved_count} 个文件。")


# ================================
# 主处理逻辑
# ================================
def main():
    """主执行函数，完成错误处理的全流程。"""
    # 1. 初始化客户端
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

    # 3. 识别并分类出错文件
    error_type_dict = defaultdict(list)
    files_with_errors = []
    files_to_move_locally = []
    for filename, data in state.items():
        status = data.get('status', '')
        if 'failed' in status or 'error' in data:
            error_message = data.get('error', '未知错误')
            error_type_dict[error_message].append(filename)
            files_with_errors.append(filename)
            if ("exceeds the supported page limit" in error_message or
                "exceeds the maximum number of tokens" in error_message):
                files_to_move_locally.append(filename)

    if not files_with_errors:
        print("\n🎉 恭喜！状态文件中没有发现任何出错的文件。无需任何操作。")
        return

    # 4. 打印错误报告
    print("\n📋 生成错误类型清单 (Markdown 格式):")
    print_error_md_table(error_type_dict)

    # 5. 移动本地过大文件
    move_oversized_local_files(files_to_move_locally)

    # 6. 删除云端文件
    delete_cloud_files(client, state, files_with_errors)

    # 7. 【核心修改】更新本地状态文件：移除已移动文件的条目，重置其他失败文件的状态
    print("\n" + "=" * 50)
    print(f"🔄 正在更新本地状态文件 '{STATE_FILE}'...")
    print("=" * 50)

    files_to_move_set = set(files_to_move_locally)
    removed_count = 0
    reset_count = 0

    # 遍历所有出错文件
    for filename in files_with_errors:
        if filename in state:
            if filename in files_to_move_set:
                # 如果文件已被移动，则从状态字典中删除其条目
                del state[filename]
                removed_count += 1
                print(f"  - 🗑️ 已从状态文件中移除条目: {filename}")
            else:
                # 如果是其他可恢复错误，则重置状态以便重试
                state[filename] = {'status': 'pending_upload'}
                reset_count += 1
                print(f"  - 🔄 已重置状态以便重试: {filename}")

    # 8. 保存最终的状态文件
    save_state(state, STATE_FILE)
    print(f"\n✅ 状态文件更新完成。")
    print(f"  - {removed_count} 个条目因文件被移动而移除。")
    print(f"  - {reset_count} 个条目被重置为 'pending_upload' 以便重试。")
    print(f"💾 新的状态已保存到 '{STATE_FILE}'。")

if __name__ == '__main__':
    main()