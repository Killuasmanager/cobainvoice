import streamlit as st
import requests
import base64
import json
from datetime import datetime, timedelta
import pandas as pd

# Page config
st.set_page_config(
    page_title="InvoiceMatch - AI Invoice Automation",
    page_icon="🧾",
    layout="wide"
)

# Initialize session state
if 'invoices' not in st.session_state:
    st.session_state.invoices = [
        {
            'id': 1001,
            'client_name': 'Acme Corp',
            'client_email': 'billing@acme.com',
            'project_name': 'Brand Redesign',
            'contract_value': 12000.0,
            'items': [
                {'description': 'Brand Strategy', 'qty': 1, 'price': 5000.0},
                {'description': 'Logo Design', 'qty': 1, 'price': 7000.0}
            ],
            'payment_terms': 'Net 30',
            'due_date': '2025-01-10',
            'status': 'overdue',
            'created_at': '2024-12-10',
            'payments': [{'amount': 5000.0, 'date': '2025-01-05', 'method': 'Bank Transfer', 'reference': 'TRF-001'}],
            'reminders_sent': 3
        },
        {
            'id': 1002,
            'client_name': 'Tech Innovations',
            'client_email': 'finance@techinno.com',
            'project_name': 'E-commerce Platform',
            'contract_value': 25000.0,
            'items': [
                {'description': 'Platform Development', 'qty': 1, 'price': 20000.0},
                {'description': 'Training', 'qty': 1, 'price': 5000.0}
            ],
            'payment_terms': 'Net 45',
            'due_date': '2025-02-28',
            'status': 'paid',
            'created_at': '2025-01-01',
            'payments': [{'amount': 25000.0, 'date': '2025-01-15', 'method': 'Wire Transfer', 'reference': 'WIR-4521'}],
            'reminders_sent': 0
        }
    ]

if 'extracted_data' not in st.session_state:
    st.session_state.extracted_data = None

if 'selected_invoice' not in st.session_state:
    st.session_state.selected_invoice = None

# Helper functions
def format_currency(amount):
    return f"${float(amount):,.0f}"

def get_days_until_due(due_date):
    if not due_date:
        return 999
    due = datetime.strptime(due_date, '%Y-%m-%d')
    today = datetime.now()
    return (due - today).days

def calculate_stats():
    invoices = st.session_state.invoices
    total_collected = sum(sum(float(p['amount']) for p in inv.get('payments', [])) for inv in invoices)
    total_receivables = sum(
        float(inv['contract_value']) - sum(float(p['amount']) for p in inv.get('payments', []))
        for inv in invoices if inv['status'] not in ['paid', 'draft']
    )
    overdue = sum(1 for inv in invoices if inv['status'] == 'overdue' or (inv['status'] == 'sent' and get_days_until_due(inv['due_date']) < 0))
    pending = sum(1 for inv in invoices if inv['status'] == 'draft')
    return {'collected': total_collected, 'receivables': total_receivables, 'overdue': overdue, 'pending': pending}

def extract_with_ai(file_bytes, file_type):
    """Extract using OpenRouter API with Gemini (FREE!)"""
    try:
        api_key = st.secrets["OPENROUTER_API_KEY"]
        base64_data = base64.standard_b64encode(file_bytes).decode('utf-8')
        
        if 'pdf' in file_type.lower():
            media_type = 'application/pdf'
        elif 'png' in file_type.lower():
            media_type = 'image/png'
        else:
            media_type = 'image/jpeg'
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://invoicematch.streamlit.app",
                "X-Title": "InvoiceMatch"
            },
            json={
                "model": "google/gemini-2.0-flash-001",  # FREE!
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{base64_data}"}},
                        {"type": "text", "text": 'Extract invoice/contract data. Return ONLY valid JSON: {"client_name":"","client_email":"","project_name":"","contract_value":0,"items":[{"description":"","qty":1,"price":0}],"payment_terms":"Net 30","due_date":"YYYY-MM-DD"}'}
                    ]
                }],
                "max_tokens": 1024
            },
            timeout=60
        )
        
        if response.status_code != 200:
            return None
        
        text = response.json()['choices'][0]['message']['content'].strip()
        if '```' in text:
            text = text.split('```')[1].replace('json', '').strip()
        start, end = text.find('{'), text.rfind('}') + 1
        if start != -1 and end > start:
            text = text[start:end]
        
        data = json.loads(text)
        data['contract_value'] = float(data.get('contract_value', 0))
        return data
    except:
        return None

# Sidebar
with st.sidebar:
    st.markdown("## 🧾 InvoiceMatch")
    st.caption("AI-Powered Invoice Automation")
    st.divider()
    page = st.radio("Menu", ["📊 Dashboard", "📄 Invoices", "➕ New Invoice"], label_visibility="collapsed")
    st.divider()
    st.caption("Contract in → Invoice out ✨")

# DASHBOARD
if page == "📊 Dashboard":
    st.header("📊 Dashboard")
    stats = calculate_stats()
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Collected", format_currency(stats['collected']))
    c2.metric("📋 Receivables", format_currency(stats['receivables']))
    c3.metric("⚠️ Overdue", f"{stats['overdue']} inv")
    c4.metric("📝 Drafts", f"{stats['pending']} inv")
    
    st.divider()
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔴 Needs Attention")
        attention = [i for i in st.session_state.invoices if i['status'] in ['draft', 'overdue'] or (i['status'] == 'sent' and get_days_until_due(i['due_date']) < 0)]
        if not attention:
            st.success("🎉 All caught up!")
        for inv in attention[:5]:
            st.markdown(f"**{inv['client_name']}** - {format_currency(inv['contract_value'])} `{inv['status'].upper()}`")
    
    with col2:
        st.subheader("💚 Recent Payments")
        payments = []
        for inv in st.session_state.invoices:
            for p in inv.get('payments', []):
                payments.append({'client': inv['client_name'], **p})
        if not payments:
            st.info("No payments yet")
        for p in sorted(payments, key=lambda x: x['date'], reverse=True)[:5]:
            st.markdown(f"**{p['client']}** - {format_currency(p['amount'])} ({p['date']})")

# INVOICES
elif page == "📄 Invoices":
    st.header("📄 All Invoices")
    
    # Invoice selection
    invoice_options = {f"{inv['client_name']} - {format_currency(inv['contract_value'])} ({inv['status'].upper()})": inv['id'] for inv in st.session_state.invoices}
    selected = st.selectbox("Select Invoice", options=list(invoice_options.keys()))
    
    if selected:
        inv_id = invoice_options[selected]
        inv = next((i for i in st.session_state.invoices if i['id'] == inv_id), None)
        
        if inv:
            total_paid = sum(float(p['amount']) for p in inv.get('payments', []))
            remaining = float(inv['contract_value']) - total_paid
            days_until = get_days_until_due(inv['due_date'])
            is_overdue = inv['status'] not in ['paid', 'draft'] and days_until < 0
            
            st.divider()
            
            # Invoice Details
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📋 Details")
                st.write(f"**Client:** {inv['client_name']}")
                st.write(f"**Email:** {inv['client_email']}")
                st.write(f"**Project:** {inv['project_name']}")
                st.write(f"**Due Date:** {inv['due_date']}")
                st.write(f"**Status:** {inv['status'].upper()}")
                if is_overdue:
                    st.error(f"⚠️ Overdue by {abs(days_until)} days!")
            
            with col2:
                st.subheader("💰 Payment Status")
                st.write(f"**Total:** {format_currency(inv['contract_value'])}")
                st.write(f"**Paid:** {format_currency(total_paid)}")
                st.write(f"**Remaining:** {format_currency(remaining)}")
                if remaining > 0 and float(inv['contract_value']) > 0:
                    st.progress(total_paid / float(inv['contract_value']))
            
            st.divider()
            
            # Actions - OUTSIDE of any nested container
            st.subheader("⚡ Actions")
            
            action_col1, action_col2 = st.columns(2)
            
            with action_col1:
                # Send Reminder Button
                if remaining > 0 and inv['status'] != 'draft':
                    if st.button("📧 Send Reminder", key=f"remind_{inv['id']}", use_container_width=True):
                        inv['reminders_sent'] = inv.get('reminders_sent', 0) + 1
                        st.success(f"📧 Reminder #{inv['reminders_sent']} sent to {inv['client_email']}!")
                        st.rerun()
                
                # Approve Button
                if inv['status'] == 'draft':
                    if st.button("✅ Approve & Send", key=f"approve_{inv['id']}", use_container_width=True):
                        inv['status'] = 'sent'
                        st.success(f"✅ Invoice sent to {inv['client_email']}!")
                        st.rerun()
            
            with action_col2:
                st.write(f"**Reminders sent:** {inv.get('reminders_sent', 0)}")
            
            # Payment Form - Separate section
            if remaining > 0 and inv['status'] != 'draft':
                st.divider()
                st.subheader("💳 Record Payment")
                
                with st.form(key=f"payment_form_{inv['id']}"):
                    pay_amount = st.number_input("Amount ($)", value=remaining, min_value=0.0, max_value=remaining, step=100.0)
                    pay_method = st.selectbox("Payment Method", ["Bank Transfer", "Wire Transfer", "Credit Card", "PayPal", "Check"])
                    pay_ref = st.text_input("Reference Number", placeholder="TRF-001")
                    
                    if st.form_submit_button("💰 Record Payment", use_container_width=True):
                        if 'payments' not in inv:
                            inv['payments'] = []
                        inv['payments'].append({
                            'amount': float(pay_amount),
                            'date': datetime.now().strftime('%Y-%m-%d'),
                            'method': pay_method,
                            'reference': pay_ref
                        })
                        new_total = sum(float(p['amount']) for p in inv['payments'])
                        if new_total >= float(inv['contract_value']):
                            inv['status'] = 'paid'
                        st.success(f"💰 Payment of {format_currency(pay_amount)} recorded!")
                        st.balloons()
                        st.rerun()
            
            # Payment History
            if inv.get('payments'):
                st.divider()
                st.subheader("📜 Payment History")
                df = pd.DataFrame([{
                    'Date': p['date'],
                    'Amount': format_currency(p['amount']),
                    'Method': p['method'],
                    'Reference': p['reference']
                } for p in inv['payments']])
                st.dataframe(df, use_container_width=True, hide_index=True)

# NEW INVOICE
elif page == "➕ New Invoice":
    st.header("➕ Create New Invoice")
    st.info("🤖 Upload a contract/invoice image and AI will extract the data!")
    
    uploaded = st.file_uploader("Upload Document", type=['png', 'jpg', 'jpeg', 'webp'])
    
    if uploaded:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📄 Preview")
            st.image(uploaded, use_container_width=True)
        
        with col2:
            st.subheader("🤖 AI Extraction")
            
            if st.button("🚀 Extract with AI", type="primary", use_container_width=True):
                with st.spinner("🤖 AI is reading the document..."):
                    file_bytes = uploaded.read()
                    result = extract_with_ai(file_bytes, uploaded.type)
                    if result:
                        st.session_state.extracted_data = result
                        st.success("✅ Data extracted!")
                    else:
                        st.error("❌ Failed to extract. Try a clearer image.")
            
            if st.session_state.extracted_data:
                data = st.session_state.extracted_data
                st.divider()
                
                with st.form("new_invoice_form"):
                    st.subheader("✏️ Review & Edit")
                    
                    client = st.text_input("Client Name", value=data.get('client_name', ''))
                    email = st.text_input("Client Email", value=data.get('client_email', ''))
                    project = st.text_input("Project", value=data.get('project_name', ''))
                    amount = st.number_input("Amount ($)", value=float(data.get('contract_value', 0)), step=100.0)
                    terms = st.selectbox("Payment Terms", ["Net 7", "Net 14", "Net 30", "Net 45", "Net 60"], index=2)
                    due = st.date_input("Due Date", value=datetime.now() + timedelta(days=30))
                    
                    if data.get('items'):
                        st.write("**Line Items:**")
                        st.dataframe(pd.DataFrame(data['items']), hide_index=True)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        draft_btn = st.form_submit_button("📝 Save as Draft", use_container_width=True)
                    with col2:
                        send_btn = st.form_submit_button("✅ Approve & Send", use_container_width=True)
                    
                    if draft_btn or send_btn:
                        new_inv = {
                            'id': max([i['id'] for i in st.session_state.invoices], default=1000) + 1,
                            'client_name': client,
                            'client_email': email,
                            'project_name': project,
                            'contract_value': float(amount),
                            'items': data.get('items', []),
                            'payment_terms': terms,
                            'due_date': due.strftime('%Y-%m-%d'),
                            'status': 'sent' if send_btn else 'draft',
                            'created_at': datetime.now().strftime('%Y-%m-%d'),
                            'payments': [],
                            'reminders_sent': 0
                        }
                        st.session_state.invoices.append(new_inv)
                        st.session_state.extracted_data = None
                        
                        if send_btn:
                            st.success(f"✅ Invoice sent to {email}!")
                        else:
                            st.success("📝 Saved as draft!")
                        st.balloons()
                        st.rerun()

# Footer
st.divider()
st.caption("InvoiceMatch ✨ Powered by AI via OpenRouter")
