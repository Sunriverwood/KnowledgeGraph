import os
import shutil
import json

# 需要处理的 PDF 文件名列表
files_to_move = [
    '耐热钢和高温合金.pdf',
    '高温合金金相图谱 (《高温合金金相图谱》编写组编著) (Z-Library).pdf',
    'ASM HandBook Volume 21 - Composites.pdf',
    'Chapter-6---Superplasticity_2015_Fundamentals-of-Creep-in-Metals-and-Alloys.pdf',
    'High temperature strain of metals and alloys physical fundamentals (Valim Levitin) (Z-Library).pdf',
    'Superalloys  Production, Properties and Applications (Jeremy E. Watson) (Z-Library).pdf',
    '高温合金痕量元素分析.dec.pdf',
    '高温合金译文集.pdf'
]

src_dir = 'data'
dst_dir = 'files_disconnected'
json_path = 'processing_state.json'

# 1. 移动文件
for filename in files_to_move:
    src = os.path.join(src_dir, filename)
    dst = os.path.join(dst_dir, filename)
    if os.path.exists(src):
        shutil.move(src, dst)
        print(f'已移动: {filename}')
    else:
        print(f'未找到: {filename}')

# 2. 删除 JSON 片段
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

for filename in files_to_move:
    if filename in data:
        del data[filename]
        print(f'已删除 JSON 片段: {filename}')

with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('操作完成。')
