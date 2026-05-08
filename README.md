<div align="center">
  <a href="#english">🇺🇸 English</a> | <a href="#turkce">🇹🇷 Türkçe</a>
</div>

<a id="english"></a>
# CSC - CtfShitCli v3.0

The ultimate CTFd Swiss Army Knife CLI designed for security researchers, CTF competitors, and team leads. Stop navigating clunky web interfaces during time-critical events—manage your entire CTF workflow directly from the terminal.

![Version](https://img.shields.io/badge/version-v3.0-blue?style=for-the-badge)
![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)
![Python](https://img.shields.io/badge/python-3.9%2B-blue?style=for-the-badge)
![Click](https://img.shields.io/badge/click-8.1%2B-orange?style=for-the-badge)

## 🚀 Core Modules & Features

### 🧠 Autonomous AI Analyzer (`ctf ai`)
When you are stuck on a challenge, deploy the Red Team AI Assistant. Run `ctf ai analyze` inside a challenge directory, and the agent will automatically read your source codes and `challenge.txt` description. It discovers the best available Gemini model for your API key, bypasses rate-limits via fallback loops, and generates a cyberpunk-themed, professional vulnerability analysis and exploitation strategy report directly in your terminal.

### 📜 Universal Script Generator (`ctf script`)
Stop rewriting the same boilerplate code for every competition! The Script Generator provides an arsenal of categorized, ready-to-use scripts:
- **Web:** Blind SQLi payloads, JWT Forgers, Padding Oracle scripts, SSTI Payload Generators.
- **Crypto:** RSA solvers, Z3 Theorem Provers, AES ECB Oracle Exploiters.
- **Pwn:** Standard `ret2libc` ROP skeletons using `pwntools`.
- **Forensics:** PCAP HTTP & DNS extractors using `scapy`.
- **OSINT:** Cross-platform username recon & enumeration scripts.
- **Stego:** LSB Extractors, Exif parsers.
Run `ctf script list` to see categories, and `ctf script generate <name>` to drop the solver into your current directory.

### 👁️ Watchdog & Auto Submitter (`ctf watch`)
Never worry about submitting flags manually again. The daemon runs in the background and watches your workspace for any `flag.txt` creation. It dynamically uses your custom `flag_format` (set via `ctf set flag_format CTF{}`) to parse the flag using regex, submits it to the CTFd API, logs the attempt locally, and can even trigger a **Discord Webhook** notification to alert your team!

### 📥 Smart Downloader & Password Cracker (`ctf pull`)
Downloading attachments is now fully asynchronous and safe against zip-slip path traversal attacks. Even better: if a zip file is password protected and the challenge description contains the password (e.g., "Password: 1234"), `ctf pull --extract` automatically extracts the password via Regex and unlocks the archive for you.

### 🏗️ Deterministic Workspace Manager
- **`ctf init`:** Initializes a local SQLite cache and `.ctf_config.json`.
- **`ctf set`:** Dynamically update your configurations like `ctf set flag_format CTF{}` or `ctf set llm_api_key AIza...` without touching files.
- **`ctf add`:** Instantly scaffold a challenge directory (`web/easy-sqli`) with a clean `challenge.txt` setup, ready for action.

### 📊 Live Tracking & Reporting
- **`ctf track`:** Launch a live scoreboard polling tracker in your terminal.
- **`ctf export writeups`:** Compile all your solved challenges and scripts into a single, beautifully formatted `writeups.md` file for your blog or GitHub.

## 📦 Installation

```bash
git clone https://github.com/MacallanTheRoot/CSL-CtfShitCli.git
cd CSL-CtfShitCli

python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -e .
```

## 🎮 CLI Reference

| Command | Description |
|---|---|
| `ctf init <url>` | Initialize a new workspace directory for an event. |
| `ctf add <cat/name>` | Scaffold a challenge directory. |
| `ctf list [--offline]` | List challenges (grouped or flat), optionally from cache. |
| `ctf pull [--all] [--extract]` | Download and safely extract challenge file attachments. |
| `ctf submit <flag>` | Submit a flag (auto-detects challenge ID). |
| `ctf bulk <csv>` | Bulk-submit flags from a CSV file. |
| `ctf hint list <id>` | List hints for a specific challenge. |
| `ctf hint unlock <id>` | Unlock a specific hint. |
| `ctf submissions <id>` | View your local flag submission history. |
| `ctf export writeups` | Export all solved challenges to a single Markdown file. |
| `ctf script list` | List built-in CTF automation and solver scripts. |
| `ctf script generate <name>` | Generate an automation script in the cwd. |
| `ctf ai analyze` | Autonomous vulnerability and code analysis using LLM. |
| `ctf watch [--all]` | Monitor `flag.txt` files and auto-submit upon changes. |
| `ctf sync --offline` | Sync the live workspace data to the offline SQLite cache. |
| `ctf track` | Launch the live scoreboard polling tracker. |
| `ctf categories` | Display category overview with solve statistics. |
| `ctf config` | Show and validate the active configuration. |
| `ctf set <key> <value>` | Update a config value in-place. |

---

<a id="turkce"></a>
# CSC - CtfShitCli v3.0

Güvenlik araştırmacıları, CTF yarışmacıları ve takım kaptanları için tasarlanmış nihai CTFd İsviçre Çakısı CLI aracı. Zamanın kritik olduğu yarışmalarda hantal web arayüzleriyle uğraşmayı bırakın; tüm CTF iş akışınızı doğrudan terminalden yönetin.

![Sürüm](https://img.shields.io/badge/s%C3%BCr%C3%BCm-v3.0-blue?style=for-the-badge)
![Lisans](https://img.shields.io/badge/lisans-MIT-green?style=for-the-badge)
![Python](https://img.shields.io/badge/python-3.9%2B-blue?style=for-the-badge)
![Click](https://img.shields.io/badge/click-8.1%2B-orange?style=for-the-badge)

## 🚀 Temel Modüller ve Özellikler

### 🧠 Otonom AI Analizörü (`ctf ai`)
Bir soruda tıkandığınızda Red Team AI Ajanınızı sahaya sürün. Bulunduğunuz dizinde `ctf ai analyze` komutunu çalıştırdığınızda ajan, kaynak kodları ve `challenge.txt` açıklamasını otomatik okur. Google Gemini API üzerinden sahip olduğunuz en güçlü modeli "Otomatik Keşif" ile bulur, kota/yük sorunlarını yedekleme (fallback) döngüsüyle atlatır ve size terminalinizde siberpunk temalı, profesyonel bir zafiyet analiz raporu sunar.

### 📜 Evrensel Script Üretici (`ctf script`)
Her yarışmada aynı kodları baştan yazmaya son! Evrensel Script Üretici, size kategorize edilmiş bir cephanelik sunar:
- **Web:** Kör SQLi (Blind SQLi) payloadları, JWT Sahteciliği (Forge), SSTI Payload Jeneratörleri.
- **Crypto:** RSA çözücüler, Z3 Theorem Prover iskeletleri, AES ECB Oracle exploit taslakları.
- **Pwn:** `pwntools` tabanlı standart `ret2libc` ROP saldırı iskeletleri.
- **Forensics:** `scapy` ile otomatik PCAP HTTP ve DNS analizcileri.
- **OSINT:** Popüler platformlarda (GitHub, Twitter vb.) hızlı username recon betikleri.
- **Stego:** LSB Çıkarıcılar (Extractor), Exif analizcileri.
Kategorileri görmek için `ctf script list`, istediğiniz betiği dizine kopyalamak için `ctf script generate <isim>` komutunu kullanın.

### 👁️ Watchdog ve Otomatik Gönderici (`ctf watch`)
Flag bulduğunuzda submit etmekle uğraşmayın. Arka planda çalışan bu iblis (daemon), çalışma alanınızı izler. Bir yere `flag.txt` yazıldığı an milisaniyeler içinde Regex ile flag'i yakalar. Hatta `ctf set flag_format CTF{}` komutuyla tanımladığınız özel formatlara dinamik uyum sağlar. Başarılı gönderimleri lokal diske kaydeder ve dilerseniz takımınızın **Discord kanalına anında Webhook** atar!

### 📥 Akıllı İndirici ve Şifre Kırıcı (`ctf pull`)
Dosya ekleri `aiohttp` ile asenkron ve çoklu olarak inerken, zip-slip zafiyetlerine karşı güvenle çıkarılır (`--extract`). En güzel yanı: Eğer indirilen arşiv parola korumalıysa ve soru açıklamasında (örn: "Şifre: 1234") parola verilmişse, ajanımız bu parolayı Regex ile algılar ve arşivi sizin yerinize otomatik kırarak dosyaları dizine serer!

### 🏗️ Deterministik Çalışma Alanı Yöneticisi
- **`ctf init`:** Lokal bir SQLite önbelleği ve `.ctf_config.json` başlatır.
- **`ctf set`:** Dosyalara dokunmadan `flag_format`, `llm_api_key`, `discord_webhook_url` gibi anahtarları canlı olarak günceller.
- **`ctf add`:** CTFd kategorisine göre temiz bir `challenge.txt` iskeleti oluşturarak ortamı analize hazır hale getirir.

### 📊 Canlı Takip ve Raporlama
- **`ctf track`:** Rakiplerinizin ilerleyişini terminalinizden anlık scoreboard üzerinden izleyin.
- **`ctf export writeups`:** Çözdüğünüz tüm soruları, kodladığınız çözüm betiklerini ve açıklamaları tek bir harika `writeups.md` dosyasına dönüştürerek blogunuzda paylaşmaya hazır hale getirin.

## 📦 Kurulum

```bash
git clone https://github.com/MacallanTheRoot/CSL-CtfShitCli.git
cd CSL-CtfShitCli

python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -e .
```

## 🎮 Komut Referansı

| Komut | Açıklama |
|---|---|
| `ctf init <url>` | Yeni bir etkinlik için çalışma alanı başlatır. |
| `ctf add <cat/name>` | Temiz bir challenge dizin iskeleti oluşturur. |
| `ctf list [--offline]` | Challenge'ları listeler (gerekirse çevrimdışı önbellekten). |
| `ctf pull [--all] [--extract]` | Dosya eklerini indirir ve güvenle klasöre çıkartır. |
| `ctf submit <flag>` | Flag gönderir (Challenge ID'sini otomatik algılar ve formatlar). |
| `ctf bulk <csv>` | CSV dosyasından toplu flag gönderimi yapar. |
| `ctf hint list <id>` | Belirli bir soruya ait ipuçlarını listeler. |
| `ctf hint unlock <id>` | Belirli bir ipucunun kilidini açar. |
| `ctf submissions <id>` | Lokal flag deneme geçmişinizi gösterir. |
| `ctf export writeups` | Çözülen tüm soruları tek bir Markdown dosyasına dönüştürür. |
| `ctf script list` | CTF'lerde zaman kazandıran hazır otomasyon betiklerini listeler. |
| `ctf script generate <name>` | Seçilen otomasyon scriptini bulunduğunuz dizine kaydeder. |
| `ctf ai analyze` | Otonom zafiyet ve kod analizi yapar (LLM tabanlı). |
| `ctf watch [--all]` | `flag.txt` dosyalarını izler ve değiştiğinde otomatik gönderir. |
| `ctf sync --offline` | Çalışma alanı verilerini çevrimdışı önbelleğe eşitler. |
| `ctf track` | Canlı skor tablosu takip aracını başlatır. |
| `ctf categories` | Çözüm istatistikleriyle kategori özetini gösterir. |
| `ctf config` | Aktif yapılandırmayı gösterir ve doğrular. |
| `ctf set <anahtar> <değer>` | Bir yapılandırma değerini anında günceller. |

---
**Lisans:** MIT  
**Geliştirici:** [MacallanTheRoot](https://github.com/MacallanTheRoot)
