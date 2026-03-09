import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import google.generativeai as genai
import json
import re

st.set_page_config(page_title="AI Manufacturing Analytics", layout="wide")
st.title("🏭 AI Manufacturing Analytics")

# Gemini setup
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.5-flash")

# -----------------------
# CHAT MEMORY
# -----------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# -----------------------
# LOAD DATA
# -----------------------
@st.cache_data
def load_data():

    conn = sqlite3.connect("manufacturing.db")

    revenue_query = """
    SELECT 
        d.full_date,
        d.year,
        r.region_name,
        p.plant_name,
        s.segment_name,
        pr.product_name,
        c.customer_name,
        i.revenue_amount
    FROM invoice i
    JOIN date_dim d ON i.date_id = d.date_id
    JOIN region r ON i.region_id = r.region_id
    JOIN plant p ON i.plant_id = p.plant_id
    JOIN product pr ON i.product_id = pr.product_id
    JOIN product_subgroup sg ON pr.subgroup_id = sg.subgroup_id
    JOIN product_group pg ON sg.group_id = pg.group_id
    JOIN segment s ON pg.segment_id = s.segment_id
    JOIN customer c ON i.customer_id = c.customer_id
    """

    spend_query = """
    SELECT 
        d.full_date,
        d.year,
        r.region_name,
        p.plant_name,
        s.segment_name,
        pr.product_name,
        v.vendor_name,
        sp.spend_amount
    FROM spend sp
    JOIN date_dim d ON sp.date_id = d.date_id
    JOIN plant p ON sp.plant_id = p.plant_id
    JOIN region r ON p.region_id = r.region_id
    JOIN product pr ON sp.product_id = pr.product_id
    JOIN product_subgroup sg ON pr.subgroup_id = sg.subgroup_id
    JOIN product_group pg ON sg.group_id = pg.group_id
    JOIN segment s ON pg.segment_id = s.segment_id
    JOIN vendor v ON sp.vendor_id = v.vendor_id
    """

    df_revenue = pd.read_sql_query(revenue_query, conn)
    df_spend = pd.read_sql_query(spend_query, conn)

    conn.close()

    df_revenue["date"] = pd.to_datetime(df_revenue["full_date"])
    df_spend["date"] = pd.to_datetime(df_spend["full_date"])

    return df_revenue, df_spend


df_revenue, df_spend = load_data()

# -----------------------
# TEXT → JSON PARSER
# -----------------------
def parse_query(question):

    history = "\n".join(st.session_state.chat_history)

    prompt = f"""
You are an analytics assistant.

Conversation history:
{history}

Current question:
{question}

Convert it into JSON.

Return ONLY JSON.

{{
"metric":"revenue/spend/profit",
"dimension":"region/plant/segment/product/customer/vendor/null",
"year":null,
"last_n_months":null,
"top_n":null,
"bottom_n":null
}}
"""

    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0}
    )

    text = response.text.strip()

    try:
        parsed = json.loads(text)

    except:
        match = re.search(r"\{[\s\S]*\}", text)
        parsed = json.loads(match.group())

    if parsed.get("dimension") == "null":
        parsed["dimension"] = None

    return parsed


# -----------------------
# NATURAL LANGUAGE → SQL
# -----------------------
def generate_sql(question):

    prompt = f"""
Convert this business question into SQL.

Tables:

invoice(date_id, region_id, plant_id, product_id, customer_id, revenue_amount)
spend(date_id, plant_id, product_id, vendor_id, spend_amount)

region(region_id, region_name)
plant(plant_id, plant_name)
product(product_id, product_name)
customer(customer_id, customer_name)
vendor(vendor_id, vendor_name)
date_dim(date_id, full_date, year)

Return ONLY SQL.

Question:
{question}
"""

    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0}
    )

    sql = response.text.strip()

    sql = sql.replace("```sql", "").replace("```", "")

    return sql


def run_sql_query(sql):

    conn = sqlite3.connect("manufacturing.db")

    df = pd.read_sql_query(sql, conn)

    conn.close()

    return df


# -----------------------
# FILTER
# -----------------------
def apply_filters(df, parsed):

    if parsed["year"]:
        df = df[df["year"] == parsed["year"]]

    if parsed["last_n_months"]:

        df["year_month"] = df["date"].dt.to_period("M")

        last_month = df["year_month"].max()

        valid = [last_month - i for i in range(parsed["last_n_months"])]

        df = df[df["year_month"].isin(valid)]

    return df


# -----------------------
# RUN ANALYTICS
# -----------------------
def run_query(parsed):

    metric = parsed["metric"]
    dimension = parsed["dimension"]

    if metric == "revenue":
        df = df_revenue.copy()
        value = "revenue_amount"

    elif metric == "spend":
        df = df_spend.copy()
        value = "spend_amount"

    else:

        rev = apply_filters(df_revenue.copy(), parsed)
        sp = apply_filters(df_spend.copy(), parsed)

        rev_m = rev.groupby(rev["date"].dt.to_period("M"))["revenue_amount"].sum()
        sp_m = sp.groupby(sp["date"].dt.to_period("M"))["spend_amount"].sum()

        profit = pd.concat([rev_m, sp_m], axis=1).fillna(0)
        profit["profit"] = profit["revenue_amount"] - profit["spend_amount"]

        profit = profit.reset_index()
        profit["month"] = profit["date"].astype(str)

        fig = px.line(profit, x="month", y="profit", title="Profit Trend")

        return fig, profit

    df = apply_filters(df, parsed)

    if dimension:

        dim_col = dimension + "_name"

        grouped = df.groupby(dim_col)[value].sum().reset_index()

        if parsed["top_n"]:
            grouped = grouped.sort_values(value, ascending=False).head(parsed["top_n"])

        fig = px.bar(grouped, x=dim_col, y=value)

        return fig, grouped

    monthly = df.groupby(df["date"].dt.to_period("M"))[value].sum().reset_index()

    monthly["month"] = monthly["date"].astype(str)

    fig = px.line(monthly, x="month", y=value)

    return fig, monthly


# -----------------------
# AI INSIGHT
# -----------------------
def generate_insight(data, question):

    prompt = f"""
You are a business analyst.

User question:
{question}

Data:
{data}

Explain key insight in 2 sentences.
"""

    response = model.generate_content(prompt)

    return response.text


# -----------------------
# SUGGEST QUESTIONS
# -----------------------
def suggest_questions(question):

    prompt = f"""
User asked: {question}

Suggest 3 related analytics questions.
"""

    response = model.generate_content(prompt)

    return response.text


# -----------------------
# UI
# -----------------------
st.subheader("Ask a Business Question")

question = st.text_input("Ask your question")

if question:

    st.session_state.chat_history.append(question)

    try:

        parsed = parse_query(question)

        fig, data = run_query(parsed)

        st.plotly_chart(fig, use_container_width=True)

        st.subheader("AI Insight")

        insight = generate_insight(data.head(10), question)

        st.write(insight)

        st.subheader("Suggested Questions")

        suggestions = suggest_questions(question)

        st.write(suggestions)

        st.subheader("Generated SQL")

        sql = generate_sql(question)

        st.code(sql, language="sql")

        st.subheader("SQL Result")

        df_sql = run_sql_query(sql)

        st.dataframe(df_sql)

        if st.button("Show Parsed Query"):
            st.json(parsed)

    except Exception as e:

        st.error("Could not understand the query.")
        st.write(e)
