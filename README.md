# J.A.R.V.I.S. - Advanced AI Ecosystem 🧠 
*(🇹🇷 Türkçe açıklamalar aşağıdadır / Turkish description is below)*

An advanced, highly autonomous AI desktop assistant powered by Google's Gemini multimodal capabilities. JARVIS is not just a chatbot; it is a fully integrated ecosystem capable of voice biometrics, system administration, network diagnostics, computer vision, and real-time market analysis.

## 🌟 Comprehensive Features

### 🎙️ 1. Voice Biometrics Security (ECAPA-TDNN)
- **Master Enrollment:** Learns your unique voiceprint through a 10-sentence enrollment process.
- **Biometric Firewall:** Highly sensitive commands (e.g., system optimization, deleting memory, shell execution) are locked behind a biometric wall.
- **Dynamic Thresholding:** Uses advanced background noise filtering (VAD) and auto-calibrated thresholds to verify if the speaker is actually the owner before executing a restricted command.

### 📝 2. Second Brain & Smart Notes (PKM)
- **NLP Auto-Tagging:** Speak your thoughts naturally. JARVIS automatically extracts categories (work, personal, etc.), tags, priorities, and deadlines.
- **Markdown Export:** Saves notes as fully searchable `.md` files with Obsidian/Notion compatible YAML Frontmatter.
- **Semantic Retrieval:** Ask JARVIS to find past notes about specific topics, and it will list or read them to you.

### 📈 3. Live Market Intelligence
- **Real-Time Data:** Tracks BIST 100 (Istanbul Stock Exchange), Bitcoin, Ethereum, Gold (Gram/Ons), USD/TRY, and EUR/TRY.
- **Zero Delay:** Uses Yahoo Finance's live API (`t.info`) to bypass standard 15-minute delays, refreshing the HUD every 60 seconds autonomously.

### 🌐 4. Network Diagnostics (SysAdmin)
- **Bandwidth & Latency:** Can run background `speedtest-cli` to check your download/upload speeds and `ping` specific servers.
- **Troubleshooting:** Traces network routes (`traceroute`) to find bottlenecks and can autonomously flush your DNS (`ipconfig /flushdns`) and renew your IP to fix internet issues.

### 👁️ 5. Computer Vision & OS Control
- **Screen Analysis:** Can take a screenshot of your active window and use Gemini Vision to read errors, analyze code, or describe the UI.
- **System Optimizer:** Flushes background RAM and optimizes system memory upon a biometric-secured command.
- **Clipboard & Automation:** Can read your clipboard, type text, and interact with the OS.

### 🧠 6. Persistent Memory & Identity
- Remembers your preferences, identity, and past conversations permanently using local JSON storage. 
- Avoids repetitive daily greetings by tracking the last boot date.

### 🤖 7. Complete OS Automation & Control
- **App & Shell Control:** Can open any application, run PowerShell scripts, type text, and simulate keyboard/mouse inputs.
- **Power Management:** Can put your PC to sleep, restart, or shut it down (Biometric secured).
- **Media Control:** Can play/pause media, adjust system volume, or directly play music on YouTube (`youtube_play`).

### 🌍 8. Web Intelligence & Communication
- **Web Search:** Can search the internet for real-time information if it doesn't know the answer.
- **WhatsApp Integration:** Can send WhatsApp messages to your contacts automatically (Biometric secured).

### 🎙️ 9. Wake Word & Always-On Listening
- **Porcupine Wake Word:** Runs seamlessly in the background and activates instantly when you say "Jarvis".
- **Dynamic Neural UI:** The UI dynamically shifts states (Listening, Thinking, Speaking) with a sleek cyberpunk aesthetic.

### 🗣️ 10. Native English Speaking Tutor
- **Language Practice:** Functions as an advanced, zero-latency English conversation partner.
- **Real-time Feedback:** Can detect your pronunciation, hold natural conversations in English, and dynamically correct your grammar or vocabulary mistakes just like a native teacher.

## 🚀 Installation
1. Clone the repository: `git clone https://github.com/beratxkeskin/jarvis.git`
2. Install dependencies: `pip install -r requirements.txt` (Requires `pyaudio`, `speechbrain`, `yfinance`, `speedtest-cli`, `psutil`)
3. Set up your API key: Rename `config/api_keys.example.json` to `api_keys.json` and insert your Gemini API Key.
4. Run the assistant: `python main.py`

---

# J.A.R.V.I.S. - Gelişmiş Yapay Zeka Ekosistemi 🧠

Google Gemini'nin çok modlu (multimodal) altyapısıyla güçlendirilmiş, son derece otonom ve gelişmiş bir masaüstü yapay zeka asistanı. JARVIS sadece bir sohbet botu değil; ses biyometrisi, sistem yönetimi, ağ tanılama, bilgisayarlı görü ve anlık piyasa analizi yapabilen tam entegre bir ekosistemdir.

## 🌟 Kapsamlı Özellikler

### 🎙️ 1. Ses Biyometrisi Güvenliği (ECAPA-TDNN)
- **Özel Ses Kaydı (Voiceprint):** 10 cümlelik özel bir kayıt süreciyle gırtlak frekansınızı ve tınınızı öğrenir.
- **Biyometrik Güvenlik Duvarı:** Sistemi optimize etme, hafıza silme veya kritik komut çalıştırma gibi eylemler kilitlidir. Komut verilmeden önce konuşanın **gerçekten siz olup olmadığını** analiz eder.
- **Arka Plan Gürültü Filtresi (VAD):** Çevresel sesleri yalıtarak sadece sizin sesinize odaklanan dinamik bir eşik (threshold) sistemi kullanır.

### 📝 2. İkinci Beyin & Akıllı Notlar (PKM)
- **Otonom Etiketleme:** Siz sadece doğal bir şekilde konuşun. JARVIS cümlenizdeki kategoriyi (iş, kişisel), etiketleri, önceliği ve tarihleri NLP (Doğal Dil İşleme) ile otomatik ayıklar.
- **Markdown Entegrasyonu:** Tüm notları Obsidian ve Notion gibi modern uygulamalarla uyumlu YAML Frontmatter destekli `.md` (Markdown) dosyaları olarak kaydeder.
- **Akıllı Arama:** Eski notlarınızı saniyeler içinde konu başlıklarına veya etiketlere göre filtreleyip bulabilir.

### 📈 3. Canlı Piyasa Zekası (Market Intelligence)
- **Gerçek Zamanlı Takip:** BIST 100, Bitcoin, Ethereum, Altın (Gram/Ons) ve Döviz kurlarını anlık takip eder.
- **Gecikmesiz Veri:** Yahoo Finance'in standart 15 dakikalık gecikmesini aşarak doğrudan anlık fiyat API'sini (`t.info`) kullanır ve HUD ekranını her 60 saniyede bir otomatik günceller.

### 🌐 4. Ağ Tanılama ve Analiz (SysAdmin)
- **Hız ve Gecikme Testi:** Arka planda `speedtest-cli` çalıştırarak anlık indirme/yükleme hızınızı ölçer ve Google sunucularına ping atarak gecikmenizi raporlar.
- **Otonom Sorun Çözme:** İnternetiniz yavaşladığında darboğazı bulmak için `traceroute` yapar. *"İnternetim koptu"* dediğinizde otonom olarak DNS önbelleğinizi temizler (`flushdns`) ve IP'nizi yeniler.

### 👁️ 5. Bilgisayarlı Görü (Computer Vision) ve OS Kontrolü
- **Ekran Analizi:** Aktif pencerenizin ekran görüntüsünü alıp Gemini Vision modeliyle okuyabilir. Ekranda çıkan bir hata kodunu veya yazılımı sizin yerinize inceleyebilir.
- **Sistem Optimizasyonu:** Biyometrik onayınızla birlikte arka plandaki gereksiz RAM bloklarını temizler.
- **Otomasyon:** Panonuzu (clipboard) okuyabilir, uygulamaları açabilir ve takviminizi yönetebilir.

### 🧠 6. Kalıcı Hafıza ve Kişilik
- Sizin tercihlerinizi, projelerinizi ve kimliğinizi kalıcı JSON belleğinde tutarak her geçen gün sizi daha iyi tanır.
- Gereksiz sabah özetlerinden kaçınmak için oturum açılış tarihlerini takip eder.

### 🤖 7. İşletim Sistemi Otomasyonu (OS Control)
- **Klavye/Mouse Simülasyonu:** İstediğiniz uygulamayı açabilir, PowerShell komutları çalıştırabilir, sizin yerinize metin yazabilir.
- **Güç Yönetimi:** Bilgisayarınızı sesli komutla uyku moduna alabilir veya kapatabilir (Biyometrik Güvenlikli).
- **Medya Kontrolü:** Sesi kısıp açabilir, müziği durdurabilir veya YouTube'dan doğrudan istediğiniz bir şarkıyı açabilir (`youtube_play`).

### 🌍 8. Web Zekası ve İletişim
- **Canlı İnternet Taraması:** Cevabını bilmediği güncel konularda anlık olarak Google üzerinde arama yapabilir ve sonuçları özetler.
- **WhatsApp Entegrasyonu:** Rehberinizdeki kişilere doğrudan WhatsApp üzerinden otonom mesaj gönderebilir (Biyometrik Güvenlikli).

### 🎙️ 9. Uyanma Kelimesi (Wake Word)
- **7/24 Arka Plan Dinleme:** Yalnızca *"Jarvis"* dediğinizde saniyesinde aktif olur (Picovoice Porcupine altyapısı ile).
- **Dinamik UI Tepkileri:** Jarvis'in o an sizi dinlediğini, düşündüğünü veya işlem yaptığını arayüzdeki şık siberpunk animasyonlarla takip edebilirsiniz.

### 🗣️ 10. Native İngilizce Pratik Eğitmeni (Speaking Partner)
- **Sıfır Gecikmeli Sohbet:** Gemini'nin sesli model gücünü kullanarak sizinle ana dili İngilizce olan biri gibi akıcı bir şekilde sohbet edebilir.
- **Anlık Geri Bildirim:** Telaffuzunuzu analiz eder, kelime dağarcığınızı geliştirir ve İngilizce konuşma pratiği yaparken dilbilgisi hatalarınızı zarifçe düzelten bir öğretmen gibi davranabilir.

## 🚀 Kurulum
1. Projeyi klonlayın: `git clone https://github.com/beratxkeskin/jarvis.git`
2. Gereksinimleri yükleyin: `pip install -r requirements.txt`
3. API Anahtarınızı girin: `config/api_keys.example.json` dosyasının adını `api_keys.json` yapın ve Gemini API anahtarınızı ekleyin.
4. Asistanı başlatın: `python main.py`
