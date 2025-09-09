import os
import google.generativeai as genai

os.environ["http_proxy"] = "http://127.0.0.1:7890"
os.environ["https_proxy"] = "http://127.0.0.1:7890"

def manage_uploaded_files():
    """
    列出所有通过 File API 上传的文件，并提供全部删除的选项。
    """
    # 步骤 1: 配置 API 密钥
    # 确保您的 GEMINI_API_KEY 已经设置在环境变量中
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ 错误: 请设置 GEMINI_API_KEY 环境变量。")
        return
    genai.configure(api_key=api_key)

    print("🔍 正在获取已上传的文件列表...")

    # 步骤 2: 获取并列出所有文件
    try:
        files = list(genai.list_files())
        if not files:
            print("✅ 文件列表为空，无需任何操作。")
            return

        print(f"\n📄 找到了 {len(files)} 个已上传的文件：")
        print("-" * 40)
        for f in files:
            # display_name 是您上传时指定的可读名称，name 是文件的唯一ID
            print(f"  - 显示名称: {f.display_name}")
            print(f"    文件 ID: {f.name}\n")
        print("-" * 40)

        # 步骤 3: 征求用户确认
        print("\n⚠️ 警告：此操作将永久删除以上所有文件！")
        confirm = input("您确定要删除所有这些文件吗？请输入 'yes' 以确认: ")

        # 步骤 4: 如果确认，则执行删除
        if confirm.lower() == 'yes':
            print("\n🔥 正在删除文件，请稍候...")
            deleted_count = 0
            for f in files:
                try:
                    print(f"  - 正在删除 {f.display_name} ({f.name})...")
                    genai.delete_file(name=f.name)
                    deleted_count += 1
                except Exception as e:
                    print(f"    🔥 删除失败: {e}")

            print(f"\n✅ 操作完成！成功删除了 {deleted_count} 个文件。")
        else:
            print("\n🚫 操作已取消，没有文件被删除。")

    except Exception as e:
        print(f"🔥 获取文件列表时发生错误: {e}")


if __name__ == "__main__":
    manage_uploaded_files()