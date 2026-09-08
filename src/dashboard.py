import streamlit as st
from google.cloud import bigquery
import pandas as pd
import plotly.express as px
import os
from dotenv import load_dotenv

# Load environment variables (for local testing if needed)
load_dotenv()
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "ecommerce-pipe-ds30")

st.set_page_config(page_title="Multi-Vendor E-Commerce Analytics", page_icon="🛍️", layout="wide")

# Initialize BigQuery Client
@st.cache_resource
def get_bq_client():
    return bigquery.Client(project=PROJECT_ID)

client = get_bq_client()

# ==========================================
# HEADER & SIDEBAR
# ==========================================
st.title("🚀 Multi-Vendor E-Commerce Platform")
st.markdown("Enterprise Big Data Pipeline processing 133M+ rows via GCP BigQuery.")

st.sidebar.header("Filter Dashboard")
vendor_selection = st.sidebar.selectbox(
    "Select Source Vendor",
    ["All Vendors", "Multi-Category Store", "Electronics Store", "Cosmetics Shop"]
)

# Map human-readable selection to database values
vendor_map = {
    "All Vendors": "ALL",
    "Multi-Category Store": "vendor_a_multicategory",
    "Electronics Store": "vendor_c_electronics",
    "Cosmetics Shop": "vendor_b_cosmetics"
}
selected_vendor = vendor_map[vendor_selection]

# Helper function to run queries
@st.cache_data(ttl=600)
def run_query(query: str) -> pd.DataFrame:
    return client.query(query).to_dataframe()

# ==========================================
# 1. EXECUTIVE KPIs
# ==========================================
kpi_query = f"""
    SELECT 
        SUM(total_orders) as total_orders,
        SUM(total_customers) as total_customers,
        SUM(total_revenue) as total_revenue,
        SUM(total_revenue) / SUM(total_orders) as avg_order_value
    FROM `{PROJECT_ID}.ecommerce_analytics.executive_kpis`
    {f"WHERE source_vendor = '{selected_vendor}'" if selected_vendor != "ALL" else ""}
"""
kpi_df = run_query(kpi_query)

if not kpi_df.empty and kpi_df['total_orders'].iloc[0] is not None:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Revenue", f"${kpi_df['total_revenue'].iloc[0]:,.0f}")
    col2.metric("Total Orders", f"{kpi_df['total_orders'].iloc[0]:,.0f}")
    col3.metric("Unique Customers", f"{kpi_df['total_customers'].iloc[0]:,.0f}")
    col4.metric("Avg Order Value", f"${kpi_df['avg_order_value'].iloc[0]:,.2f}")
else:
    st.warning("No data found for this selection.")

st.markdown("---")

# ==========================================
# 2. MONTHLY REVENUE TREND (Line Chart)
# ==========================================
st.subheader("📈 Monthly Revenue Trend")
trend_query = f"""
    SELECT 
        year_month,
        SUM(total_revenue) as total_revenue
    FROM `{PROJECT_ID}.ecommerce_analytics.monthly_revenue`
    {f"WHERE source_vendor = '{selected_vendor}'" if selected_vendor != "ALL" else ""}
    GROUP BY year_month
    ORDER BY year_month
"""
trend_df = run_query(trend_query)

if not trend_df.empty:
    fig_trend = px.area(
        trend_df, x="year_month", y="total_revenue",
        labels={"year_month": "Month", "total_revenue": "Revenue ($)"},
        color_discrete_sequence=["#00b4d8"]
    )
    st.plotly_chart(fig_trend, use_container_width=True)

# ==========================================
# 3. CATEGORY & BRAND PERFORMANCE
# ==========================================
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("🛍️ Top 10 Categories by Revenue")
    # Category performance isn't currently split by vendor in the view,
    # but we can query it globally for this dashboard.
    cat_query = f"""
        SELECT category_main, total_revenue 
        FROM `{PROJECT_ID}.ecommerce_analytics.category_performance`
        ORDER BY total_revenue DESC
        LIMIT 10
    """
    cat_df = run_query(cat_query)
    fig_cat = px.bar(
        cat_df, x="total_revenue", y="category_main", orientation="h",
        labels={"category_main": "Category", "total_revenue": "Revenue ($)"},
        color_discrete_sequence=["#ff9f1c"]
    )
    fig_cat.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig_cat, use_container_width=True)

with col_b:
    st.subheader("🏆 Top 10 Products by Revenue")
    prod_query = f"""
        SELECT product_id, brand, total_revenue 
        FROM `{PROJECT_ID}.ecommerce_analytics.product_performance`
        ORDER BY total_revenue DESC
        LIMIT 10
    """
    prod_df = run_query(prod_query)
    # Convert product_id to string so it's treated as a category, not a number
    prod_df["product_id"] = prod_df["product_id"].astype(str)
    
    fig_prod = px.bar(
        prod_df, x="total_revenue", y="product_id", orientation="h",
        hover_data=["brand"],
        labels={"product_id": "Product ID", "total_revenue": "Revenue ($)"},
        color_discrete_sequence=["#8338ec"]
    )
    fig_prod.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig_prod, use_container_width=True)

st.markdown("---")
st.caption("Dashboard built with Streamlit and Google BigQuery. Processing 133M+ rows of data.")
