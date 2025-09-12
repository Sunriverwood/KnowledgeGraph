import os
import re

def sanitize_filename(filename):
    """
    删除'Z-Library'和'编著'，删除中文符号，空格换成下划线，保留其他字符。
    """
    name, extension = os.path.splitext(filename)
    # 删除指定字符串
    name = name.replace('Z-Library', '').replace('编著', '')
    # 删除常见中文符号
    name = re.sub(r'[，。！？【】（）《》“”‘’、；：]', '', name)
    # 删除英文小括号
    name = re.sub(r'[()]', '', name)
    # 空格换成下划线
    name = name.replace(' ', '_')
    # 删除开头和结尾的下划线
    name = name.strip('_')
    # 删除指定字段
    name = re.sub(r'\b(ebook|pdf|epub|mobi|azw3|txt|doc|docx|rtf|fb2|lit|chm|djvu|cbr|cbz)\b',
                  '', name, flags=re.IGNORECASE)
    # 删除中文指定字段
    name = re.sub(r'电子书|下载|免费|完整版|高清版|高清|高温合金金相图谱编写组', '', name)
    # 连续下划线换成单个下划线
    name = re.sub(r'__+', '_', name)
    return name + extension

def rename_pdfs_in_folder(folder_path):
    """
    遍历指定文件夹中的所有PDF文件，并根据需要重命名它们。
    """
    # 1. 检查文件夹是否存在，如果不存在则创建
    if not os.path.exists(folder_path):
        print(f"📁 文件夹 '{folder_path}' 不存在，正在创建...")
        os.makedirs(folder_path)
        print("✅ 创建完成。请将您的PDF文件放入该文件夹后重新运行此脚本。")
        return

    print(f"🔍 正在扫描文件夹 '{folder_path}' 中的PDF文件...")

    # 2. 获取所有PDF文件
    try:
        pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".pdf")]
    except FileNotFoundError:
        print(f"❌ 错误：找不到文件夹 '{folder_path}'。")
        return

    if not pdf_files:
        print("✅ 在文件夹中未找到任何PDF文件，无需操作。")
        return

    # 3. 遍历并重命名
    rename_count = 0
    for filename in pdf_files:
        original_path = os.path.join(folder_path, filename)

        # 检查原始文件名是否已经符合规则 (简单检查长度和字符)
        name_part = os.path.splitext(filename)[0]
        if len(name_part) <= 60 and re.match(r'^[a-zA-Z0-9_-]+$', name_part):
            continue  # 文件名已符合规则，跳过

        # 生成新的、符合规范的文件名
        new_filename = sanitize_filename(filename)
        new_path = os.path.join(folder_path, new_filename)

        # 如果新旧文件名相同，则无需重命名
        if new_path == original_path:
            continue

        # 检查新文件名是否存在，如果存在则添加后缀以保证唯一
        counter = 1
        base_name, extension = os.path.splitext(new_filename)
        while os.path.exists(new_path):
            new_filename = f"{base_name}_{counter}{extension}"
            new_path = os.path.join(folder_path, new_filename)
            counter += 1

        # 执行重命名
        try:
            os.rename(original_path, new_path)
            print(f"🔄 重命名: '{filename}' -> '{new_filename}'")
            rename_count += 1
        except OSError as e:
            print(f"❌ 重命名 '{filename}' 时出错: {e}")

    print("\n" + "="*50)
    if rename_count > 0:
        print(f"✅ 操作完成！总共有 {rename_count} 个文件被成功重命名。")
    else:
        print("✅ 所有文件名均已符合要求，未进行任何更改。")
    print("="*50)


if __name__ == "__main__":
    rename_pdfs_in_folder(folder_path="files_oversized")