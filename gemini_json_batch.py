import os
import json
import time
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
        json.dump(state, f, indent=2, ensure_ascii=False)


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
# 核心功能函数 (重构和实现)
# ================================
def process_job_results(client, batch_job, state, output_folder):
    """
    【已实现】处理成功作业的结果，并更新状态文件。
    """
    print(f"  -> 正在处理作业 '{batch_job.name}' 的结果...")
    if not (batch_job.dest and batch_job.dest.file_name):
        print(f"  - ❌ 错误：作业 '{batch_job.name}' 成功，但未找到输出文件。")
        # 将所有与此作业相关的任务标记为失败
        for pdf_file, data in state.items():
            if data.get('batch_job_name') == batch_job.name:
                data.update({'status': 'failed_job_no_output', 'error': '作业成功但无输出文件'})
        return

    result_file_name = batch_job.dest.file_name
    try:
        print(f"  - 📥 正在下载结果文件: {result_file_name}")
        file_content = client.files.download(file=result_file_name).decode('utf-8')

        # 逐行解析 JSONL 结果文件
        for line in file_content.strip().split('\n'):
            result = json.loads(line)
            original_pdf_key = result.get("key")

            # 如果找不到key，则无法关联，跳过此行
            if not original_pdf_key:
                print(f"  - ⚠️ 警告：在结果文件中发现一个没有 'key' 的条目。")
                continue

            # 检查原始PDF是否存在于状态中
            if original_pdf_key not in state:
                print(f"  - ⚠️ 警告：结果文件中的 key '{original_pdf_key}' 不在当前状态跟踪中。")
                continue

            # 处理单个请求的成功情况
            if result.get("response"):
                output_filename = os.path.splitext(original_pdf_key)[0] + ".json"
                output_path = os.path.join(output_folder, output_filename)
                try:
                    # 提取 JSON 内容
                    json_text = result["response"]["candidates"][0]["content"]["parts"][0]["text"]
                    # 清理并验证
                    cleaned_json = json_text.strip().replace("```json", "").replace("```", "").strip()
                    json_data = json.loads(cleaned_json)
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(json_data, f, ensure_ascii=False, indent=2)

                    state[original_pdf_key].update({'status': 'completed', 'output_path': output_path})
                    print(f"    - ✅ 成功: '{original_pdf_key}' 的结果已保存到 {output_path}")

                except (KeyError, IndexError, json.JSONDecodeError) as e:
                    state[original_pdf_key].update({'status': 'failed_parsing', 'error': f"解析结果失败: {e}"})
                    print(f"    - ❌ 失败: 解析 '{original_pdf_key}' 的结果时出错: {e}")

            # 处理单个请求的失败情况
            elif result.get("error"):
                error_message = result['error'].get('message', '未知错误')
                state[original_pdf_key].update({'status': 'failed_in_job', 'error': error_message})
                print(f"    - ❌ 失败: 处理 '{original_pdf_key}' 时API返回错误: {error_message}")

    except Exception as e:
        print(f"  - ❌ 严重错误: 处理结果文件 '{result_file_name}' 时发生意外: {e}")
        # 将所有与此作业相关的任务标记为失败
        for pdf_file, data in state.items():
            if data.get('batch_job_name') == batch_job.name:
                data.update({'status': 'failed_processing_results', 'error': str(e)})


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
    pdf_folder = "data"
    output_folder = "json"
    model_name = "models/gemini-2.5-pro"

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
    print(" Fase 1: 文件发现与状态同步...")
    current_pdfs = {f for f in os.listdir(pdf_folder) if f.lower().endswith(".pdf")}
    for pdf_file in current_pdfs:
        if pdf_file not in state:
            state[pdf_file] = {'status': 'pending_upload'}
    save_state(state)
    print("  - 状态同步完成。")

    # 3. 上传待上传的文件
    print("\n Fase 2: 上传新文件...")
    files_to_upload = [f for f, data in state.items() if data['status'] == 'pending_upload']
    if files_to_upload:
        for pdf_file in files_to_upload:
            pdf_path = os.path.join(pdf_folder, pdf_file)
            try:
                print(f"  - 正在上传: {pdf_file}")
                response = client.files.upload(file=pdf_path)
                state[pdf_file].update({
                    'status': 'uploaded',
                    'uploaded_file_uri': response.uri,
                    'uploaded_file_name': response.name
                })
            except Exception as e:
                state[pdf_file].update({'status': 'failed_upload', 'error': str(e)})
            finally:
                save_state(state)
    else:
        print("  - 无新文件需要上传。")

    # 4. 创建批处理作业
    print("\n Fase 3: 为待处理文件创建批处理作业...")
    requests_to_process = []
    files_for_this_batch = []  # 记录哪些文件被包含在将要创建的批处理中
    for pdf_file, data in state.items():
        if data['status'] == 'uploaded':
            requests_to_process.append({
                "key": pdf_file,
                "request": {
                    "contents": [{"role": "user", "parts": [{"text": instructions}, {
                        "file_data": {"mime_type": "application/pdf", "file_uri": data['uploaded_file_uri']}}]}],
                    "generationConfig": {"response_mime_type": "application/json"}
                }
            })
            files_for_this_batch.append(pdf_file)

    if requests_to_process:
        request_chunks = [requests_to_process[i:i + BATCH_SIZE] for i in range(0, len(requests_to_process), BATCH_SIZE)]
        files_chunks = [files_for_this_batch[i:i + BATCH_SIZE] for i in range(0, len(files_for_this_batch), BATCH_SIZE)]

        for i, (chunk, files_in_chunk) in enumerate(zip(request_chunks, files_chunks)):
            batch_requests_file = f"temp_batch_requests_{i}.jsonl"
            job_display_name = f"KG-Batch-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{i + 1}"

            try:
                # 写入临时的 JSONL 文件
                with open(batch_requests_file, "w", encoding="utf-8") as f:
                    for req in chunk:
                        f.write(json.dumps(req) + "\n")

                # 上传 JSONL 文件
                print(f"  - 正在上传请求文件 '{batch_requests_file}'...")
                batch_input_file = client.files.upload(
                    file=batch_requests_file,
                    config=types.UploadFileConfig(display_name=job_display_name, mime_type='jsonl')
                )

                # 创建批处理作业
                print(f"  - 正在创建批处理作业 '{job_display_name}'...")
                batch_job = client.batches.create(
                    model=model_name,
                    src=batch_input_file.name,
                    config={'display_name': job_display_name}
                )
                print(f"  - ✅ 作业创建成功: {batch_job.name}")

                # 更新状态
                for pdf in files_in_chunk:
                    state[pdf].update({'status': 'processing', 'batch_job_name': batch_job.name})
                save_state(state)

            except Exception as e:
                print(f"  - ❌ 创建批处理作业块 {i + 1} 时失败: {e}")
                # 将此块中的文件标记为失败
                for pdf in files_in_chunk:
                    state[pdf].update({'status': 'failed_job_creation', 'error': str(e)})
                save_state(state)
            finally:
                # 清理临时文件
                if os.path.exists(batch_requests_file):
                    os.remove(batch_requests_file)
    else:
        print("  - 无待处理文件需要创建新作业。")

    # 5. 监控所有“处理中”的作业
    print("\n Fase 4: 监控所有处理中的作业...")
    active_job_names = {data['batch_job_name'] for data in state.values() if data.get('status') == 'processing'}

    if not active_job_names:
        print("  - 当前无活动作业需要监控。")
    else:
        start_times = {name: datetime.now() for name in active_job_names}
        while active_job_names:
            print(f"  - 正在监控 {len(active_job_names)} 个活动作业...")
            for job_name in active_job_names:
                try:
                    job = client.batches.get(name=job_name)
                    print(f"  - 作业 '{job_name}' 当前状态: {job.state.name} ({time.strftime('%Y-%m-%d %H:%M:%S')})")
                except Exception as e:
                    print(f"  - 获取作业 '{job_name}' 状态时出错: {e}")
            sleep_interval = 600
            time.sleep(sleep_interval)
            finished_jobs = set()

            for job_name in list(active_job_names):
                # 检查超时
                elapsed = datetime.now() - start_times.get(job_name, datetime.now())
                if elapsed.total_seconds() > BATCH_POLLING_TIMEOUT_SECONDS:
                    print(f"⏰ 作业 '{job_name}' 超时，正在尝试取消...")
                    try:
                        client.batches.cancel(name=job_name)
                    except exceptions.NotFound:
                        pass

                    for pdf, data in state.items():
                        if data.get('batch_job_name') == job_name:
                            data.update({'status': 'failed_timeout', 'error': '批处理作业运行超时'})
                    save_state(state)
                    finished_jobs.add(job_name)
                    continue

                # 获取作业状态
                try:
                    job = client.batches.get(name=job_name)
                    if job.state.name in ('JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED', 'JOB_STATE_EXPIRED',
                                          'JOB_STATE_CANCELLED'):
                        print(f"  -> 作业 '{job.name}' 已完成，状态: {job.state.name}")
                        if job.state.name == 'JOB_STATE_SUCCEEDED':
                            process_job_results(client, job, state, output_folder)
                        else:
                            error_detail = str(job.error) if job.error else f"作业以状态 {job.state.name} 结束"
                            for pdf, data in state.items():
                                if data.get('batch_job_name') == job_name:
                                    data.update({'status': f'failed_{job.state.name.lower()}', 'error': error_detail})

                        save_state(state)
                        finished_jobs.add(job_name)
                except exceptions.NotFound:
                    print(f"  - ⚠️ 作业 '{job_name}' 在API侧未找到，可能已被删除。将其标记为失败。")
                    for pdf, data in state.items():
                        if data.get('batch_job_name') == job_name:
                            data.update({'status': 'failed_job_not_found', 'error': '作业在API侧丢失'})
                    save_state(state)
                    finished_jobs.add(job_name)
                except Exception as e:
                    print(f"  - ❌ 监控作业 '{job_name}' 时发生错误: {e}")
                    # 避免无限循环，暂时不从此轮监控中移除，下次再试

            active_job_names -= finished_jobs
            if active_job_names:
                print(f"  - 仍有 {len(active_job_names)} 个作业在运行中，将在 {sleep_interval}s后再次检查...")

    # 6. 生成最终报告
    print("\n Fase 5: 所有作业处理完毕，生成报告...")
    generate_final_report(state)


if __name__ == "__main__":
    main()