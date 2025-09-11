import os
import re
import time
from neo4j import GraphDatabase
from google.genai import Client, errors

# -------------------- 配置 --------------------
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "123456789"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

QUESTION = "Inconel 718 的主要应用场景是什么？"

# 配置代理 (如果需要)
os.environ["http_proxy"] = "http://127.0.0.1:7890"
os.environ["https_proxy"] = "http://127.0.0.1:7890"


# 初始化 Gemini 客户端（新版 SDK）
client = Client(api_key=GEMINI_API_KEY)

# -------------------- Step 0: 初始化 Neo4j --------------------
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# -------------------- Step 1: 提取智能子图 --------------------
def build_smart_subgraph(tx, question, max_level=2):
    query = """
    WITH split($question, ' ') AS words
    UNWIND words AS w
    MATCH (e)
    WHERE toLower(e.name) CONTAINS toLower(w)
    WITH collect(DISTINCT e) AS entities
    CALL apoc.path.subgraphAll(entities, {maxLevel:$max_level}) YIELD nodes, relationships
    RETURN nodes, relationships
    """
    result = tx.run(query, question=question, max_level=max_level).single()
    nodes = result["nodes"]
    relationships = result["relationships"]

    context_lines = []
    for r in relationships:
        start = r.start_node["name"]
        end = r.end_node["name"]
        rel_type = r.type
        context_lines.append(f"({start})-[:{rel_type}]->({end})")
    context_text = "\n".join(context_lines) if context_lines else "数据库中没有找到相关信息。"
    return context_text, nodes, relationships

with driver.session() as session:
    context_text, nodes, relationships = session.execute_read(build_smart_subgraph, QUESTION)

print("🟢 Subgraph Context:\n", context_text)

# -------------------- Step 2: 生成 Cypher 查询 (新版 Gemini SDK) --------------------
def generate_cypher(question: str, context: str) -> str:
    # --- 1. Updated Prompt ---
    # Made the instruction to avoid formatting even more explicit.
    prompt = f"""
    You are an expert Neo4j Cypher query generator.
    Based on the following subgraph context, generate a single, executable Cypher query.

    IMPORTANT:
    - ONLY return the raw Cypher query text.
    - DO NOT include any explanations.
    - DO NOT wrap the query in Markdown code blocks like ```cypher or ```.

    Question: "{question}"
    Subgraph Context:
    {context}

    Cypher Query:
    """

    # --- 2. Server error retry logic (remains the same) ---
    retries = 2
    delay = 5
    for i in range(retries):
        try:
            response = client.models.generate_content(
                model="models/gemini-2.5-pro",
                contents=prompt,
                config={
                    "temperature": 0,
                    "max_output_tokens": 10000,
                    "candidate_count": 1
                }
            )

            # --- 3. New Response Cleaning Logic ---
            # This is the most critical fix.
            raw_text = response.text

            # Use regex to find and extract content within ```cypher ... ```
            match = re.search(r"```(?:cypher)?\s*(.*?)\s*```", raw_text, re.DOTALL)
            if match:
                cleaned_query = match.group(1).strip()
            else:
                # If no markdown block is found, just strip whitespace as a fallback.
                cleaned_query = raw_text.strip()

            print(f"✅ Cleaned Cypher Query:\n{cleaned_query}")
            return cleaned_query

        except google.genai.errors.ServerError as e:
            print(f"Attempt {i + 1} failed with a server error: {e}")
            if i < retries - 1:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2
            else:
                print("All retry attempts failed.")
                return "MATCH (n) RETURN 'ERROR: Query generation failed due to server overload' LIMIT 1"

        except AttributeError:
            print("❌ 生成 Cypher 查询失败：模型返回内容为空 (可能被安全过滤器阻止)。")
            print(response)
            return "MATCH (n) RETURN 'ERROR: Query generation failed by safety filter' LIMIT 1"

    return "MATCH (n) RETURN 'ERROR: Query generation failed unexpectedly' LIMIT 1"
# -------------------- Step 3: 执行查询 --------------------
def run_cypher(tx, query):
    result = tx.run(query)
    rows = []
    for record in result:
        rows.append(", ".join([str(v) for v in record.values()]))
    return "\n".join(rows) if rows else "数据库中没有找到相关信息。"

cypher_query = generate_cypher(QUESTION, context_text)

with driver.session() as session:
    query_result = session.execute_read(run_cypher, cypher_query)

print("🟢 Query Result:\n", query_result)

# -------------------- Step 4: 整理答案 (新版 Gemini SDK) --------------------
def summarize_answer(context: str, question: str) -> str:
    prompt = f"""
    根据下面 Neo4j 查询结果生成简洁的自然语言答案。
    问题: "{question}"
    查询结果:
    {context}
    答案:
    """
    # 使用新的 generate_content 方法
    response = client.models.generate_content(
        model="models/gemini-2.5-pro", # 实际模型名称可能为 gemini-2.5-pro
        contents=prompt,
        config={
            "temperature": 0,
            "max_output_tokens": 10000,
            "candidate_count": 1
        }
    )
    # 增加对响应的稳健性检查
    try:
        final_answer = response.text.strip()
        return final_answer
    except AttributeError:
        print("❌ 总结答案失败：模型返回内容为空。")
        print("   这很可能是因为内容触发了安全过滤器。")
        print("   以下是完整的响应对象以供调试：")
        print(response)
        return "未能生成最终答案，响应内容为空。"

# -------------------- Step 5: Neo4j 可视化子图 (临时标签) --------------------
def create_visual_subgraph(tx, nodes, relationships):
    for n in nodes:
        name = n["name"]
        tx.run("MERGE (:`_RAG_TMP` {name: $name})", name=name)
    for r in relationships:
        start = r.start_node["name"]
        end = r.end_node["name"]
        rel_type = r.type
        tx.run("""
            MATCH (a:`_RAG_TMP` {name:$start}), (b:`_RAG_TMP` {name:$end})
            MERGE (a)-[rel:`%s`]->(b)
        """ % rel_type, start=start, end=end)

def delete_visual_subgraph(tx):
    tx.run("MATCH (n:`_RAG_TMP`) DETACH DELETE n")

# 创建可视化子图
with driver.session() as session:
    session.execute_write(create_visual_subgraph, nodes, relationships)
print("🟢 临时子图已创建，可在 Neo4j 浏览器查看。")

# 删除临时子图
with driver.session() as session:
    session.execute_write(delete_visual_subgraph)
print("🟢 临时子图已删除，数据库恢复整洁。")
