import os
import google.generativeai as genai

# ================================
# 配置代理（默认 clash7890）
# ================================
os.environ["http_proxy"] = "http://127.0.0.1:7890"
os.environ["https_proxy"] = "http://127.0.0.1:7890"

# ================================
# 构造 OCR 规则
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
    pdf_folder = "data"  # 指定PDF文件夹
    pdf_files = [f for f in os.listdir(pdf_folder) if f.lower().endswith(".pdf")]
    output_files = [os.path.splitext(f)[0] + ".txt" for f in pdf_files]
    api_key = os.getenv("GEMINI_API_KEY")

    # 初始化 Gemini
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-pro")

    # 构造规则
    instructions = build_instructions(no_math=True, no_table=True, no_images=True)

    for pdf_file, output_file in zip(pdf_files, output_files):
        print("📄 正在上传 PDF:", pdf_file)
        uploaded_file = genai.upload_file(os.path.join(pdf_folder, pdf_file))

        print("⚙️ 开始 OCR 处理...")
        response = model.generate_content(
            [instructions, uploaded_file],
            request_options={"timeout": 2000}
        )

        # 保存结果
        output_path = os.path.join("output", output_file)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(response.text)

        print("✅ OCR 完成，结果已保存到:", output_file)

if __name__ == "__main__":
    main()
