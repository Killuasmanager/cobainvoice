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
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(90deg, #10b981, #14b8a6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    .sub-header {
        color: #64748b;
        font-size: 1rem;
        margin-top: -10px;
    }
    .stButton > button {
        background: linear-gradient(90deg, #10b981, #14b8a6);
        color: white;
        border: none;
        border-radius: 0.75rem;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
    }
    .stButton > button:hover {
        background: linear-gradient(90deg, #059669, #0d9488);
    }
</style>
""", unsafe_allow_html=True)

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
                {'description': 'Brand Strategy', 'qty': 1, 'price': 5000},
                {'description': 'Logo Design', 'qty': 1, 'price': 7000}
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
                {'description': 'Platform Development', 'qty': 1, 'price': 20000},
                {'description': 'Training', 'qty': 1, 'price': 5000}
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

if 'show_payment_form' not in st.session_state:
    st.session_state.show_payment_form = None

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
    
    total_collected = sum(
        sum(float(p['amount']) for p in inv.get('payments', []))
        for inv in invoices
    )
    
    total_receivables = sum(
        float(inv['contract_value']) - sum(float(p['amount']) for p in inv.get('payments', []))
        for inv in invoices
        if inv['status'] not in ['paid', 'draft']
    )
    
    overdue = sum(
        1 for inv in invoices
        if inv['status'] == 'overdue' or (inv['status'] == 'sent' and get_days_until_due(inv['due_date']) < 0)
    )
    
    pending = sum(1 for inv in invoices if inv['status'] == 'draft')
    
    return {
        'collected': total_collected,
        'receivables': total_receivables,
        'overdue': overdue,
        'pending': pending
    }

def extract_with_openrouter(file_bytes, file_type):
    """Extract contract data using OpenRouter API"""
    try:
        api_key = st.secrets["OPENROUTER_API_KEY"]
        
        # Encode file to base64
        base64_data = base64.standard_b64encode(file_bytes).decode('utf-8')
        
        # Determine media type
        if 'pdf' in file_type.lower():
            media_type = 'application/pdf'
        elif 'png' in file_type.lower():
            media_type = 'image/png'
        elif 'jpg' in file_type.lower() or 'jpeg' in file_type.lower():
            media_type = 'image/jpeg'
        else:
            media_type = 'image/png'
        
        user_content = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{media_type};base64,{base64_data}"
                }
            },
            {
                "type": "text", 
                "text": """Extract contract/invoice data from this document. Return ONLY valid JSON:
{
    "client_name": "Company or person name",
    "client_email": "email@example.com",
    "project_name": "Project description", 
    "contract_value": 0,
    "items": [{"description": "Item", "qty": 1, "price": 0}],
    "payment_terms": "Net 30",
    "due_date": "YYYY-MM-DD",
    "contract_number": "ID"
}
Rules: contract_value=number, due_date=YYYY-MM-DD, extract ALL items. Return ONLY JSON."""
            }
        ]
        
        # Call OpenRouter API
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://invoicematch.streamlit.app",
                "X-Title": "InvoiceMatch AI"
            },
            json={
                "model": "google/gemini-2.0-flash-001",  # FREE model with vision!
                "messages": [
                    {
                        "role": "user",
                        "content": user_content
                    }
                ],
                "max_tokens": 1024
            }
        )
        
        if response.status_code != 200:
            st.error(f"API Error: {response.status_code} - {response.text}")
            return None
        
        result = response.json()
        response_text = result['choices'][0]['message']['content'].strip()
        
        # Clean JSON if wrapped in markdown
        if '```' in response_text:
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
        response_text = response_text.strip()
        
        # Find JSON object
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        if start != -1 and end > start:
            response_text = response_text[start:end]
        
        data = json.loads(response_text)
        # Ensure contract_value is float
        data['contract_value'] = float(data.get('contract_value', 0))
        return data
        
    except json.JSONDecodeError as e:
        st.error(f"Failed to parse AI response: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Extraction error: {str(e)}")
        return None

# Sidebar
with st.sidebar:
    st.markdown('<p class="main-header">🧾 InvoiceMatch</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">AI-Powered Invoice Automation</p>', unsafe_allow_html=True)
    st.divider()
    
    page = st.radio(
        "Navigation",
        ["📊 Dashboard", "📄 Invoices", "➕ New Invoice"],
        label_visibility="collapsed"
    )
    
    st.divider()
    st.caption("Contract in → Invoice out ✨")
    st.caption("Powered by AI")

# Main content
if page == "📊 Dashboard":
    st.markdown("## 📊 Dashboard")
    
    stats = calculate_stats()
    
    # Stats row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="💰 Total Collected",
            value=format_currency(stats['collected']),
            delta="This month"
        )
    
    with col2:
        st.metric(
            label="📋 Receivables", 
            value=format_currency(stats['receivables']),
            delta=f"{len([i for i in st.session_state.invoices if i['status'] == 'sent'])} pending"
        )
    
    with col3:
        st.metric(
            label="⚠️ Overdue",
            value=f"{stats['overdue']} invoices",
            delta="Needs attention" if stats['overdue'] > 0 else "All good!",
            delta_color="inverse" if stats['overdue'] > 0 else "normal"
        )
    
    with col4:
        st.metric(
            label="📝 Drafts",
            value=f"{stats['pending']} invoices",
            delta="Pending approval"
        )
    
    st.divider()
    
    # Two columns
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🔴 Needs Attention")
        attention_invoices = [
            inv for inv in st.session_state.invoices
            if inv['status'] == 'draft' or inv['status'] == 'overdue' or 
            (inv['status'] == 'sent' and get_days_until_due(inv['due_date']) < 0)
        ]
        
        if not attention_invoices:
            st.success("🎉 All caught up!")
        else:
            for inv in attention_invoices[:5]:
                with st.container():
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**{inv['client_name']}**")
                        st.caption(f"{format_currency(inv['contract_value'])}")
                    with c2:
                        st.markdown(f"🔴 {inv['status'].upper()}")
    
    with col2:
        st.markdown("### 💚 Recent Payments")
        all_payments = []
        for inv in st.session_state.invoices:
            for payment in inv.get('payments', []):
                all_payments.append({'client': inv['client_name'], **payment})
        
        if not all_payments:
            st.info("No payments yet")
        else:
            for payment in sorted(all_payments, key=lambda x: x['date'], reverse=True)[:5]:
                with st.container():
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**{payment['client']}**")
                        st.caption(f"{payment['method']}")
                    with c2:
                        st.markdown(f"**{format_currency(payment['amount'])}**")

elif page == "📄 Invoices":
    st.markdown("## 📄 All Invoices")
    
    status_filter = st.selectbox("Filter", ["All", "Draft", "Sent", "Paid", "Overdue"])
    
    filtered = st.session_state.invoices
    if status_filter != "All":
        filtered = [inv for inv in filtered if inv['status'] == status_filter.lower()]
    
    for idx, inv in enumerate(filtered):
        days_until = get_days_until_due(inv['due_date'])
        is_overdue = inv['status'] not in ['paid', 'draft'] and days_until < 0
        total_paid = sum(float(p['amount']) for p in inv.get('payments', []))
        remaining = float(inv['contract_value']) - total_paid
        
        with st.expander(f"**{inv['client_name']}** - {format_currency(inv['contract_value'])} ({inv['status'].upper()})"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**Details**")
                st.write(f"📧 {inv.get('client_email', 'N/A')}")
                st.write(f"📋 {inv['project_name']}")
                st.write(f"📅 Due: {inv['due_date']}")
                if is_overdue:
                    st.error(f"⚠️ Overdue by {abs(days_until)} days!")
            
            with col2:
                st.markdown("**Payment**")
                st.write(f"Total: {format_currency(inv['contract_value'])}")
                st.write(f"Paid: {format_currency(total_paid)}")
                st.write(f"Remaining: {format_currency(remaining)}")
                if remaining > 0 and float(inv['contract_value']) > 0:
                    st.progress(total_paid / float(inv['contract_value']))
            
            with col3:
                st.markdown("**Actions**")
                
                if inv['status'] == 'draft':
                    if st.button("✅ Approve & Send", key=f"approve_{inv['id']}_{idx}"):
                        inv['status'] = 'sent'
                        st.success(f"✅ Sent to {inv.get('client_email')}")
                        st.rerun()
                
                if remaining > 0 and inv['status'] != 'draft':
                    if st.button("📧 Send Reminder", key=f"remind_{inv['id']}_{idx}"):
                        inv['reminders_sent'] = inv.get('reminders_sent', 0) + 1
                        st.success(f"📧 Reminder sent! ({inv['reminders_sent']} total)")
                        st.rerun()
                    
                    # Payment form - now properly structured
                    st.markdown("---")
                    st.markdown("**💰 Record Payment**")
                    with st.form(key=f"payment_form_{inv['id']}_{idx}"):
                        pay_amount = st.number_input(
                            "Amount", 
                            value=remaining, 
                            min_value=0.0, 
                            max_value=remaining,
                            step=100.0,
                            key=f"amount_{inv['id']}_{idx}"
                        )
                        pay_method = st.selectbox(
                            "Method", 
                            ["Bank Transfer", "Wire", "Credit Card", "PayPal"],
                            key=f"method_{inv['id']}_{idx}"
                        )
                        pay_ref = st.text_input(
                            "Reference",
                            placeholder="TRF-001",
                            key=f"ref_{inv['id']}_{idx}"
                        )
                        
                        submitted = st.form_submit_button("💰 Record Payment")
                        
                        if submitted:
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
                            st.success(f"💰 {format_currency(pay_amount)} recorded!")
                            st.rerun()
            
            if inv.get('payments'):
                st.markdown("**Payment History**")
                payment_data = []
                for p in inv['payments']:
                    payment_data.append({
                        'Date': p['date'],
                        'Amount': format_currency(p['amount']),
                        'Method': p['method'],
                        'Reference': p['reference']
                    })
                st.dataframe(pd.DataFrame(payment_data), hide_index=True)

elif page == "➕ New Invoice":
    st.markdown("## ➕ Create New Invoice")
    st.markdown("Upload a contract/PO and AI will extract all details! 🤖")
    
    uploaded_file = st.file_uploader(
        "Drop your contract here",
        type=['pdf', 'png', 'jpg', 'jpeg'],
        help="PDF, PNG, JPG supported"
    )
    
    if uploaded_file:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("### 📄 Document")
            if 'pdf' not in uploaded_file.type:
                st.image(uploaded_file, use_container_width=True)
            else:
                st.info(f"📄 {uploaded_file.name}")
        
        with col2:
            st.markdown("### 🤖 AI Extraction")
            
            if st.button("🚀 Extract with AI", type="primary"):
                with st.spinner("🤖 AI analyzing document..."):
                    file_bytes = uploaded_file.read()
                    extracted = extract_with_openrouter(file_bytes, uploaded_file.type)
                    
                    if extracted:
                        st.session_state.extracted_data = extracted
                        st.success("✅ Extracted!")
                    else:
                        st.error("Extraction failed")
            
            if st.session_state.extracted_data:
                data = st.session_state.extracted_data
                
                st.divider()
                st.markdown("### ✅ Extracted Data")
                
                with st.form("invoice_form"):
                    client_name = st.text_input("Client", value=data.get('client_name', ''))
                    client_email = st.text_input("Email", value=data.get('client_email', ''))
                    project = st.text_input("Project", value=data.get('project_name', ''))
                    value = st.number_input("Amount ($)", value=float(data.get('contract_value', 0)), step=100.0)
                    terms = st.selectbox("Terms", ["Net 7", "Net 14", "Net 30", "Net 45"], index=2)
                    due = st.date_input("Due Date", value=datetime.now() + timedelta(days=30))
                    
                    if data.get('items'):
                        st.markdown("**Items**")
                        st.dataframe(pd.DataFrame(data['items']), hide_index=True)
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        draft = st.form_submit_button("📝 Save Draft")
                    with c2:
                        send = st.form_submit_button("✅ Approve & Send")
                    
                    if draft or send:
                        new_inv = {
                            'id': max([i['id'] for i in st.session_state.invoices], default=1000) + 1,
                            'client_name': client_name,
                            'client_email': client_email,
                            'project_name': project,
                            'contract_value': float(value),
                            'items': data.get('items', []),
                            'payment_terms': terms,
                            'due_date': due.strftime('%Y-%m-%d'),
                            'status': 'sent' if send else 'draft',
                            'created_at': datetime.now().strftime('%Y-%m-%d'),
                            'payments': [],
                            'reminders_sent': 0
                        }
                        
                        st.session_state.invoices.append(new_inv)
                        st.session_state.extracted_data = None
                        
                        if send:
                            st.success(f"✅ Sent to {client_email}!")
                        else:
                            st.success("📝 Saved as draft!")
                        st.balloons()
                        st.rerun()

# Footer
st.divider()
st.caption("InvoiceMatch ✨ Contract in → Invoice out")
