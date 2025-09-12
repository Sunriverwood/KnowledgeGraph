批量处理，单个文件最大2G
单个文件最大页数1000
api在系统环境变量里设置
记得用cloud_manager删除上传的文件
启动neo4j，首先进入neo4j安装目录的bin目录，然后cmd运行./neo4j console，浏览器访问localhost:7474


工作流程：
1. data目录下放入待处理的pdf文件
2. 运行gemini_json_batch.py，生成json文件，放在data/json目录下
3. 运行merge_json.py，生成neo4j导入文件merged_knowledge_graph.json，复制到neo4j的import目录下
4. 浏览器里按照neo4j的导入方法导入数据
5. 运行rag.py，完成问答
6. 浏览器里根据rag生成的查询语句查询知识图谱，进行可视化