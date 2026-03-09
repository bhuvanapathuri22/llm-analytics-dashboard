import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import google.generativeai as genai
import json
import re


st.set_page_config(page_title="AI Manufacturing Analytics", layout="wide")
st.title("🏭 AI Manufacturing Analytics")



genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.5-flash")


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


def parse_query(question):

    prompt = f"""
Convert this analytics question into JSON.

Question: "{question}"

Return ONLY JSON. No explanation.

JSON format:

{{
"metric": "revenue/spend/profit",
"dimension": "region/plant/segment/product/customer/vendor/null",
"year": null or number,
"last_n_months": null or number,
"top_n": null or number,
"bottom_n": null or number
}}
"""

    response = model.generate_content(prompt,generation_config={"temperature":0})

    text = response.text.strip()

    try:
        # Try direct JSON
        parsed = json.loads(text)

    except:
        # Extract JSON block if model added text
        json_match = re.search(r"\{[\s\S]*\}", text)

        if json_match:
            parsed = json.loads(json_match.group())
        else:
            raise ValueError("LLM did not return JSON")

    if parsed.get("dimension") == "null":
        parsed["dimension"] = None

    return parsed



def apply_filters(df, parsed):

    if parsed["year"]:
        df = df[df["year"] == parsed["year"]]

    if parsed["last_n_months"]:

        df["year_month"] = df["date"].dt.to_period("M")

        last_month = df["year_month"].max()

        valid_months = [last_month - i for i in range(parsed["last_n_months"])]

        df = df[df["year_month"].isin(valid_months)]

    return df


def is_valid_query(parsed):

    if parsed["metric"] not in ["revenue", "spend", "profit"]:
        return False

    return True


def run_query(parsed):

    metric = parsed["metric"]
    dimension = parsed["dimension"]

    # SELECT DATASET
    if metric == "revenue":
        df = df_revenue.copy()
        value = "revenue_amount"

    elif metric == "spend":
        df = df_spend.copy()
        value = "spend_amount"

    else:
        rev = df_revenue.copy()
        sp = df_spend.copy()

        rev = apply_filters(rev, parsed)
        sp = apply_filters(sp, parsed)

        rev_m = rev.groupby(rev["date"].dt.to_period("M"))["revenue_amount"].sum()
        sp_m = sp.groupby(sp["date"].dt.to_period("M"))["spend_amount"].sum()

        profit = pd.concat([rev_m, sp_m], axis=1).fillna(0)
        profit["profit"] = profit["revenue_amount"] - profit["spend_amount"]

        profit = profit.reset_index()
        profit["month"] = profit["date"].astype(str)

        fig = px.line(profit, x="month", y="profit", title="Profit Trend")

        total = profit["profit"].sum()

        return fig, total, "Profit"

    df = apply_filters(df, parsed)

    # DIMENSION QUERY
    if dimension:

        dim_col = dimension + "_name"

        grouped = df.groupby(dim_col)[value].sum().reset_index()

        if parsed["top_n"]:
            grouped = grouped.sort_values(value, ascending=False).head(parsed["top_n"])

        if parsed["bottom_n"]:
            grouped = grouped.sort_values(value).head(parsed["bottom_n"])

        fig = px.bar(grouped, x=dim_col, y=value,
                     title=f"{metric.capitalize()} by {dimension.capitalize()}")

        total = grouped[value].sum()

        return fig, total, metric.capitalize()

    monthly = df.groupby(df["date"].dt.to_period("M"))[value].sum().reset_index()

    monthly["month"] = monthly["date"].astype(str)

    fig = px.line(monthly, x="month", y=value,
                  title=f"{metric.capitalize()} Trend")

    total = monthly[value].sum()

    return fig, total, metric.capitalize()



# -----------------------------
# USER QUERY UI
# -----------------------------

st.subheader("Ask a Business Question")

question = st.text_input(
    "Ask your question (Press ENTER to analyze)",
    key="query_box"
)

if question:

    try:
        parsed = parse_query(question)

        # Validate query
        if parsed["metric"] not in ["revenue", "spend", "profit"]:
            st.warning("Please ask a business analytics question about revenue, spend, or profit.")

        else:

            fig, total, metric = run_query(parsed)

            # Chart
            st.plotly_chart(fig, use_container_width=True)

            # Total value
            st.metric(f"Total {metric}", f"{total:,.2f}")

            # Optional debug button
            if st.button("Show Parsed Query"):
                st.json(parsed)

    except Exception as e:

        st.error("Could not understand the query.")
        st.write("Debug info:", e)

