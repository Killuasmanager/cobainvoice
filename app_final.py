import streamlit as st
import requests
import base64
import json
from datetime import datetime, timedelta
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import fitz  # PyMuPDF for PDF

# Page config
st.set_page_config(
    page_title="InvoiceMatch - AI Invoice Automation",
    page_icon="🧾",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
<style>
    /* API Settings Card */
    .api-card {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border: 1px solid #475569;
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
    }
    .api-status-ok {
        background: #064e3b;
        color: #34d399;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }
    .api-status-warning {
        background: #78350f;
        color: #fbbf24;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    /* Better input styling */
    .stTextInput > div > div > input {
        border-radius: 8px;
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
            'contract_value': 12000000.0,
            'items': [
                {'description': 'Brand Strategy', 'qty': 1, 'price': 5000000.0},
                {'description': 'Logo Design', 'qty': 1, 'price': 7000000.0}
            ],
            'payment_terms': 'Net 30',
            'due_date': '2025-01-10',
            'status': 'overdue',
            'created_at': '2024-12-10',
            'payments': [{'amount': 5000000.0, 'date': '2025-01-05', 'method': 'Bank Transfer', 'reference': 'TRF-001'}],
            'reminders_sent': 3
        },
        {
            'id': 1002,
            'client_name': 'Tech Innovations',
            'client_email': 'finance@techinno.com',
            'project_name': 'E-commerce Platform',
            'contract_value': 25000000.0,
            'items': [
                {'description': 'Platform Development', 'qty': 1, 'price': 20000000.0},
                {'description': 'Training', 'qty': 1, 'price': 5000000.0}
            ],
            'payment_terms': 'Net 45',
            'due_date': '2025-02-28',
            'status': 'paid',
            'created_at': '2025-01-01',
            'payments': [{'amount': 25000000.0, 'date': '2025-01-15', 'method': 'Wire Transfer', 'reference': 'WIR-4521'}],
            'reminders_sent': 0
        }
    ]

if 'extracted_data' not in st.session_state:
    st.session_state.extracted_data = None
if 'api_key' not in st.session_state:
    st.session_state.api_key = ""
if 'api_provider' not in st.session_state:
    st.session_state.api_provider = "OpenRouter"
if 'show_email_form' not in st.session_state:
    st.session_state.show_email_form = None

# Helper functions
def format_currency(amount):
    return f"Rp {float(amount):,.0f}".replace(",", ".")

def get_days_until_due(due_date):
    if not due_date:
        return 999
    due = datetime.strptime(due_date, '%Y-%m-%d')
    return (due - datetime.now()).days

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

def pdf_to_image(pdf_bytes):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2))
        return pix.tobytes("png")
    except Exception as e:
        return None

def send_email_reminder(to_email, invoice):
    """Send email via Gmail"""
    try:
        gmail_user = st.secrets.get("GMAIL_ADDRESS", "")
        gmail_password = st.secrets.get("GMAIL_APP_PASSWORD", "")
        
        if not gmail_user or not gmail_password:
            return False, "⚠️ Gmail belum dikonfigurasi. Tambahkan GMAIL_ADDRESS dan GMAIL_APP_PASSWORD di Streamlit secrets."
        
        remaining = float(invoice['contract_value']) - sum(float(p['amount']) for p in invoice.get('payments', []))
        days_overdue = abs(get_days_until_due(invoice['due_date']))
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Payment Reminder - Invoice #{invoice['id']} - {invoice['project_name']}"
        msg['From'] = gmail_user
        msg['To'] = to_email
        
        html = f"""
        <html>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #f8fafc;">
            <div style="background: linear-gradient(135deg, #10b981, #14b8a6); padding: 40px 30px; text-align: center; border-radius: 0 0 30px 30px;">
                <h1 style="color: white; margin: 0; font-size: 28px;">💰 Payment Reminder</h1>
            </div>
            <div style="padding: 40px 30px;">
                <p style="font-size: 16px; color: #334155;">Dear <strong>{invoice['client_name']}</strong>,</p>
                <p style="font-size: 16px; color: #334155;">This is a friendly reminder about your outstanding invoice:</p>
                
                <div style="background: white; padding: 25px; border-radius: 16px; margin: 25px 0; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #64748b;">Invoice Number</td>
                            <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; text-align: right; font-weight: 600;">#{invoice['id']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #64748b;">Project</td>
                            <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; text-align: right; font-weight: 600;">{invoice['project_name']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #64748b;">Due Date</td>
                            <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; text-align: right; font-weight: 600; color: #ef4444;">{invoice['due_date']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 16px 0; color: #64748b; font-size: 18px;">Amount Due</td>
                            <td style="padding: 16px 0; text-align: right; font-weight: 700; font-size: 24px; color: #10b981;">{format_currency(remaining)}</td>
                        </tr>
                    </table>
                </div>
                
                <div style="background: #fef2f2; border-left: 4px solid #ef4444; padding: 16px 20px; border-radius: 8px; margin: 20px 0;">
                    <p style="margin: 0; color: #991b1b; font-weight: 600;">⚠️ Invoice ini sudah overdue {days_overdue} hari.</p>
                </div>
                
                <p style="font-size: 16px; color: #334155;">Mohon segera melakukan pembayaran. Jika sudah melakukan pembayaran, abaikan email ini.</p>
                
                <p style="font-size: 16px; color: #334155; margin-top: 30px;">Best regards,<br><strong>Finance Team</strong></p>
            </div>
            <div style="background: #1e293b; padding: 20px; text-align: center; border-radius: 30px 30px 0 0;">
                <p style="color: #94a3b8; margin: 0; font-size: 12px;">Sent via InvoiceMatch ✨</p>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html, 'html'))
        
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, to_email, msg.as_string())
        server.quit()
        return True, "✅ Email berhasil dikirim!"
    except Exception as e:
        return False, f"❌ Gagal: {str(e)}"

def extract_with_ai(file_bytes, file_type):
    """Extract using AI"""
    api_key = st.session_state.api_key
    provider = st.session_state.api_provider
    
    if not api_key:
        st.error("⚠️ Masukkan API key dulu di sidebar!")
        return None
    
    try:
        if 'pdf' in file_type.lower():
            file_bytes = pdf_to_image(file_bytes)
            if not file_bytes:
                return None
            media_type = 'image/png'
        elif 'png' in file_type.lower():
            media_type = 'image/png'
        else:
            media_type = 'image/jpeg'
        
        base64_data = base64.standard_b64encode(file_bytes).decode('utf-8')
        
        prompt = """Extract invoice/contract data. Return ONLY valid JSON:
{"client_name":"","client_email":"","project_name":"","contract_value":0,"items":[{"description":"","qty":1,"price":0}],"payment_terms":"Net 30","due_date":"YYYY-MM-DD"}
Numbers without currency symbols. Return ONLY JSON."""
        
        if provider == "OpenRouter":
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://invoicematch.streamlit.app",
                    "X-Title": "InvoiceMatch"
                },
                json={
                    "model": "google/gemini-2.0-flash-001",
                    "messages": [{"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{base64_data}"}},
                        {"type": "text", "text": prompt}
                    ]}],
                    "max_tokens": 1024
                },
                timeout=60
            )
        else:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{base64_data}"}},
                        {"type": "text", "text": prompt}
                    ]}],
                    "max_tokens": 1024
                },
                timeout=60
            )
        
        if response.status_code == 429:
            st.error("❌ Rate limit! Tunggu sebentar atau ganti ke OpenRouter (gratis)")
            return None
        if response.status_code != 200:
            st.error(f"API Error {response.status_code}")
            return None
        
        text = response.json()['choices'][0]['message']['content'].strip()
        if '```' in text:
            for part in text.split('```'):
                if '{' in part:
                    text = part.replace('json', '').strip()
                    break
        
        start, end = text.find('{'), text.rfind('}') + 1
        if start != -1 and end > start:
            text = text[start:end]
        
        data = json.loads(text)
        val = str(data.get('contract_value', 0))
        val = ''.join(c for c in val if c.isdigit())
        data['contract_value'] = float(val) if val else 0
        return data
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None

# ============ SIDEBAR ============
with st.sidebar:
    st.markdown("## 🧾 InvoiceMatch")
    st.caption("AI-Powered Invoice Automation")
    
    st.divider()
    
    # API Settings - Clean collapsible design
    with st.expander("⚙️ API Settings", expanded=not st.session_state.api_key):
        st.markdown("##### AI Provider")
        provider = st.radio(
            "provider",
            ["OpenRouter", "OpenAI"],
            index=0,
            label_visibility="collapsed",
            horizontal=True
        )
        st.session_state.api_provider = provider
        
        if provider == "OpenRouter":
            st.caption("🆓 Gemini 2.0 Flash (Gratis!)")
            link = "https://openrouter.ai/keys"
            placeholder = "sk-or-v1-..."
        else:
            st.caption("💳 GPT-4o-mini (Berbayar)")
            link = "https://platform.openai.com/api-keys"
            placeholder = "sk-proj-..."
        
        api_key = st.text_input(
            "API Key",
            type="password",
            placeholder=placeholder,
            value=st.session_state.api_key,
            label_visibility="collapsed"
        )
        st.session_state.api_key = api_key
        
        st.markdown(f"[🔑 Dapatkan API Key]({link})")
    
    # API Status indicator
    if st.session_state.api_key:
        st.markdown('<span class="api-status-ok">✓ API Connected</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="api-status-warning">⚠ API Key Required</span>', unsafe_allow_html=True)
    
    st.divider()
    
    # Navigation
    page = st.radio("Menu", ["📊 Dashboard", "📄 Invoices", "➕ New Invoice"], label_visibility="collapsed")
    
    st.divider()
    st.caption("Contract in → Invoice out ✨")

# ============ DASHBOARD ============
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

# ============ INVOICES ============
elif page == "📄 Invoices":
    st.header("📄 All Invoices")
    
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
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📋 Details")
                st.write(f"**Client:** {inv['client_name']}")
                st.write(f"**Email:** {inv['client_email']}")
                st.write(f"**Project:** {inv['project_name']}")
                st.write(f"**Due Date:** {inv['due_date']}")
                if is_overdue:
                    st.error(f"⚠️ Overdue {abs(days_until)} hari!")
            
            with col2:
                st.subheader("💰 Payment")
                st.write(f"**Total:** {format_currency(inv['contract_value'])}")
                st.write(f"**Paid:** {format_currency(total_paid)}")
                st.write(f"**Remaining:** {format_currency(remaining)}")
                if remaining > 0 and float(inv['contract_value']) > 0:
                    st.progress(total_paid / float(inv['contract_value']))
            
            st.divider()
            
            # ========== ACTIONS ==========
            st.subheader("⚡ Actions")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # SEND REMINDER with email edit
                if remaining > 0 and inv['status'] != 'draft':
                    if st.button("📧 Send Reminder", use_container_width=True):
                        st.session_state.show_email_form = inv['id']
                    
                    # Show email edit form
                    if st.session_state.show_email_form == inv['id']:
                        st.markdown("---")
                        st.markdown("##### 📧 Kirim Reminder")
                        
                        with st.form(key=f"email_form_{inv['id']}"):
                            email_to = st.text_input(
                                "Email Tujuan",
                                value=inv['client_email'],
                                help="Periksa email sebelum mengirim"
                            )
                            
                            st.caption(f"📝 Invoice #{inv['id']} - {inv['project_name']}")
                            st.caption(f"💰 Amount: {format_currency(remaining)}")
                            
                            col_send, col_cancel = st.columns(2)
                            with col_send:
                                send_btn = st.form_submit_button("📤 Kirim", use_container_width=True)
                            with col_cancel:
                                cancel_btn = st.form_submit_button("❌ Batal", use_container_width=True)
                            
                            if send_btn:
                                with st.spinner("Mengirim email..."):
                                    # Update email if changed
                                    inv['client_email'] = email_to
                                    success, msg = send_email_reminder(email_to, inv)
                                    if success:
                                        inv['reminders_sent'] = inv.get('reminders_sent', 0) + 1
                                        st.success(f"✅ Email terkirim ke {email_to}!")
                                        st.session_state.show_email_form = None
                                        st.rerun()
                                    else:
                                        st.error(msg)
                            
                            if cancel_btn:
                                st.session_state.show_email_form = None
                                st.rerun()
                
                # APPROVE
                if inv['status'] == 'draft':
                    if st.button("✅ Approve & Send", use_container_width=True):
                        inv['status'] = 'sent'
                        st.success("✅ Approved!")
                        st.rerun()
            
            with col2:
                st.metric("Reminders Sent", inv.get('reminders_sent', 0))
            
            # RECORD PAYMENT
            if remaining > 0 and inv['status'] != 'draft':
                st.divider()
                st.subheader("💳 Record Payment")
                with st.form(key=f"pay_{inv['id']}"):
                    amt = st.number_input("Amount (Rp)", value=remaining, min_value=0.0, max_value=remaining, step=100000.0)
                    method = st.selectbox("Method", ["Bank Transfer", "Wire", "Credit Card", "PayPal", "Cash"])
                    ref = st.text_input("Reference", placeholder="TRF-001")
                    if st.form_submit_button("💰 Record Payment", use_container_width=True):
                        inv.setdefault('payments', []).append({
                            'amount': float(amt), 'date': datetime.now().strftime('%Y-%m-%d'),
                            'method': method, 'reference': ref
                        })
                        if sum(float(p['amount']) for p in inv['payments']) >= float(inv['contract_value']):
                            inv['status'] = 'paid'
                        st.success(f"💰 {format_currency(amt)} recorded!")
                        st.balloons()
                        st.rerun()
            
            # PAYMENT HISTORY
            if inv.get('payments'):
                st.divider()
                st.subheader("📜 Payment History")
                st.dataframe(pd.DataFrame([{
                    'Date': p['date'], 'Amount': format_currency(p['amount']),
                    'Method': p['method'], 'Reference': p['reference']
                } for p in inv['payments']]), use_container_width=True, hide_index=True)

# ============ NEW INVOICE ============
elif page == "➕ New Invoice":
    st.header("➕ Create New Invoice")
    
    if not st.session_state.api_key:
        st.warning("⚠️ Masukkan API key di sidebar untuk menggunakan AI extraction!")
    else:
        st.success(f"✅ {st.session_state.api_provider} connected")
    
    st.info("🤖 Upload invoice/contract - AI akan extract datanya!")
    
    uploaded = st.file_uploader("Upload Document", type=['pdf', 'png', 'jpg', 'jpeg', 'webp'])
    
    if uploaded:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📄 Preview")
            if 'pdf' in uploaded.type:
                st.caption(f"📄 {uploaded.name}")
                try:
                    pdf_bytes = uploaded.read()
                    uploaded.seek(0)
                    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                    pix = doc[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                    st.image(pix.tobytes("png"), use_container_width=True)
                except:
                    st.warning("Preview tidak tersedia")
            else:
                st.image(uploaded, use_container_width=True)
        
        with col2:
            st.subheader("🤖 AI Extraction")
            
            if st.button("🚀 Extract with AI", type="primary", use_container_width=True, disabled=not st.session_state.api_key):
                with st.spinner("🤖 Membaca dokumen..."):
                    file_bytes = uploaded.read()
                    result = extract_with_ai(file_bytes, uploaded.type)
                    if result:
                        st.session_state.extracted_data = result
                        st.success("✅ Data berhasil diextract!")
            
            if st.session_state.extracted_data:
                data = st.session_state.extracted_data
                st.divider()
                
                with st.form("new_inv"):
                    st.subheader("✏️ Review & Edit")
                    client = st.text_input("Client", value=data.get('client_name', ''))
                    email = st.text_input("Email", value=data.get('client_email', ''))
                    project = st.text_input("Project", value=data.get('project_name', ''))
                    amount = st.number_input("Amount (Rp)", value=float(data.get('contract_value', 0)), step=100000.0)
                    terms = st.selectbox("Terms", ["Net 7", "Net 14", "Net 30", "Net 45"], index=2)
                    due = st.date_input("Due Date", value=datetime.now() + timedelta(days=30))
                    
                    if data.get('items'):
                        st.write("**Items:**")
                        st.dataframe(pd.DataFrame(data['items']), hide_index=True)
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        draft = st.form_submit_button("📝 Save Draft", use_container_width=True)
                    with c2:
                        send = st.form_submit_button("✅ Approve", use_container_width=True)
                    
                    if draft or send:
                        new = {
                            'id': max([i['id'] for i in st.session_state.invoices], default=1000) + 1,
                            'client_name': client, 'client_email': email, 'project_name': project,
                            'contract_value': float(amount), 'items': data.get('items', []),
                            'payment_terms': terms, 'due_date': due.strftime('%Y-%m-%d'),
                            'status': 'sent' if send else 'draft',
                            'created_at': datetime.now().strftime('%Y-%m-%d'),
                            'payments': [], 'reminders_sent': 0
                        }
                        st.session_state.invoices.append(new)
                        st.session_state.extracted_data = None
                        st.success("✅ Tersimpan!" if draft else f"✅ Invoice dibuat!")
                        st.balloons()
                        st.rerun()

st.divider()
st.caption("InvoiceMatch ✨ AI-Powered Invoice Automation")
