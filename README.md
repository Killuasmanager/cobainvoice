# 🧾 InvoiceMatch - AI Invoice Automation

Contract in → Invoice out. Automatically!

## 🚀 Deploy dalam 5 Menit!

### Step 1: Dapat OpenRouter API Key (GRATIS!)

1. Buka [openrouter.ai](https://openrouter.ai)
2. Sign up (bisa pakai Google)
3. Dapat **FREE credits** otomatis!
4. Klik **"Keys"** → **"Create Key"**
5. Copy API key (mulai dengan `sk-or-...`)

### Step 2: Upload ke GitHub

1. Buat repo baru di GitHub
2. Upload 2 file ini:
   - `app.py`
   - `requirements.txt`

### Step 3: Deploy ke Streamlit Cloud

1. Buka [share.streamlit.io](https://share.streamlit.io)
2. Login dengan GitHub
3. Klik **"New app"**
4. Pilih repo kamu
5. Main file: `app.py`
6. Klik **"Advanced settings"**
7. Di **Secrets**, tambah:

```toml
OPENROUTER_API_KEY = "sk-or-PASTE-KEY-KAMU-DISINI"
```

8. Klik **"Deploy!"**
9. Tunggu 2-3 menit
10. ✅ DONE!

## ✨ Features

- 📄 AI Document Extraction (Claude via OpenRouter)
- ✅ Approval Workflow
- 💰 Payment Tracking
- 📧 Payment Reminders
- 📊 Dashboard Analytics

## 💰 Biaya

| Model | Harga |
|-------|-------|
| Claude 3.5 Sonnet | ~$3/1M tokens |
| Gemini Flash | FREE! |
| Llama 3.2 Vision | FREE! |

**Tips:** Ubah model di `app.py` ke model gratis:
```python
"model": "google/gemini-flash-1.5"  # FREE!
# atau
"model": "meta-llama/llama-3.2-11b-vision-instruct:free"  # FREE!
```

## 🎬 Demo Flow

1. Dashboard → Lihat stats
2. New Invoice → Upload kontrak
3. Extract with AI → Data muncul
4. Approve & Send → Auto kirim
5. Invoices → Record payment, send reminder

---
Built with ❤️ and AI
