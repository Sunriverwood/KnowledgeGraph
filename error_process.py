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

# 【核心修改】更新错误映射，将错误类型归类到指定的三个文件夹中
UNRECOVERABLE_ERROR_MAP = {
    # 尺寸/Token限制 -> files_oversized
    "exceeds the supported page limit": "files_oversized",
    "exceeds the maximum number of tokens": "files_oversized",

    # 网络/连接问题 -> files_disconnected
    "Server disconnected without sending a response": "files_disconnected",
    "[WinError 10054]": "files_disconnected",

    # 其他问题 -> files_other_questions
    "The document has no pages": "files_other_questions",
    "Request contains an invalid argument": "files_other_questions"
}

# ================================
# 核心功能函数 (无变动)
# ================================

def load_state(state_file):
    with open(state_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_state(state, state_file):
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def save_error_md_table(error_dict, md_file='错误文件清单.md'):
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write("\n| 错误类型 | 文件数 | 文件名 |\n")
        f.write("|---|---|---|\n")
        for error, files in sorted(error_dict.items()):
            file_list = '<br>'.join(sorted(files))
            f.write(f"| {error} | {len(files)} | {file_list} |\n")
    print(f"✅ 错误报告已写入 {md_file}")

def delete_cloud_files(client, state, files_to_delete):
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
                print(f"    - ⚠️ 警告：文件 {cloud_file_id} 在云端未找到。")
            except Exception as e:
                print(f"    - ❌ 删除失败: {filename} (ID: {cloud_file_id})，原因: {e}")
        else:
            print(f"  - ℹ️ 跳过: {filename} (无云端文件ID)。")
    print(f"\n✅ 云端文件删除操作完成，共删除 {deleted_count} 个文件。")

def move_and_quarantine_files(quarantine_plan):
    """
    根据归档计划，将本地文件移动到对应的错误类型文件夹。
    quarantine_plan: 一个字典 { "文件名": "目标文件夹", ... }
    """
    print("\n" + "=" * 50)
    print(f"📦 开始归档本地无法处理的文件...")
    print("=" * 50)
    if not quarantine_plan:
        print("✅ 无需归档本地文件。")
        return

    moved_count = 0
    for filename, folder in quarantine_plan.items():
        os.makedirs(folder, exist_ok=True)
        source_path = os.path.join(PDF_SOURCE_FOLDER, filename)
        destination_path = os.path.join(folder, filename)

        if os.path.exists(source_path):
            try:
                shutil.move(source_path, destination_path)
                print(f"  - 🚚 已移动 '{filename}' 到 '{folder}'")
                moved_count += 1
            except Exception as e:
                print(f"  - ❌ 移动失败: {filename}, 原因: {e}")
        else:
            print(f"  - ⚠️ 警告：本地文件未找到，无法移动: {source_path}")
    print(f"\n✅ 本地文件归档操作完成，共移动 {moved_count} 个文件。")


# ================================
# 主处理逻辑 (无变动)
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
    if not os.path.exists(STATE_FILE):
        print(f"❌ 错误：状态文件 '{STATE_FILE}' 不存在。")
        return
    state = load_state(STATE_FILE)

    # 3. 识别并分类出错文件，制定归档计划
    print(f"\n" + "=" * 50)
    print(f"🔍 开始分析状态文件 '{STATE_FILE}'...")
    print("=" * 50)
    error_type_dict = defaultdict(list)
    files_with_errors = []
    files_to_quarantine = {}

    for filename, data in state.items():
        if 'failed' in data.get('status', '') or 'error' in data:
            error_message = data.get('error', '未知错误')
            files_with_errors.append(filename)
            error_type_dict[error_message].append(filename)

            for error_key, folder in UNRECOVERABLE_ERROR_MAP.items():
                if error_key in error_message:
                    files_to_quarantine[filename] = folder
                    break

    if not files_with_errors:
        print("\n🎉 恭喜！状态文件中没有发现任何出错的文件。")
        return

    # 4. 报错错误报告
    save_error_md_table(error_type_dict)

    # 5. 执行文件归档操作
    move_and_quarantine_files(files_to_quarantine)

    # 6. 删除所有出错文件在云端的副本
    delete_cloud_files(client, state, files_with_errors)

    # 7. 更新本地状态文件
    print("\n" + "=" * 50)
    print(f"🔄 正在更新本地状态文件 '{STATE_FILE}'...")
    print("=" * 50)
    files_to_remove_from_state = set(files_to_quarantine.keys())
    removed_count = 0
    reset_count = 0

    for filename in files_with_errors:
        if filename in state:
            if filename in files_to_remove_from_state:
                del state[filename]
                removed_count += 1
                print(f"  - 🗑️ 已从状态文件中移除条目: {filename}")
            else:
                state[filename] = {'status': 'pending_upload'}
                reset_count += 1
                print(f"  - 🔄 已重置状态以便重试: {filename}")

    # 8. 保存最终状态并总结
    save_state(state, STATE_FILE)
    print(f"\n✅ 状态文件更新完成。")
    print(f"  - {removed_count} 个条目因文件被归档而移除。")
    print(f"  - {reset_count} 个条目被重置为 'pending_upload' 以便重试。")
    print(f"💾 新的状态已保存到 '{STATE_FILE}'。")

if __name__ == '__main__':
    main()