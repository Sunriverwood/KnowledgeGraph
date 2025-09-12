import os
import shutil


def flatten_folder(parent_folder):
    """
    展开一个文件夹，将所有子文件夹中的文件移动到父文件夹，并删除空的子文件夹。

    Args:
        parent_folder (str): 要处理的父文件夹的路径。
    """
    # 1. 检查路径是否存在且是一个文件夹
    if not os.path.isdir(parent_folder):
        print(f"错误：提供的路径 '{parent_folder}' 不是一个有效的文件夹。")
        return

    print(f"开始处理文件夹: {parent_folder}\n")

    # --- 步骤 1: 移动所有子文件夹中的文件到父文件夹 ---
    # os.walk 会遍历指定目录下的所有子目录和文件
    for dirpath, dirnames, filenames in os.walk(parent_folder):
        # 我们只关心子文件夹中的文件，所以跳过父文件夹本身
        if dirpath == parent_folder:
            continue

        for filename in filenames:
            # 构建文件的完整原始路径
            source_path = os.path.join(dirpath, filename)

            # 构建文件移动到父文件夹后的目标路径
            dest_path = os.path.join(parent_folder, filename)

            # 检查文件名冲突：如果父文件夹中已存在同名文件，则重命名
            counter = 1
            # 分离文件名和扩展名，方便重命名
            file_base, file_ext = os.path.splitext(filename)
            while os.path.exists(dest_path):
                # 创建新的文件名，例如：report_1.txt
                new_filename = f"{file_base}_{counter}{file_ext}"
                dest_path = os.path.join(parent_folder, new_filename)
                counter += 1

            # 移动文件
            try:
                shutil.move(source_path, dest_path)
                if dest_path != os.path.join(parent_folder, filename):
                    print(f"移动并重命名: {source_path} -> {dest_path}")
                else:
                    print(f"移动文件: {source_path} -> {dest_path}")
            except Exception as e:
                print(f"移动文件 '{source_path}' 时出错: {e}")

    print("\n--- 所有文件移动完成 ---\n")

    # --- 步骤 2: 删除所有空的子文件夹 ---
    # 我们使用 topdown=False 参数，这样 os.walk 会从最深的子文件夹开始向上遍历
    # 这确保了我们在删除父目录之前，它的子目录已经被处理（或删除）
    for dirpath, dirnames, filenames in os.walk(parent_folder, topdown=False):
        # 再次跳过父文件夹本身
        if dirpath == parent_folder:
            continue

        # 检查文件夹是否为空
        if not os.listdir(dirpath):
            try:
                os.rmdir(dirpath)
                print(f"删除空文件夹: {dirpath}")
            except OSError as e:
                print(f"删除文件夹 '{dirpath}' 时出错: {e}")
        else:
            print(f"文件夹不为空，跳过: {dirpath}")

    print("\n--- 任务完成！---")


# --- 如何使用 ---
if __name__ == "__main__":
    # 在这里修改为你需要处理的文件夹路径
    # 重要提示：请使用绝对路径或相对于脚本位置的正确相对路径。
    # 示例 (Windows): target_folder = r"C:\Users\YourUser\Documents\MyFolder"
    # 示例 (macOS/Linux): target_folder = "/home/youruser/documents/my_folder"

    target_folder = "files_disconnected"  # <--- 在这里替换成你的文件夹路径

    # 在运行前，确保路径是正确的，否则脚本会提示错误
    if target_folder == "你的文件夹路径":
        print("请先修改脚本中的 'target_folder' 变量为你需要处理的文件夹路径！")
    else:
        # 运行主函数
        flatten_folder(target_folder)