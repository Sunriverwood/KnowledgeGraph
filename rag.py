import os
import re
import time
from neo4j import GraphDatabase
from google.genai import Client, errors

# -------------------- 1. 配置与初始化 --------------------
# Neo4j 数据库连接配置
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "123456789"

# 从环境变量获取 Gemini API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("错误: 请设置 GEMINI_API_KEY 环境变量。")

# 配置代理 (如果您的网络环境需要)
os.environ["http_proxy"] = "http://127.0.0.1:7890"
os.environ["https_proxy"] = "http://127.0.0.1:7890"

# 初始化 Gemini 客户端
client = Client(api_key=GEMINI_API_KEY)

# 初始化 Neo4j 驱动
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# 定义要提出的问题
QUESTION = "什么是堆垛层错（Stacking Fault）？请说明内禀层错和外禀层错的区别"


# -------------------- 2. 定义核心功能函数 --------------------

def generate_cypher_query(question: str) -> str:
    """使用Prompt控制大模型严格生成能用于neo4j数据库查询的cypher语句。"""
    print("\nStep 1: 正在生成 Cypher 查询语句...")
    with open("Prompt：为高温合金知识图谱生成灵活的Cypher查询.md", "r", encoding="utf-8") as f:
        prompt = f.read()
    prompt = prompt.replace("{question}", question)
    retries = 2
    delay = 5
    for i in range(retries):
        try:
            response = client.models.generate_content(
                model="models/gemini-2.5-pro",
                contents=prompt,
                config={"temperature": 0}
            )
            raw_text = response.text
            # 清理模型可能返回的Markdown格式
            match = re.search(r"```(?:cypher)?\s*(.*?)\s*```", raw_text, re.DOTALL)
            cleaned_query = match.group(1).strip() if match else raw_text.strip()

            print("✅ Cypher 查询生成成功。")
            return cleaned_query
        except errors.ServerError as e:
            print(f"第 {i + 1} 次尝试失败，服务器错误: {e}")
            if i < retries - 1:
                print(f"将在 {delay} 秒后重试...")
                time.sleep(delay)
                delay *= 2
            else:
                print("所有重试均失败。")
                return "MATCH (n) RETURN 'ERROR: Query generation failed due to server overload' LIMIT 1"
        except (AttributeError, ValueError):
            print("❌ 生成 Cypher 查询失败：模型返回内容为空或格式不正确。")
            print(f"   原始返回内容: {response.text if 'response' in locals() else 'N/A'}")
            return "MATCH (n) RETURN 'ERROR: Query generation failed by safety filter or empty response' LIMIT 1"
    return "MATCH (n) RETURN 'ERROR: Query generation failed unexpectedly' LIMIT 1"


def run_cypher_query(tx, query: str) -> str:
    """在Neo4j数据库中执行Cypher查询并返回格式化的结果。"""
    result = tx.run(query)
    rows = [", ".join(map(str, record.values())) for record in result]
    return "\n".join(rows) if rows else "查询成功，但数据库未返回任何结果。"


def generate_final_answer(question: str, query_result: str) -> str:
    """使用Prompt控制模型基于查询结果生成最终回答。"""
    print("\nStep 3: 正在根据查询结果生成最终回答...")
    prompt = f"""
    请根据下面提供的 Neo4j 查询结果，为原始问题生成一个简洁、流畅的自然语言回答。

    原始问题: "{question}"

    查询结果:
    {query_result}

    最终回答:
    """
    try:
        response = client.models.generate_content(
            model="models/gemini-2.5-pro",
            contents=prompt,
            config={"temperature": 0.1}  # slight temperature for more natural language
        )
        final_answer = response.text.strip()
        print("✅ 最终回答生成成功。")
        return final_answer
    except (errors.ServerError, AttributeError, ValueError) as e:
        print(f"❌ 生成最终回答失败: {e}")
        return "未能根据查询结果生成最终答案。"


# -------------------- 3. 执行完整的 RAG 流程 --------------------
if __name__ == "__main__":
    with driver.session() as session:
        # Step 1: 生成 Cypher 查询
        cypher_query = generate_cypher_query(QUESTION)
        print("-" * 50)
        print("生成的 Cypher 查询:\n", cypher_query)
        print("-" * 50)

        # Step 2: 执行查询
        print("\nStep 2: 正在 Neo4j 数据库中执行查询...")
        query_result = session.execute_read(run_cypher_query, cypher_query)
        print("✅ 查询执行完成。")
        print("-" * 50)
        print("数据库查询结果:\n", query_result)
        print("-" * 50)

        # Step 3: 生成最终回答
        final_answer = generate_final_answer(QUESTION, query_result)
        print("=" * 50)
        print("✨ 最终答案:\n", final_answer)
        print("=" * 50)

    driver.close()