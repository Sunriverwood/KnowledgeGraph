import os
from google import genai
from google.api_core import exceptions
from datetime import datetime, timezone

# ================================
# 配置区
# ================================
# 配置代理 (如果需要)
os.environ["http_proxy"] = "http://127.0.0.1:7890"
os.environ["https_proxy"] = "http://127.0.0.1:7890"


# ================================
# 文件管理功能 (源自 cloud_file.py)
# ================================
def manage_uploaded_files(client):
    """
    列出所有通过 File API 上传的文件，并提供全部删除的选项。
    """
    print("\n" + "=" * 50)
    print("📁 文件管理模块")
    print("=" * 50)
    print("🔍 正在获取已上传的文件列表...")

    try:
        files = list(client.files.list())
        if not files:
            print("✅ 文件列表为空，无需任何操作。")
            return

        print(f"\n📄 找到了 {len(files)} 个已上传的文件：")
        for f in files:
            display_name = f.display_name or "未知"
            print(f"  - 显示名称: {display_name:<40} 文件 ID: {f.name}")

        print("\n" + "-" * 50)
        print("⚠️ 警告：此操作将永久删除以上所有文件！")
        confirm = input("您确定要删除所有这些文件吗？请输入 'yes' 以确认: ").lower()

        if confirm == 'yes':
            print("\n🔥 正在删除文件，请稍候...")
            for f in files:
                try:
                    display_name = f.display_name or "未知"
                    client.files.delete(name=f.name)
                    print(f"  - 已删除 {display_name} ({f.name})")
                except Exception as e:
                    print(f"  - 🔥 删除 {display_name} 失败: {e}")
            print("\n✅ 文件删除操作完成！")
        else:
            print("\n🚫 操作已取消。")

    except Exception as e:
        print(f"🔥 获取或删除文件时发生错误: {e}")


# ================================
# 新增：批处理作业管理功能
# ================================
def manage_batch_jobs(client):
    """
    列出并管理正在运行的批处理作业，可以终止运行超时的作业。
    """
    print("\n" + "=" * 50)
    print("⚙️  批处理作业管理模块")
    print("=" * 50)

    try:
        # 获取超时阈值
        while True:
            threshold_input = input("请输入超时阈值（小时），超过此时长的正在运行的作业将被列出 (例如输入 8): ")
            if threshold_input.isdigit() and int(threshold_input) > 0:
                HOURS_THRESHOLD = int(threshold_input)
                break
            else:
                print("❌ 无效输入，请输入一个正整数。")

        print(f"🔍 正在查找运行超过 {HOURS_THRESHOLD} 小时的活动作业...")

        all_jobs = list(client.batches.list())
        now = datetime.now(timezone.utc)

        # 筛选出正在运行且超时的作业
        long_running_jobs = []
        for job in all_jobs:
            if 'RUNNING' in job.state.name or 'PENDING' in job.state.name:
                create_time = job.create_time.astimezone(timezone.utc)
                duration_hours = (now - create_time).total_seconds() / 3600
                if duration_hours > HOURS_THRESHOLD:
                    job.duration_hours = duration_hours  # 动态添加属性以便显示
                    long_running_jobs.append(job)

        if not long_running_jobs:
            print(f"\n✅ 未找到任何运行时间超过 {HOURS_THRESHOLD} 小时的活动作业。")
            return

        print(f"\n" + "-" * 50)
        print(f"🕒 发现 {len(long_running_jobs)} 个超时作业：")
        for i, job in enumerate(long_running_jobs):
            print(f"  {i + 1}. 作业名称: {job.display_name}")
            print(f"     ID: {job.name}")
            print(f"     状态: {job.state.name}")
            print(f"     已运行时长: {job.duration_hours:.2f} 小时")

        print("-" * 50)
        print("⚠️ 警告：此操作将尝试取消并删除以上列出的所有超时作业！")
        confirm = input("您确定要终止所有这些作业吗？请输入 'yes' 以确认: ").lower()

        if confirm == 'yes':
            print("\n🔥 正在终止作业，请稍候...")
            for job in long_running_jobs:
                try:
                    print(f"  - 正在取消作业: {job.display_name}...")
                    client.batches.cancel(name=job.name)  # 优先取消
                    print(f"    - 取消成功。")

                    # 取消后通常需要一点时间才能删除，这里我们直接尝试
                    try:
                        client.batches.delete(name=job.name)  # 然后删除
                        print(f"    - 已从列表中删除。")
                    except exceptions.PermissionDenied as e:
                        print(f"    - 提示：作业已取消，但立即删除失败 (这通常是正常的，稍后会自动清理): {e}")

                except Exception as e:
                    print(f"  - 🔥 终止作业 {job.display_name} 失败: {e}")
            print("\n✅ 作业终止操作完成！")
        else:
            print("\n🚫 操作已取消。")

    except Exception as e:
        print(f"🔥 获取或管理作业时发生错误: {e}")


# ================================
# 主程序入口
# ================================
def main():
    """
    主菜单，让用户选择要管理的项目。
    """
    # 初始化新版 SDK 客户端
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ 错误: 请设置 GEMINI_API_KEY 环境变量")
        return

    try:
        client = genai.Client(api_key=api_key)
        print("✅ Gemini 客户端初始化成功。")
    except Exception as e:
        print(f"❌ Gemini 初始化失败: {e}")
        return

    while True:
        print("\n" + "=" * 50)
        print("🛠️ Gemini 云端资源管理器 🛠️")
        print("=" * 50)
        print("1. 管理已上传的文件 (列出和批量删除)")
        print("2. 管理批处理作业 (查找并终止超时作业)")
        print("3. 退出")
        choice = input("请输入您的选择 (1, 2, 或 3): ")

        if choice == '1':
            manage_uploaded_files(client)
        elif choice == '2':
            manage_batch_jobs(client)
        elif choice == '3':
            print("👋 再见！")
            break
        else:
            print("❌ 无效选择，请输入 1, 2, 或 3。")


if __name__ == "__main__":
    main()