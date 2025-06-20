# app.py
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
import json
import os

app = Flask(__name__)
CORS(app) # Enable CORS for cross-origin requests from your frontend

# IMPORTANT: For security, never hardcode your API key in production.
# Use environment variables or a secure configuration management system.
GEMINI_API_KEY = "AIzaSyBJ3cFd100yNCi6GLZk4U621iWcfKxAW38" # User provided API key

@app.route('/')
def index():
    """Render the main HTML page."""
    return render_template('index.html')

@app.route('/analyze_market', methods=['POST'])
def analyze_market_endpoint():
    """
    Endpoint to get AI-powered comparative market analysis, including an "Opportunity Score"
    for multiple assets (crypto and gold), fetching real-time crypto prices,
    and analyzing uploaded charts.
    """
    data = request.json
    if not data:
        return jsonify({"error": "No input data provided"}), 400

    # New: Handle multiple crypto IDs
    crypto_ids = data.get('cryptoIds', [])
    crypto_market_news = data.get('cryptoMarketNews', '').strip()
    gold_market_news = data.get('goldMarketNews', '').strip()
    chart_image_base64 = data.get('chartImageBase64', '').strip()

    # Dictionary to hold crypto data (name, price)
    crypto_assets_data = []

    # 1. Fetch real-time crypto prices for all selected cryptos
    if crypto_ids:
        ids_string = ",".join(crypto_ids)
        crypto_price_api_url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids_string}&vs_currencies=usd"
        try:
            crypto_response = requests.get(crypto_price_api_url)
            crypto_response.raise_for_status()
            crypto_data = crypto_response.json()
            for crypto_id in crypto_ids:
                if crypto_id in crypto_data and 'usd' in crypto_data[crypto_id]:
                    price = crypto_data[crypto_id]['usd']
                    name = crypto_id.replace('-', ' ').title()
                    crypto_assets_data.append({"id": crypto_id, "name": name, "price": price})
                else:
                    app.logger.warning(f"Could not find USD price for crypto ID: {crypto_id}")
                    # Still add it to the list for news-based analysis
                    crypto_assets_data.append({"id": crypto_id, "name": crypto_id.title(), "price": None})
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Error fetching crypto prices from CoinGecko: {e}")
            # Populate with no price data if API fails
            for crypto_id in crypto_ids:
                 crypto_assets_data.append({"id": crypto_id, "name": crypto_id.title(), "price": None})


    # 2. Construct the new, advanced prompt for Gemini AI
    prompt_parts = [
        "Anda adalah seorang analis keuangan kuantitatif elite di sebuah hedge fund. Tugas Anda adalah melakukan analisis komparatif pada beberapa aset yang diberikan (cryptocurrency, emas) untuk menentukan peluang investasi terbaik saat ini.",
        "Input yang Anda terima bisa berupa data harga real-time, berita pasar, dan/atau gambar grafik harga.",
        "Output Anda HARUS dalam format JSON yang ketat dan tidak boleh menyertakan teks lain di luar JSON. JSON harus memiliki dua kunci utama: 'ranked_assets' dan 'detailed_analysis'.",
        
        "\n--- DATA INPUT UNTUK ANALISIS ---"
    ]

    # Add crypto data to prompt
    if crypto_assets_data:
        prompt_parts.append("\n**Aset Cryptocurrency:**")
        for asset in crypto_assets_data:
            price_info = f"${asset['price']}" if asset['price'] is not None else "(harga tidak tersedia)"
            prompt_parts.append(f"- {asset['name']}: Harga saat ini {price_info}")
        if crypto_market_news:
            prompt_parts.append(f"\n**Konteks Berita/Tren Umum Crypto:**\n{crypto_market_news}")

    # Add gold data to prompt
    if gold_market_news:
        prompt_parts.append("\n**Aset Emas:**")
        prompt_parts.append("- Konteks Berita/Tren Pasar Emas:")
        prompt_parts.append(gold_market_news)
    
    # Add chart context to prompt
    if chart_image_base64:
        prompt_parts.append("\n**Konteks Tambahan dari Grafik Harga:**")
        prompt_parts.append("Sebuah grafik harga (chart) juga dilampirkan. Gunakan analisis teknis dari grafik ini (pola, indikator, volume) sebagai salah satu faktor utama dalam penilaian Anda untuk SEMUA aset yang relevan.")

    # Add instruction for the JSON output structure
    prompt_parts.extend([
        "\n\n--- TUGAS DAN FORMAT OUTPUT JSON ---",
        "1.  **Untuk kunci 'ranked_assets':**",
        "    - Buat sebuah array JSON.",
        "    - Untuk SETIAP aset yang diinput (termasuk Emas jika ada beritanya), buat sebuah objek JSON dengan field berikut:",
        "      - `asset_name`: (string) Nama aset (e.g., 'Bitcoin', 'Ethereum', 'Emas').",
        "      - `current_price`: (number or null) Harga saat ini, atau null jika tidak tersedia.",
        "      - `score`: (number) 'Opportunity Score' dari 0-100. Skor ini mencerminkan potensi keuntungan (upside) vs. risiko saat ini. Skor tinggi = peluang beli yang kuat. Skor rendah = sinyal jual atau hindari.",
        "      - `strategy`: (string) Rekomendasi strategi yang jelas: 'BUY', 'SELL', atau 'HOLD'.",
        "      - `holding_period`: (string) Estimasi durasi trading yang disarankan untuk strategi ini. Jika peluang terbaik adalah untuk scalping, gunakan format waktu sangat singkat (misal: 'Scalping (5-30 menit)', 'Scalping (15-60 menit)', atau 'Scalping (1-3 jam)'). Jangan gunakan istilah 'jangka pendek' untuk scalping.",
        "      - `reason`: (string) Satu kalimat ringkas dan kuat yang menjadi alasan utama skor tersebut. Contoh: 'Baru saja menembus level resistance kuat didukung volume tinggi.' atau 'Tertekan oleh sentimen pasar negatif dari berita regulasi.'",
        "    - Urutkan array ini dari skor tertinggi ke terendah.",

        "\n2.  **Untuk kunci 'detailed_analysis':**",
        "    - Tulis analisis mendalam dalam format teks Markdown yang terstruktur dan rapi.",
        "    - Awali dengan ringkasan perbandingan umum.",
        "    - Untuk setiap aset, buat bagian terpisah menggunakan heading Markdown (e.g., `### Analisis Mendalam: Bitcoin`).",
        "    - Di dalam setiap bagian aset, gunakan sub-heading (e.g., `#### Analisis Teknikal (Grafik):`, `#### Analisis Fundamental (Berita & Sentimen):`, `#### Skenario & Risiko:`) untuk memecah analisis Anda.",
        "    - Tambahkan sub-heading khusus: `#### Rekomendasi Scalping (Entry, Exit, SL, TP, Logika, Risiko):` yang berisi:",
        "        - Level entry, exit, stop loss, dan take profit yang direkomendasikan (jika memungkinkan).",
        "        - Penjelasan logika teknikal (support/resistance, candlestick, volume, dsb) yang relevan untuk scalping.",
        "        - Tips manajemen risiko/modal untuk scalper.",
        "    - Penjelasan harus sangat detail, logis, dan menghubungkan semua data input (harga, berita, grafik).",
        "    - Akhiri dengan kesimpulan strategis menyeluruh dan disclaimer investasi.",
        
        "\nContoh output JSON yang Anda berikan:",
        """
        {
          "ranked_assets": [
            {
              "asset_name": "Solana",
              "current_price": 150.25,
              "score": 85,
              "strategy": "BUY",
              "holding_period": "Scalping (15-30 menit)",
              "reason": "Volume tinggi di area support, peluang scalping dengan risk-reward menarik."
            }
          ],
          "detailed_analysis": "### Analisis Mendalam: Solana\\n#### Analisis Teknikal (Grafik):\\n...\\n#### Rekomendasi Scalping (Entry, Exit, SL, TP, Logika, Risiko):\\n- Entry: 150.10\\n- Exit: 150.60\\n- Stop Loss: 149.80\\n- Take Profit: 150.80\\nLogika: Breakout volume tinggi di support, candlestick reversal.\\nRisiko: Hindari over-leverage, gunakan trailing stop jika volatilitas tinggi."
        }
        """,
        "\nPastikan JSON Anda valid. Mulai respons Anda dengan `{` dan akhiri dengan `}`. Jangan tambahkan '```json' atau komentar lain di luar objek JSON."
    ])

    # Add new features to prompt
    prompt_parts.extend([
        "\n\n--- FITUR TAMBAHAN YANG WAJIB ADA DI OUTPUT JSON ---",
        "3.  **Multi-Timeframe Analysis:**",
        "    - Tambahkan kunci baru 'multi_timeframe_analysis' (array) di JSON output.",
        "    - Untuk setiap timeframe berikut, buat objek dengan field: 'timeframe' (string, misal: 'Scalping (1-5 menit)', 'Intraday (15-60 menit)', 'Swing (4 jam - harian)'), 'signal' (BUY/SELL/HOLD/NETRAL), 'risk' (tinggi/sedang/rendah), dan 'reason' (penjelasan teknikal/sentimen utama).",
        "    - Contoh:",
        "      [",
        "        { 'timeframe': 'Scalping (1-5 menit)', 'signal': 'BUY', 'risk': 'tinggi', 'reason': 'Breakout volume tinggi di support.' },",
        "        { 'timeframe': 'Intraday (15-60 menit)', 'signal': 'HOLD', 'risk': 'sedang', 'reason': 'Harga konsolidasi, belum ada sinyal kuat.' },",
        "        { 'timeframe': 'Swing (4 jam - harian)', 'signal': 'SELL', 'risk': 'tinggi', 'reason': 'Divergensi RSI dan pola reversal.' }",
        "      ]",
        "4.  **Pattern Recognition Otomatis:**",
        "    - Jika ada gambar chart, deteksi pola populer (double top, head & shoulders, triangle, engulfing, dsb) dan tambahkan kunci baru 'pattern_recognition' (array) di JSON output.",
        "    - Untuk setiap pola yang terdeteksi, buat objek dengan field: 'pattern' (nama pola), 'confidence' (tingkat keyakinan AI, 0-100), dan 'description' (implikasi pola tsb).",
        "    - Contoh:",
        "      [",
        "        { 'pattern': 'Bullish Engulfing', 'confidence': 90, 'description': 'Potensi reversal naik kuat.' },",
        "        { 'pattern': 'Head & Shoulders', 'confidence': 75, 'description': 'Sinyal pembalikan tren turun.' }",
        "      ]",
        "    - Jika tidak ada pola jelas, tulis array kosong atau beri pesan 'Tidak ada pola signifikan terdeteksi.'",
        "\nPastikan semua kunci baru ('multi_timeframe_analysis', 'pattern_recognition') ada di JSON output utama bersama kunci lain yang sudah ada.",
    ])

    # Construct content for Gemini API call
    contents = []
    # Add text parts first
    contents.append({"role": "user", "parts": [{"text": "".join(prompt_parts)}]})

    # Add image part if available
    if chart_image_base64:
        contents.append({
            "role": "user",
            "parts": [{
                "inlineData": {
                    "mimeType": "image/png", # Assuming PNG, or you can detect based on magic bytes or frontend info
                    "data": chart_image_base64
                }
            }]
        })

    # 3. Call Gemini API
    try:
        payload = {"contents": contents} # Use the combined contents
        gemini_api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

        gemini_response = requests.post(gemini_api_url, headers={'Content-Type': 'application/json'}, json=payload)
        gemini_response.raise_for_status()

        gemini_result = gemini_response.json()

        if gemini_result.get("candidates") and gemini_result["candidates"][0].get("content") and \
           gemini_result["candidates"][0]["content"].get("parts") and gemini_result["candidates"][0]["content"]["parts"][0].get("text"):
            
            raw_text = gemini_result["candidates"][0]["content"]["parts"][0]["text"]
            
            # Clean the response to ensure it's valid JSON
            # Find the first '{' and the last '}'
            start = raw_text.find('{')
            end = raw_text.rfind('}')
            if start != -1 and end != -1:
                json_text = raw_text[start:end+1]
                try:
                    # Parse the JSON string into a Python dictionary
                    analysis_data = json.loads(json_text)
                    
                    # Add current prices to the ranked_assets if they are not included by the AI
                    if 'ranked_assets' in analysis_data:
                        for asset in analysis_data['ranked_assets']:
                            # Find the corresponding crypto data we fetched
                            for crypto in crypto_assets_data:
                                if asset.get('asset_name', '').lower() == crypto.get('name', '').lower():
                                    asset['current_price'] = crypto.get('price')
                                    break

                    return jsonify(analysis_data), 200
                except json.JSONDecodeError as e:
                    app.logger.error(f"Failed to parse JSON from AI response: {e}")
                    app.logger.error(f"Raw AI response was: {raw_text}")
                    return jsonify({"error": "Gagal mem-parsing respons dari AI. Respons tidak dalam format JSON yang valid."}), 500
            else:
                app.logger.error(f"Could not find valid JSON object in AI response. Raw response: {raw_text}")
                return jsonify({"error": "Tidak menemukan objek JSON dalam respons AI."}), 500
        else:
            return jsonify({"error": "Failed to generate analysis: AI response empty or ill-structured"}), 500

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error calling Gemini API: {e}")
        return jsonify({"error": f"Failed to connect to AI or an error occurred: {str(e)}"}), 500
    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {e}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    # The host '0.0.0.0' makes the server publicly available.
    # For development, you can run with debug=True.
    # For production, use a proper WSGI server like Gunicorn.
    app.run(host='0.0.0.0', port=5000, debug=True)
