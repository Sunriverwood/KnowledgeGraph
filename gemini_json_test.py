import os
import json
import google.generativeai as genai

# ================================
# 配置代理（默认 clash7890）
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
            return f.read()
    except FileNotFoundError:
        print(f"❌ 错误：指令文件 '{filepath}' 未找到。请确保该文件与脚本在同一目录下。")
        return None


# ================================
# 主程序
# ================================
def main():
    """
    主执行函数，用于处理PDF文件并生成知识图谱JSON。
    """
    pdf_folder = "data_test"  # 存放待处理PDF的文件夹
    output_folder = "json"  # 存放生成的JSON文件的文件夹

    # 检查输入输出文件夹是否存在
    if not os.path.exists(pdf_folder):
        print(f"📁 正在创建 '{pdf_folder}' 文件夹，请将您的PDF文件放入其中。")
        os.makedirs(pdf_folder)
        return

    os.makedirs(output_folder, exist_ok=True)

    # 从环境变量获取 API 密钥
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ 错误: 请先设置您的 GEMINI_API_KEY 环境变量。")
        return

    # 初始化 Gemini
    try:
        genai.configure(api_key=api_key)
        # 使用支持高级指令理解和多模态分析的模型
        model = genai.GenerativeModel("gemini-2.5-pro")
        print("✅ Gemini 客户端初始化成功 (gemini-2.5-pro)。")
    except Exception as e:
        print(f"❌ Gemini 初始化失败: {e}")
        return

    # 加载核心指令
    instructions = load_graph_instructions()
    if not instructions:
        return

    # 查找 'data' 文件夹中的所有 PDF 文件
    pdf_files = [f for f in os.listdir(pdf_folder) if f.lower().endswith(".pdf")]

    if not pdf_files:
        print(f"⚠️ 在 '{pdf_folder}' 文件夹中未找到任何 PDF 文件。")
        return

    print(f"\n🚀 发现 {len(pdf_files)} 个 PDF 文件，准备开始处理...")

    for pdf_file in pdf_files:
        pdf_path = os.path.join(pdf_folder, pdf_file)
        # 定义输出JSON文件的路径
        json_filename = os.path.splitext(pdf_file)[0] + ".json"
        json_path = os.path.join(output_folder, json_filename)

        print("-" * 50)
        try:
            # 步骤 1: 上传PDF文件
            print("📄 正在上传 PDF:", pdf_file)
            uploaded_file = genai.upload_file(pdf_path)

            # 步骤 2: 调用模型生成内容
            print("  开始PDF转化为JSON处理...")
            response = model.generate_content(
                [instructions, uploaded_file],
                request_options={"timeout": 2000}
            )

            # 步骤 3: 解析并保存结果
            print("  正在解析和保存结果...")
            cleaned_json = response.text.strip().replace("```json", "").replace("```", "").strip()

            # 验证JSON格式是否正确
            try:
                json_data = json.loads(cleaned_json)
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(json_data, f, ensure_ascii=False, indent=2)
                print(f"  - ✅ 成功！知识图谱已保存到: {json_path}")
            except json.JSONDecodeError:
                print(f"  - ❌ 错误：模型未能返回有效的JSON。将原始输出保存为txt文件以供调试。")
                error_path = os.path.splitext(json_path)[0] + "_error.txt"
                with open(error_path, "w", encoding="utf-8") as f:
                    f.write(response.text)
                print(f"  - 原始输出已保存至: {error_path}")

        except Exception as e:
            print(f"  - ❌ 处理文件 {pdf_file} 时发生意外错误: {e}")
        finally:
            # 建议：可以在此处添加删除已上传文件的逻辑，以管理您的存储空间
            # genai.delete_file(name=uploaded_file.name)
            # print(f"  - 已清理上传的文件: {uploaded_file.name}")
            pass

    print("-" * 50)
    print("✅ 所有任务处理完毕。")


if __name__ == "__main__":
    main()