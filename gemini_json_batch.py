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
BATCH_SIZE = 1
# 单个批次的最长轮询时间
BATCH_POLLING_TIMEOUT_SECONDS = 0.2 * 60 * 60
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
        json.dump(state, f, indent=2)


# ================================
# 指令加载函数 (无变化)
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
    # ... (此函数逻辑与上一版基本相同，但现在接收并修改 state 对象)
    # ... (为简洁起见，此处省略，请参考上一版代码)
    pass  # 实际代码请参考上一版 `process_job_results`


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

    # 2. 文件发现与状态同步 (实现断点续传的第一步)
    print(" Fase 1: 文件发现与状态同步...")
    current_pdfs = {f for f in os.listdir(pdf_folder) if f.lower().endswith(".pdf")}
    for pdf_file in current_pdfs:
        if pdf_file not in state:
            state[pdf_file] = {'status': 'pending_upload'}
    save_state(state)

    # 3. 上传待上传的文件 (跳过已上传的)
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
                    'uploaded_file_uri': response.uri
                })
            except Exception as e:
                state[pdf_file].update({'status': 'failed_upload', 'error': str(e)})
            finally:
                save_state(state)  # 每次操作后都保存状态
    else:
        print("  - 无新文件需要上传。")

    # 4. 创建批处理作业 (仅为未处理的文件)
    print("\n Fase 3: 为待处理文件创建批处理作业...")
    requests_to_process = []
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

    if requests_to_process:
        request_chunks = [requests_to_process[i:i + BATCH_SIZE] for i in range(0, len(requests_to_process), BATCH_SIZE)]
        for i, chunk in enumerate(request_chunks):
            job_display_name = f"KG-Batch-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{i + 1}"
            # ... (创建批处理作业的逻辑，同上一版 `create_and_run_batch`)
            # ... 创建后，更新 state 中对应文件的 status 为 'processing' 和 'batch_job_name'
            save_state(state)
    else:
        print("  - 无待处理文件需要创建新作业。")

    # 5. 监控所有“处理中”的作业 (实现超时控制)
    print("\n Fase 4: 监控所有处理中的作业...")
    active_job_names = {data['batch_job_name'] for data in state.values() if data.get('status') == 'processing'}

    start_times = {name: datetime.now() for name in active_job_names}

    while active_job_names:
        time.sleep(60)
        finished_jobs = set()
        for job_name in list(active_job_names):
            # 检查超时
            elapsed = datetime.now() - start_times[job_name]
            if elapsed.total_seconds() > BATCH_POLLING_TIMEOUT_SECONDS:
                print(f"⏰ 作业 '{job_name}' 超时 (超过8小时)，正在尝试取消...")
                try:
                    client.batches.cancel(name=job_name)
                except exceptions.NotFound:  # 作业可能恰好完成
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
                        # ... 调用 process_job_results 来处理结果并更新 state
                        pass
                    else:
                        # ... 更新 state 中相关文件的 status 为 failed
                        pass
                    save_state(state)
                    finished_jobs.add(job_name)
            except exceptions.NotFound:
                # ... 作业在API侧找不到了，标记为失败
                finished_jobs.add(job_name)

        active_job_names -= finished_jobs
        if active_job_names:
            print(f"  - 仍有 {len(active_job_names)} 个作业在运行中...")

    # 6. 生成最终报告
    print("\n Fase 5: 所有作业处理完毕，生成报告...")
    generate_final_report(state)


if __name__ == "__main__":
    main()