import streamlit as st
import pandas as pd
import plaid
from plaid.api import plaid_api
from plaid.model.transactions_sync_request import TransactionsSyncRequest
import random
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# ============================================================
# 1. SECURE CONFIGURATION
# ============================================================
# Load the keys from the .env file
load_dotenv()

PLAID_CLIENT_ID = os.getenv('PLAID_CLIENT_ID')
PLAID_SECRET = os.getenv('PLAID_SECRET')
ACCESS_TOKEN = os.getenv('PLAID_ACCESS_TOKEN')

PLAID_ENV = plaid.Environment.Sandbox 
# ============================================================

# 2. Connect to Plaid
@st.cache_resource
def get_client():
    configuration = plaid.Configuration(
        host=PLAID_ENV,
        api_key={'clientId': PLAID_CLIENT_ID, 'secret': PLAID_SECRET}
    )
    api_client = plaid.ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)

# 3. SIMULATOR: Generate "EMG Tech" & Clinic Revenue
def generate_clinic_revenue(num_transactions=30):
    data = []
    services = [
        # YOUR WORK
        {"Item": "NCS Tech Fee (Upper Limb)", "Amount": 75.00, "Type": "EMG Tech Svc"},
        {"Item": "NCS Tech Fee (Lower Limb)", "Amount": 90.00, "Type": "EMG Tech Svc"},
        {"Item": "Bilateral Carpal Tunnel Study", "Amount": 110.00, "Type": "EMG Tech Svc"},
        
        # PASSIVE INCOME
        {"Item": "Facility Fee Split (Dr. Smith)", "Amount": 150.00, "Type": "Facility Split"},
        {"Item": "Facility Fee Split (Dr. Patel)", "Amount": 200.00, "Type": "Facility Split"},
        
        # RETAIL SALES
        {"Item": "Wrist Splint (Retail)", "Amount": 45.00, "Type": "Retail Product"},
        {"Item": "TENS Unit", "Amount": 120.00, "Type": "Retail Product"},
        {"Item": "Lumbar Roll", "Amount": 30.00, "Type": "Retail Product"},
    ]
    
    today = datetime.now()
    
    for _ in range(num_transactions):
        sale = random.choice(services)
        days_ago = random.randint(0, 30)
        date = today - timedelta(days=days_ago)
        
        data.append({
            "Date": date.date(),
            "Description": sale["Item"],
            "Amount": sale["Amount"],
            "Category": sale["Type"],
            "Flow": "IN (Revenue)"
        })
    return pd.DataFrame(data)

# 4. Helper: Clean up Plaid Expenses
def clean_expense_category(name):
    name = name.lower()
    if 'uber' in name or 'united' in name: return "Travel"
    if 'mcdonald' in name or 'starbucks' in name: return "Meals"
    if 'sparkfun' in name or 'apple' in name: return "Equipment/Supplies"
    if 'payment' in name: return "Rent/Overhead"
    return "Misc. Expense"

# 5. The Main App
def main():
    st.set_page_config(page_title="London Physio & EMG", page_icon="🏥", layout="wide")
    st.title("🏥 London Physio & EMG: Owner Dashboard")
    
    # --- LOAD DATA ---
    client = get_client()
    
    # A. Fetch Expenses (Real Plaid Sandbox Data)
    expense_data = []
    try:
        request = TransactionsSyncRequest(access_token=ACCESS_TOKEN)
        response = client.transactions_sync(request)
        plaid_tx = response['added']
        
        for t in plaid_tx:
            expense_data.append({
                "Date": pd.to_datetime(t['date']).date(),
                "Description": t['name'],
                "Amount": t['amount'], 
                "Category": clean_expense_category(t['name']),
                "Flow": "OUT (Expense)"
            })
    except Exception as e:
        st.error("Plaid Connection Error. Check your Access Token in .env")

    df_expenses = pd.DataFrame(expense_data)

    # B. Generate Revenue (Simulated EMG Tech Data)
    df_revenue = generate_clinic_revenue(40) 

    # --- CALCULATE METRICS ---
    total_revenue = df_revenue['Amount'].sum()
    total_expense = df_expenses['Amount'].sum() if not df_expenses.empty else 0
    net_profit = total_revenue - total_expense
    
    profit_margin = (net_profit / total_revenue) * 100 if total_revenue > 0 else 0

    # --- DISPLAY TOP ROW (KPIs) ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Revenue", f"${total_revenue:,.2f}", delta="Income")
    col2.metric("Total Expenses", f"${total_expense:,.2f}", delta="-Cost", delta_color="inverse")
    col3.metric("Net Profit", f"${net_profit:,.2f}", delta=f"{profit_margin:.1f}% Margin")
    col4.metric("Est. Cash Balance", "$18,250.00", help="Previous Balance + Net Profit")

    st.divider()

    # --- CHARTS ---
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("💰 Income Sources")
        st.bar_chart(df_revenue.groupby("Category")["Amount"].sum(), color="#4CAF50")
        
    with c2:
        st.subheader("💸 Expense Breakdown")
        if not df_expenses.empty:
            st.bar_chart(df_expenses.groupby("Category")["Amount"].sum(), color="#FF4B4B")
        else:
            st.info("No expenses found.")

    # --- DETAILED TABLE ---
    st.subheader("📄 Transaction Ledger (All Activity)")
    
    if not df_expenses.empty:
        df_combined = pd.concat([df_revenue, df_expenses])
    else:
        df_combined = df_revenue
        
    df_combined['Date'] = pd.to_datetime(df_combined['Date'])
    df_combined = df_combined.sort_values(by="Date", ascending=False)
    
    # === THE FIX IS HERE ===
    df_combined = df_combined.reset_index(drop=True)
    # =======================
    
    def color_flow(val):
        color = '#d1e7dd' if 'Revenue' in val else '#f8d7da'
        return f'background-color: {color}; color: black'

    st.dataframe(
        df_combined.style.applymap(color_flow, subset=['Flow']),
        use_container_width=True,
        column_config={
            "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
            "Amount": st.column_config.NumberColumn("Amount", format="$%.2f")
        },
        hide_index=True
    )

if __name__ == "__main__":
    main()