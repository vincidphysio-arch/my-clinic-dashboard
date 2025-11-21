import streamlit as st
import pandas as pd
import plaid
from plaid.api import plaid_api
from plaid.model.transactions_sync_request import TransactionsSyncRequest
import random
from datetime import datetime, timedelta
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ============================================================
# 1. SMART CONFIGURATION
# ============================================================
def get_key(name):
    if name in st.secrets: return st.secrets[name]
    return os.getenv(name)

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

PLAID_CLIENT_ID = get_key('PLAID_CLIENT_ID')
PLAID_SECRET = get_key('PLAID_SECRET')
ACCESS_TOKEN = get_key('PLAID_ACCESS_TOKEN')
PLAID_ENV = plaid.Environment.Sandbox

# ============================================================
# 2. CONNECT TO DATA SOURCES
# ============================================================

@st.cache_resource
def get_plaid_client():
    configuration = plaid.Configuration(
        host=PLAID_ENV,
        api_key={'clientId': PLAID_CLIENT_ID, 'secret': PLAID_SECRET}
    )
    api_client = plaid.ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)

@st.cache_data(ttl=60)
def get_google_sheet_data():
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            
            # OPEN THE SHEET (Ensure your Google Sheet is named exactly this)
            sheet = client.open("Clinic Expenses").sheet1
            data = sheet.get_all_records()
            return pd.DataFrame(data)
    except Exception as e:
        st.warning(f"Google Sheet Error: {e}")
        return pd.DataFrame()
    return pd.DataFrame()

# ============================================================
# 3. DATA PROCESSING
# ============================================================

def clean_expense_category(name):
    name = name.lower()
    if 'uber' in name or 'united' in name: return "Travel"
    if 'mcdonald' in name or 'starbucks' in name: return "Meals"
    if 'sparkfun' in name or 'apple' in name: return "Equipment/Supplies"
    return "Misc. Expense"

def main():
    st.set_page_config(page_title="London Physio & EMG", page_icon="🏥", layout="wide")
    st.title("🏥 London Physio & EMG: Owner Dashboard")

    # --- 1. GET PLAID DATA (Bank) ---
    plaid_client = get_plaid_client()
    plaid_data = []
    try:
        request = TransactionsSyncRequest(access_token=ACCESS_TOKEN)
        response = plaid_client.transactions_sync(request)
        for t in response['added']:
            plaid_data.append({
                "Date": pd.to_datetime(t['date']).date(),
                "Description": t['name'],
                "Amount": t['amount'],
                "Category": clean_expense_category(t['name']),
                "Source": "Bank Feed (Plaid)",
                "Flow": "OUT (Expense)",
                "Receipt": None  # No receipts for bank yet
            })
    except:
        st.error("Plaid Error. Check Secrets.")

    # --- 2. GET GOOGLE SHEET DATA (Manual) ---
    sheet_df = get_google_sheet_data()
    sheet_data = []
    if not sheet_df.empty:
        for index, row in sheet_df.iterrows():
            try:
                d = pd.to_datetime(row['Date']).date()
            except:
                d = datetime.now().date()
            
            # SAFE GET: Checks if 'receipts' column exists, otherwise is None
            receipt_link = row.get('receipts', None) 
            if receipt_link == "": receipt_link = None

            sheet_data.append({
                "Date": d,
                "Description": row['Description'],
                "Amount": float(row['Amount']),
                "Category": row['Category'],
                "Source": "Google Sheet",
                "Flow": "OUT (Expense)",
                "Receipt": receipt_link
            })

    # --- 3. GENERATE REVENUE (Simulator) ---
    rev_data = []
    services = [
        {"Item": "NCS Tech Fee", "Amount": 75.00, "Type": "EMG Tech Svc"},
        {"Item": "Facility Split", "Amount": 150.00, "Type": "Facility Split"},
    ]
    for _ in range(30):
        sale = random.choice(services)
        rev_data.append({
            "Date": (datetime.now() - timedelta(days=random.randint(0,30))).date(),
            "Description": sale["Item"],
            "Amount": sale["Amount"],
            "Category": sale["Type"],
            "Source": "Simulator",
            "Flow": "IN (Revenue)",
            "Receipt": None
        })

    # --- MERGE EVERYTHING ---
    df_plaid = pd.DataFrame(plaid_data)
    df_sheet = pd.DataFrame(sheet_data)
    df_rev = pd.DataFrame(rev_data)
    
    # Check if empty before concat
    dfs_to_merge = [df for df in [df_plaid, df_sheet, df_rev] if not df.empty]
    if dfs_to_merge:
        df_all = pd.concat(dfs_to_merge).reset_index(drop=True)
        df_all['Date'] = pd.to_datetime(df_all['Date'])
        df_all = df_all.sort_values(by="Date", ascending=False)
    else:
        st.stop() # Stop if no data

    # --- DISPLAY ---
    
    total_rev = df_all[df_all['Flow'] == 'IN (Revenue)']['Amount'].sum()
    total_exp = df_all[df_all['Flow'] == 'OUT (Expense)']['Amount'].sum()
    net = total_rev - total_exp
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Revenue", f"${total_rev:,.2f}")
    col2.metric("Total Expenses", f"${total_exp:,.2f}")
    col3.metric("Net Profit", f"${net:,.2f}")

    st.subheader("📋 Consolidated Ledger")
    st.info("Transactions from Plaid, Simulator, and Google Sheets.")
    
    st.dataframe(
        df_all[['Date', 'Description', 'Amount', 'Category', 'Source', 'Flow', 'Receipt']],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
            "Amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
            "Receipt": st.column_config.LinkColumn("Receipt", display_text="View Receipt")
        }
    )

if __name__ == "__main__":
    main()
