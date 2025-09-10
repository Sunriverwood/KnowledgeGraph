import os
import json
import time
from google import genai
from google.genai import types

# ================================
# 配置代理（如果需要，请取消注释并设置）
# ================================
os.environ["http_proxy"] = "http://127.0.0.1:7890"
os.environ["https_proxy"] = "http://127.0.0.1:7890"

# ================================
# 从 .md 文件加载知识图谱构建指令
# ================================
def load_graph_instructions(filepath="任务：根据混合Schema从PDF构建可直接导入的知识图谱.md"):
    """
    从指定的 Markdown 文件中读取并返回其内容作为指令。
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            return content
    except FileNotFoundError:
        print(f"❌ 错误：指令文件 '{filepath}' 未找到。请确保该文件与脚本在同一目录下。")
        return None

# ================================
# 主程序
# ================================
def main():
    """
    主执行函数，用于批量处理PDF文件并生成知识图谱JSON。
    """
    pdf_folder = "data"
    output_folder = "json"
    batch_requests_file = "batch_kg_requests.jsonl"  # 为任务指定新请求文件名

    # 检查输入文件夹
    if not os.path.exists(pdf_folder):
        os.makedirs(pdf_folder)
        print(f"📁 已创建 '{pdf_folder}' 文件夹，请将您的PDF文件放入其中后重新运行。")
        return
    os.makedirs(output_folder, exist_ok=True)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("请设置 GEMINI_API_KEY 环境变量")

    # 1. 初始化新版 SDK 客户端
    client = genai.Client(api_key=api_key)
    print("✅ Gemini 客户端初始化完成。")

    # 加载核心指令
    instructions = load_graph_instructions()
    if not instructions:
        return

    pdf_files = [f for f in os.listdir(pdf_folder) if f.lower().endswith(".pdf")]
    if not pdf_files:
        print(f"⚠️ 在 '{pdf_folder}' 文件夹中未找到任何 PDF 文件。")
        return

    # 2. 上传所有 PDF 文件到 File API
    uploaded_files = {}
    print("\n📄 开始上传 PDF 文件...")
    for pdf_file in pdf_files:
        pdf_path = os.path.join(pdf_folder, pdf_file)
        print(f"  - 正在上传: {pdf_file}")
        try:
            # 增加重试逻辑
            for attempt in range(3):
                try:
                    response = client.files.upload(file=pdf_path)
                    uploaded_files[pdf_file] = response
                    print(f"  - 上传成功: {response.name}")
                    break
                except Exception as e:
                    print(f"  - 上传尝试 {attempt + 1}/3 失败: {e}")
                    if attempt == 2:
                        raise
                    time.sleep(5)
        except Exception as e:
            print(f"  - ❌ 上传 {pdf_file} 彻底失败，跳过此文件。")
            continue
    print("✅ 所有 PDF 文件上传完成。")

    if not uploaded_files:
        print("❌ 未成功上传任何文件，程序终止。")
        return

    # 3. 构造批处理请求的 JSONL 文件
    print(f"\n📝 正在构造批处理请求文件 '{batch_requests_file}'...")
    with open(batch_requests_file, "w", encoding="utf-8") as f:
        for pdf_file, uploaded_file in uploaded_files.items():
            # 构造每个文件的 GenerateContentRequest 对象
            request = {
                "key": pdf_file,  # 使用原始文件名作为唯一键
                "request": {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {"text": instructions},
                                {"file_data": {"mime_type": "application/pdf", "file_uri": uploaded_file.uri}}
                            ]
                        }
                    ],
                    "generationConfig": {
                        "response_mime_type": "application/json"
                    }
                }
            }
            f.write(json.dumps(request) + "\n")
    print(f"✅ 批处理请求文件 '{batch_requests_file}' 创建成功。")

    # 4. 上传 JSONL 文件并创建批处理作业
    print("\n📤 正在上传批处理请求文件...")
    batch_input_file = client.files.upload(
        file=batch_requests_file,
        config=types.UploadFileConfig(display_name='batch_kg_requests', mime_type='jsonl')
    )
    print(f"  - 上传成功: {batch_input_file.name}")

    print("⚙️ 正在创建批处理作业...")
    batch_job = client.batches.create(
        model="models/gemini-2.5-pro",
        src=batch_input_file.name,
        config={'display_name': "batch-kg-job"}
    )
    print(f"✅ 批处理作业已创建: {batch_job.name}")

    # 5. 轮询作业状态
    print("\n⏳ 正在等待批处理作业完成，这可能需要较长时间...")
    while batch_job.state.name not in ('JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED', 'JOB_STATE_EXPIRED',
                                       'JOB_STATE_CANCELLED'):
        print(f"  - 当前状态: {batch_job.state.name} ({time.strftime('%Y-%m-%d %H:%M:%S')})")
        time.sleep(60)  # 每 60 秒检查一次状态
        batch_job = client.batches.get(name=batch_job.name)

    print(f"🎉 作业处理完成，最终状态: {batch_job.state.name}")

    # 6. 处理并保存结果
    if batch_job.state.name == 'JOB_STATE_SUCCEEDED':
        if batch_job.dest and batch_job.dest.file_name:
            result_file_name = batch_job.dest.file_name
            print(f"\n📥 正在下载结果文件: {result_file_name}")
            file_content = client.files.download(file=result_file_name).decode('utf-8')

            # 解析结果并保存到对应的 json 文件
            for line in file_content.strip().split('\n'):
                result = json.loads(line)
                original_pdf = result.get("key")
                output_filename = os.path.splitext(original_pdf)[0] + ".json"
                output_path = os.path.join(output_folder, output_filename)

                if original_pdf and result.get("response"):
                    try:
                        # 因为我们指定了 response_mime_type 为 json，所以可以直接访问解析后的内容
                        # 注意：这里的路径可能因SDK版本而异，根据API文档，内容在 part 中
                        json_output = result["response"]["candidates"][0]["content"]["parts"][0]["text"]

                        # 再次解析模型生成的JSON字符串
                        kg_data = json.loads(json_output)

                        with open(output_path, "w", encoding="utf-8") as f:
                            json.dump(kg_data, f, ensure_ascii=False, indent=2)
                        print(f"  - ✅ 结果已保存到: {output_path}")

                    except (KeyError, IndexError, json.JSONDecodeError) as e:
                        print(f"  - ⚠️ 解析 '{original_pdf}' 的结果失败: {e}")
                        # 将原始响应保存为txt文件以供调试
                        error_path = os.path.splitext(output_path)[0] + "_error.txt"
                        with open(error_path, "w", encoding="utf-8") as f:
                            f.write(json.dumps(result.get("response"), indent=2))
                        print(f"  - 原始响应已保存至: {error_path}")

                elif result.get("error"):
                    print(f"  - ❌ 处理 '{original_pdf}' 时发生错误: {result['error']['message']}")
        else:
            print("❌ 作业成功，但未找到输出文件。")
    else:
        print(f"‼️ 作业失败或已过期。错误详情: {batch_job.error}")


if __name__ == "__main__":
    main()