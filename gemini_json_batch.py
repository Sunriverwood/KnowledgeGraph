import os
import json
import time
import hashlib  # 新增：导入哈希库
from datetime import datetime, timedelta

from google import genai
from google.genai import types
from google.api_core import exceptions

# ================================
# 配置区
# ================================
# 每个小批次包含的PDF文件数量
BATCH_SIZE = 20
# 单个批次的最长轮询时间
BATCH_POLLING_TIMEOUT_SECONDS = 8 * 60 * 60
# 状态持久化文件
STATE_FILE = "processing_state.json"

# 配置代理（如果需要）
os.environ["http_proxy"] = "http://127.0.0.1:7890"
os.environ["https_proxy"] = "http://127.0.0.1:7890"


# ================================
# 状态管理函数
# ================================
def load_state():
    """加载处理状态，如果文件不存在则初始化。"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_state(state):
    """将当前处理状态保存到文件。"""
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=4, ensure_ascii=False)


# ================================
# 指令加载函数
# ================================
def load_graph_instructions(filepath="任务：根据混合Schema从PDF构建可直接导入的知识图谱.md"):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


# ================================
# 核心功能函数 (重构)
# ================================
def process_job_results(client, batch_job, state, output_folder):
    """处理成功作业的结果，并更新状态文件。"""
    print(f"  -> 正在处理作业 '{batch_job.name}' 的结果...")

    # 结果以内联响应的形式返回
    if batch_job.dest and batch_job.dest.inlined_responses:
        for inline_response in batch_job.dest.inlined_responses:
            safe_key = inline_response.key

            # 通过 safe_key 找到对应的原始文件名
            original_filename = None
            for fname, data in state.items():
                if data.get('safe_key') == safe_key and data.get('batch_job_name') == batch_job.name:
                    original_filename = fname
                    break

            if not original_filename:
                print(f"  - ⚠️ 警告：在状态文件中找不到 key '{safe_key}' 对应的文件。")
                continue

            # 处理成功响应
            if inline_response.response:
                try:
                    # 提取、清理并验证JSON
                    cleaned_json_text = inline_response.response.text.strip().replace("```json", "").replace("```",
                                                                                                             "").strip()
                    json_data = json.loads(cleaned_json_text)

                    # 保存JSON文件
                    json_filename = os.path.splitext(original_filename)[0] + ".json"
                    json_path = os.path.join(output_folder, json_filename)
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(json_data, f, ensure_ascii=False, indent=2)

                    print(f"    - ✅ 成功处理 '{original_filename}' -> {json_path}")
                    state[original_filename]['status'] = 'completed'

                except json.JSONDecodeError:
                    error_msg = "模型未能返回有效的JSON格式"
                    print(f"    - ❌ 处理 '{original_filename}' 失败: {error_msg}")
                    state[original_filename].update({'status': 'failed_parsing', 'error': error_msg})
                except Exception as e:
                    error_msg = f"保存文件时出错: {e}"
                    print(f"    - ❌ 处理 '{original_filename}' 失败: {error_msg}")
                    state[original_filename].update({'status': 'failed_saving', 'error': error_msg})

            # 处理错误响应
            elif inline_response.error:
                error_msg = inline_response.error.message
                print(f"    - ❌ 处理 '{original_filename}' 时API返回错误: {error_msg}")
                state[original_filename].update({'status': 'failed_api_error', 'error': error_msg})

    else:
        print(f"  - ⚠️ 作业 '{batch_job.name}' 成功，但未找到内联结果。")
        # 将此作业关联的所有文件都标记为失败
        for filename, data in state.items():
            if data.get('batch_job_name') == batch_job.name:
                data.update({'status': 'failed_no_result', 'error': '作业成功但无内联结果返回'})


def generate_final_report(state):
    """根据最终状态生成清晰的处理报告。"""
    successful_files = [f for f, data in state.items() if data.get('status') == 'completed']
    failed_files = [f for f, data in state.items() if 'failed' in data.get('status', '')]
    pending_files = [f for f, data in state.items() if
                     data.get('status') not in ['completed'] and 'failed' not in data.get('status', '')]

    print("\n" + "=" * 50)
    print("📋 最终处理报告")
    print("=" * 50)

    print(f"\n✅ 处理成功 ({len(successful_files)} 个文件):")
    if successful_files:
        for f in successful_files: print(f"  - {f}")
    else:
        print("  - 无")

    print(f"\n❌ 处理失败 ({len(failed_files)} 个文件):")
    if failed_files:
        for f in failed_files:
            error = state[f].get('error', '未知错误')
            print(f"  - {f} (原因: {error})")
    else:
        print("  - 无")

    if pending_files:
        print(f"\n⏳ 待处理/处理中 ({len(pending_files)} 个文件):")
        for f in pending_files: print(f"  - {f}")

    print("\n" + "=" * 50)


# ================================
# 主程序 (全新工作流)
# ================================
def main():
    # 1. 初始化
    pdf_folder = "data_test"
    output_folder = "json"
    model_name = "models/gemini-1.5-pro"  # 确保使用的模型支持批处理

    if not os.path.exists(pdf_folder): os.makedirs(pdf_folder)
    os.makedirs(output_folder, exist_ok=True)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: raise ValueError("❌ 错误：请设置 GEMINI_API_KEY 环境变量")

    client = genai.Client(api_key=api_key)
    instructions = load_graph_instructions()
    if not instructions:
        print("❌ 错误：未能加载指令文件。")
        return

    state = load_state()

    # 2. 文件发现与状态同步
    print(">> 阶段 1: 文件发现与状态同步...")
    current_pdfs = {f for f in os.listdir(pdf_folder) if f.lower().endswith(".pdf")}
    for pdf_file in current_pdfs:
        if pdf_file not in state:
            state[pdf_file] = {'status': 'pending_upload'}
    save_state(state)

    # 3. 上传待上传的文件
    print("\n>> 阶段 2: 上传新文件...")
    files_to_upload = [f for f, data in state.items() if data['status'] == 'pending_upload']
    if files_to_upload:
        for pdf_file in files_to_upload:
            pdf_path = os.path.join(pdf_folder, pdf_file)
            try:
                print(f"  - 正在上传: {pdf_file}")
                response = client.files.upload(file=pdf_path)
                state[pdf_file].update({
                    'status': 'uploaded',
                    'uploaded_file_uri': response.uri
                })
            except Exception as e:
                state[pdf_file].update({'status': 'failed_upload', 'error': str(e)})
            finally:
                save_state(state)
    else:
        print("  - 无新文件需要上传。")

    # 4. 创建批处理作业
    print("\n>> 阶段 3: 为待处理文件创建批处理作业...")
    requests_to_process = []
    # 存储原始文件名到安全key的映射，以便更新状态
    file_to_key_map = {}

    for pdf_file, data in state.items():
        # 只为已上传且未被处理的文件创建请求
        if data['status'] == 'uploaded':
            # 修改：使用文件名的SHA256哈希值作为安全的key
            safe_key = hashlib.sha256(pdf_file.encode('utf-8')).hexdigest()
            file_to_key_map[safe_key] = pdf_file

            requests_to_process.append({
                "key": safe_key,  # 使用安全key
                "request": {
                    "contents": [{"role": "user", "parts": [{"text": instructions}, {
                        "file_data": {"mime_type": "application/pdf", "file_uri": data['uploaded_file_uri']}}]}],
                    "generationConfig": {"response_mime_type": "application/json"}
                }
            })

    if requests_to_process:
        request_chunks = [requests_to_process[i:i + BATCH_SIZE] for i in range(0, len(requests_to_process), BATCH_SIZE)]
        for i, chunk in enumerate(request_chunks):
            job_display_name = f"KG-Batch-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{i + 1}"
            try:
                print(f"  - 正在为 {len(chunk)} 个文件创建批处理作业 '{job_display_name}'...")
                # 补全：创建批处理作业
                batch_job = client.batches.create(
                    model=model_name,
                    src=chunk,  # 直接使用内联请求
                    config={'display_name': job_display_name}
                )
                print(f"  - 作业创建成功: {batch_job.name}")

                # 补全：更新 state 中对应文件的状态
                for req in chunk:
                    safe_key = req['key']
                    original_file = file_to_key_map[safe_key]
                    if original_file in state:
                        state[original_file].update({
                            'status': 'processing',
                            'batch_job_name': batch_job.name,
                            'safe_key': safe_key  # 保存safe_key用于结果匹配
                        })
                save_state(state)

            except Exception as e:
                print(f"  - ❌ 创建批处理作业失败: {e}")
                # 将此批次中所有文件的状态标记为失败
                for req in chunk:
                    safe_key = req['key']
                    original_file = file_to_key_map[safe_key]
                    if original_file in state:
                        state[original_file].update({'status': 'failed_job_creation', 'error': str(e)})
                save_state(state)
    else:
        print("  - 无待处理文件需要创建新作业。")

    # 5. 监控所有“处理中”的作业
    print("\n>> 阶段 4: 监控所有处理中的作业...")

    # 动态构建需要监控的作业列表
    active_jobs = {}
    for data in state.values():
        if data.get('status') == 'processing':
            job_name = data['batch_job_name']
            if job_name not in active_jobs:
                active_jobs[job_name] = {'start_time': datetime.now()}

    while active_jobs:
        time.sleep(60)
        finished_jobs = set()

        for job_name, job_info in list(active_jobs.items()):
            # 检查超时
            elapsed = datetime.now() - job_info['start_time']
            if elapsed.total_seconds() > BATCH_POLLING_TIMEOUT_SECONDS:
                print(f"  - ⏰ 作业 '{job_name}' 超时 (超过8小时)，正在尝试取消...")
                try:
                    client.batches.cancel(name=job_name)
                except exceptions.NotFound:
                    pass

                # 更新所有相关文件的状态为失败
                for pdf, data in state.items():
                    if data.get('batch_job_name') == job_name:
                        data.update({'status': 'failed_timeout', 'error': '批处理作业运行超过8小时'})
                save_state(state)
                finished_jobs.add(job_name)
                continue

            # 获取作业状态
            try:
                job = client.batches.get(name=job_name)
                if job.state.name in ('JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED', 'JOB_STATE_EXPIRED',
                                      'JOB_STATE_CANCELLED'):
                    if job.state.name == 'JOB_STATE_SUCCEEDED':
                        # 调用函数处理结果并更新 state
                        process_job_results(client, job, state, output_folder)
                    else:
                        # 更新 state 中相关文件的 status 为失败
                        error_detail = str(job.error) if job.error else f"作业以 {job.state.name} 状态结束"
                        print(f"  - ❌ 作业 '{job_name}' 未成功，状态: {job.state.name}")
                        for pdf, data in state.items():
                            if data.get('batch_job_name') == job_name:
                                data.update({'status': f'failed_{job.state.name.lower()}', 'error': error_detail})

                    save_state(state)
                    finished_jobs.add(job_name)

            except exceptions.NotFound:
                print(f"  - ❌ 作业 '{job_name}' 在API侧找不到了，标记为失败。")
                for pdf, data in state.items():
                    if data.get('batch_job_name') == job_name:
                        data.update({'status': 'failed_not_found', 'error': '作业在API端丢失'})
                save_state(state)
                finished_jobs.add(job_name)
            except Exception as e:
                print(f"  - ❌ 监控作业 '{job_name}' 时发生错误: {e}")

        for finished_job in finished_jobs:
            del active_jobs[finished_job]

        if active_jobs:
            print(f"  - ({datetime.now().strftime('%H:%M:%S')}) 仍有 {len(active_jobs)} 个作业在运行中...")

    # 6. 生成最终报告
    print("\n>> 阶段 5: 所有作业处理完毕，生成报告...")
    generate_final_report(state)


if __name__ == "__main__":
    main()