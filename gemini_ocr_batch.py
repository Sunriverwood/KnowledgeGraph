import os
import json
import time
from google import genai
from google.genai import types

# ================================
# 配置代理（如果需要）
# ================================
os.environ["http_proxy"] = "http://127.0.0.1:7890"
os.environ["https_proxy"] = "http://127.0.0.1:7890"

# ================================
# 构造 OCR 规则 (与您原有的函数相同)
# ================================
def build_instructions(no_math=False, no_table=False, no_images=False):
    rules = ["你是一个OCR识别助手，请严格遵循以下要求："]
    if no_images:
        rules.append("1. 只识别文字内容，忽略图片的说明文字，不输出图片内容。")
    else:
        rules.append("1. 保留并识别图片说明文字。")
    if no_table:
        rules.append("2. 忽略表格内容，忽略表格的说明文字。")
    else:
        rules.append("2. 表格请转为Markdown格式，保证列对齐。")
    if no_math:
        rules.append("3. 忽略数学公式内容。")
    else:
        rules.append("3. 数学公式保持LaTeX格式，用 $...$ 或 \\[...\\] 包裹。")
    rules.append("4. 输出纯文本，不要添加额外解释。")
    return "\n".join(rules)


# ================================
# 主程序
# ================================
def main():
    pdf_folder = "data"
    output_folder = "output"
    batch_requests_file = "batch_ocr_requests.jsonl"

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("请设置 GEMINI_API_KEY 环境变量")

    # 1. 初始化新版 SDK 客户端
    client = genai.Client(api_key=api_key)
    print("✅ Gemini 客户端初始化完成。")

    pdf_files = [f for f in os.listdir(pdf_folder) if f.lower().endswith(".pdf")]
    if not pdf_files:
        print("⚠️ 在 'data' 文件夹中未找到任何 PDF 文件。")
        return

    # 2. 上传所有 PDF 文件到 File API
    uploaded_files = {}
    print("📄 开始上传 PDF 文件...")
    for pdf_file in pdf_files:
        pdf_path = os.path.join(pdf_folder, pdf_file)
        print(f"  - 正在上传: {pdf_file}")
        response = client.files.upload(file=pdf_path)
        uploaded_files[pdf_file] = response
        print(f"  - 上传成功: {response.name}")
    print("✅ 所有 PDF 文件上传完成。")

    # 3. 构造批处理请求的 JSONL 文件
    instructions = build_instructions(no_math=True, no_table=True, no_images=True)

    with open(batch_requests_file, "w", encoding="utf-8") as f:
        for pdf_file, uploaded_file in uploaded_files.items():
            # 构造每个文件的 GenerateContentRequest 对象
            # 每个请求都包含指令和对已上传文件的引用
            request = {
                "key": pdf_file,
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
                        "response_mime_type": "text/plain"
                    }
                }
            }
            f.write(json.dumps(request) + "\n")
    print(f"✅ 批处理请求文件 '{batch_requests_file}' 创建成功。")

    # 4. 上传 JSONL 文件并创建批处理作业
    print("📤 正在上传批处理请求文件...")
    batch_input_file = client.files.upload(
        file=batch_requests_file,
        config=types.UploadFileConfig(display_name='batch_ocr_requests',mime_type='jsonl')
    )
    print(f"  - 上传成功: {batch_input_file.name}")

    print("⚙️ 正在创建批处理作业...")
    batch_job = client.batches.create(
        model="models/gemini-2.5-pro",  # 请确保模型支持批处理
        src=batch_input_file.name,
        config={'display_name': "batch-ocr-job"}
    )
    print(f"✅ 批处理作业已创建: {batch_job.name}")

    # 5. 轮询作业状态
    print("⏳ 正在等待批处理作业完成，这将需要一些时间...")
    while batch_job.state.name not in ('JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED', 'JOB_STATE_EXPIRED'):
        print(f"  - 当前状态: {batch_job.state.name} ({time.strftime('%Y-%m-%d %H:%M:%S')})")
        time.sleep(60)  # 每 60 秒检查一次状态
        batch_job = client.batches.get(name=batch_job.name)

    print(f"🎉 作业处理完成，最终状态: {batch_job.state.name}")

    # 6. 处理并保存结果
    if batch_job.state.name == 'JOB_STATE_SUCCEEDED':
        if batch_job.dest and batch_job.dest.file_name:
            result_file_name = batch_job.dest.file_name
            print(f"📥 正在下载结果文件: {result_file_name}")
            file_content = client.files.download(file=result_file_name).decode('utf-8')

            # 解析结果并保存到对应的 txt 文件
            os.makedirs(output_folder, exist_ok=True)
            for line in file_content.strip().split('\n'):
                result = json.loads(line)
                original_pdf = result.get("key")

                if original_pdf and result.get("response"):
                    output_filename = os.path.splitext(original_pdf)[0] + ".txt"
                    output_path = os.path.join(output_folder, output_filename)

                    try:
                        # 提取文本内容
                        ocr_text = result["response"]["candidates"][0]["content"]["parts"][0]["text"]
                        with open(output_path, "w", encoding="utf-8") as f:
                            f.write(ocr_text)
                        print(f"  - ✅ 结果已保存到: {output_path}")
                    except (KeyError, IndexError) as e:
                        print(f"  - ⚠️ 解析 '{original_pdf}' 的结果失败: {e}")

                elif result.get("error"):
                    print(f"  - ❌ 处理 '{original_pdf}' 时发生错误: {result['error']['message']}")

        else:
            print("❌ 作业成功，但未找到输出文件。")
    else:
        print(f"‼️ 作业失败或已过期。错误详情: {batch_job.error}")


if __name__ == "__main__":
    main()