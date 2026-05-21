"""
JARVIS - Modüler Araç Şemaları (Tool Declarations)
"""

TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": "Windows'ta herhangi bir uygulamayi acar. Spotify, Edge, Terminal, Explorer, VS Code vb.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Uygulama adi (orn. 'Spotify', 'Edge', 'Terminal')"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "close_app",
        "description": "Windows'ta acik olan bir uygulamayi kapatir (sonlandirir).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Kapatilacak uygulamanin adi (orn. 'Chrome', 'Hesap Makinesi')"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "sleep_jarvis",
        "description": "JARVIS'i uyku moduna (arka plana) alır. Ekranda kaybolur ama 'Jarvis' dendiğinde tekrar uyanmak için arka planda mikrofonu dinlemeye devam eder. Kullanıcı 'uyu', 'arka plana geç', 'kendini gizle', 'beklemeye geç' derse kullan.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "shutdown_jarvis",
        "description": "JARVIS'i TAMAMEN kapatır ve programdan çıkar. Bunu yaparsan bir daha SESLE UYANAMAZSIN. Sadece kullanıcı açıkça 'tamamen kapan', 'komple çık', 'sistemi sonlandır' derse kullan. Kullanıcı sadece 'kapan' veya 'kendini kapat' derse, ona 'Tamamen kapanmamı mı istiyorsunuz, yoksa arka planda uyuyup sizi dinlemeye devam mı edeyim?' diye sor.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "power_control",
        "description": "Bilgisayarı (Windows sistemini) kapatır, yeniden başlatır veya acil durum güvenlik protokolü (Lockdown) ile kilitler. Kullanıcı 'bilgisayarı kapat', 'yeniden başlat' veya 'sistemi kilitle', 'güvenlik protokolünü başlat', 'acil durum kalkanı' dediğinde kullan.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "shutdown | restart | lockdown"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "news_intelligence",
        "description": "Global yapay zeka, teknoloji, ülke gündemi veya Trabzonspor haberlerini getirir ve detaylarını okur. Kullanıcı Trabzonspor'u veya genel haberleri sorduğunda action='summary' ve category='ai|tech|turkey|trabzonspor' kullan. Kullanıcı 'Bize her yer Trabzon!', 'Trabzonspor'da ne var' gibi coşkulu şeyler sorarsa category='trabzonspor' kullanıp ona Bordo Mavi coşkusuyla hitap et.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "summary | detail"
                },
                "category": {
                    "type": "STRING",
                    "description": "ai | tech | turkey | trabzonspor"
                },
                "news_id": {
                    "type": "STRING",
                    "description": "Haberin ID'si (Örn: news_1)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "cinema_intelligence",
        "description": "Film ve dizi zekası. Kullanıcının ruh haline veya isteğine göre akıllı film/dizi tavsiyeleri yapmak (action='recommend'), izleme listesine veya dizi bölüm takibine kayıt eklemek (action='tracker_save', item_name='Dune 2', item_type='movie|series', episode_info='İzlenecek'), kayıtları Film ve Dizi olarak ayrı kategoriler halinde sorgulamak (action='tracker_get') veya bu hafta sinema/platformlarda ne olduğunu taramak (action='radar') için kullan.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "recommend | tracker_save | tracker_get | radar"
                },
                "query": {
                    "type": "STRING",
                    "description": "Kullanıcının öneri/arama kriteri"
                },
                "item_name": {
                    "type": "STRING",
                    "description": "Dizi veya film adı (tracker_save için)"
                },
                "item_type": {
                    "type": "STRING",
                    "description": "movie | series (tracker_save için)"
                },
                "episode_info": {
                    "type": "STRING",
                    "description": "Bölüm veya not (Örn: 'S01E05' veya 'İzlenecek')"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "sys_info",
        "description": "Sistem bilgisi alır: pil durumu, CPU, RAM, disk, saat, tarih, ağ bağlantısı.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "battery | cpu | ram | disk | time | date | network | all"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_weather",
        "description": (
            "Anlık ve günün ilerleyen saatlerindeki (saatlik) hava tahminini ve trendleri getirir. "
            "Kullanıcı hava durumunu, sıcaklığı veya yağmur durumunu sorduğunda kullan. "
            "Gelen veriyi Weather Intelligence kurallarına (🌤️ Durum Analizi, 🏃 Günlük Senaryo) göre analiz et."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "location": {
                    "type": "STRING",
                    "description": "Sehir veya konum. Bos birakilirsa Istanbul kullanilir."
                }
            }
        }
    },
    {
        "name": "get_calendar_events",
        "description": (
            "Windows JARVIS yerel takvimini okur. "
            "Bugun, yarin, siradaki etkinlik veya yaklasan ajandayi ozetler. "
            "Kullanici toplanti, takvim, ajanda, etkinlik veya gunluk programini sordugunda kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": (
                        "today | tomorrow | next | agenda | week veya dogal dilde "
                        "'onumuzdeki 30 gun', '2 hafta', 'bu ay', 'gelecek ay'"
                    )
                },
                "limit": {
                    "type": "NUMBER",
                    "description": "Maksimum etkinlik sayisi"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "add_calendar_event",
        "description": (
            "Windows JARVIS yerel takvimine yeni etkinlik ekler. "
            "Kullanici toplanti, randevu, takvime ekleme veya etkinlik olusturma isterse kullan. "
            "Baslangic tarihini gercek tarih/saat olarak ver; bitis verilmezse varsayilan sure kullanilir."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {
                    "type": "STRING",
                    "description": "Etkinlik basligi. Ornek: 'Disci Randevusu'"
                },
                "start_iso": {
                    "type": "STRING",
                    "description": "Baslangic tarih/saat. ISO veya yyyy-MM-dd HH:mm formatinda."
                },
                "end_iso": {
                    "type": "STRING",
                    "description": "Bitis tarih/saat. Opsiyonel."
                },
                "location": {
                    "type": "STRING",
                    "description": "Etkinlik konumu. Opsiyonel."
                },
                "notes": {
                    "type": "STRING",
                    "description": "Etkinlik notlari. Opsiyonel."
                },
                "calendar_name": {
                    "type": "STRING",
                    "description": "Eklenecek takvim adi. Opsiyonel."
                },
                "all_day": {
                    "type": "BOOLEAN",
                    "description": "true ise tum gun etkinligi olusturur."
                }
            },
            "required": ["title", "start_iso"]
        }
    },
    {
        "name": "delete_calendar_event",
        "description": (
            "Windows JARVIS yerel takviminden etkinlik siler. "
            "Kullanici bir toplantiyi, randevuyu veya takvim kaydini silmek istediginde kullan. "
            "Ayni ada birden fazla etkinlik varsa dogru kaydi bulmak icin baslangic tarihini gercek tarih/saat olarak ver."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {
                    "type": "STRING",
                    "description": "Silinecek etkinlik basligi. Ornek: 'Disci Randevusu'"
                },
                "start_iso": {
                    "type": "STRING",
                    "description": "Opsiyonel tarih/saat. Ayni isimli birden fazla etkinligi ayirt etmek icin kullan."
                },
                "calendar_name": {
                    "type": "STRING",
                    "description": "Opsiyonel takvim adi"
                },
                "delete_all_matches": {
                    "type": "BOOLEAN",
                    "description": "true ise eslesen tum etkinlikleri siler"
                }
            },
            "required": ["title"]
        }
    },
    {
        "name": "get_reminders",
        "description": (
            "Windows JARVIS hatirlaticilar listesini okur. "
            "Bugunku, yaklasan, geciken veya tum acik animsaticilari ozetler. "
            "Kullanici hatirlatma, animsatici, reminder veya yapilacaklar listesini sordugunda kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "today | upcoming | overdue | all | next"
                },
                "limit": {
                    "type": "NUMBER",
                    "description": "Maksimum animsatici sayisi"
                },
                "list_name": {
                    "type": "STRING",
                    "description": "Istenirse belirli bir animsatici listesi adi"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "add_reminder",
        "description": (
            "Windows JARVIS hatirlatici deposuna yeni bir animsatici ekler. "
            "Kullanici 'hatirlat', 'animsatici ekle', 'reminder kur' dediginde kullan. "
            "Goreli zaman ifadelerini bugunku tarih baglamina gore due_iso alanina ISO formatinda cevir."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {
                    "type": "STRING",
                    "description": "Animsatici basligi"
                },
                "due_iso": {
                    "type": "STRING",
                    "description": "Opsiyonel tarih/saat. Ornek: 2026-04-13T09:00 veya tum gun icin 2026-04-13"
                },
                "notes": {
                    "type": "STRING",
                    "description": "Opsiyonel not"
                },
                "list_name": {
                    "type": "STRING",
                    "description": "Opsiyonel animsatici listesi"
                },
                "priority": {
                    "type": "STRING",
                    "description": "low | medium | high"
                },
                "all_day": {
                    "type": "BOOLEAN",
                    "description": "Tum gun animsatici ise true"
                }
            },
            "required": ["title"]
        }
    },
    {
        "name": "delete_reminder",
        "description": "Windows JARVIS hatırlatıcı deposundan kayıtlı bir anımsatıcıyı siler. Kullanıcı 'hatırlatıcıyı sil', 'anımsatıcıyı kaldır', 'şu hatırlatmayı sil' dediğinde kullan.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {
                    "type": "STRING",
                    "description": "Silinecek anımsatıcının başlığı veya içeriği (Örn: 'Bilgisayarı kapatma')"
                }
            },
            "required": ["title"]
        }
    },
    {
        "name": "browser_control",
        "description": "Tarayıcıda URL açar, Google'da arama yapar veya YouTube'da ilk sonucu doğrudan oynatır.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "open_url | search | play_youtube"},
                "url":    {"type": "STRING", "description": "Açılacak URL (open_url için)"},
                "query":  {"type": "STRING", "description": "Arama sorgusu (search veya play_youtube için)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "shell_run",
        "description": "Windows PowerShell komutu calistirir. Dosya işlemleri, sistem yönetimi.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {
                    "type": "STRING",
                    "description": "Calistirilacak PowerShell komutu"
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "play_media",
        "description": (
            "YouTube, Spotify veya Windows Muzik uygulamasında şarkı, müzik veya video açar. "
            "Kullanıcı belirli bir platform söylerse onu kullan. "
            "Belirtmezse uygun olanı dene. "
            "Kullanıcı 'çal', 'oynat', 'aç' diyorsa autoplay=true kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Şarkı, sanatçı, albüm veya video arama ifadesi"
                },
                "provider": {
                    "type": "STRING",
                    "description": "auto | youtube | spotify | windows_music"
                },
                "autoplay": {
                    "type": "BOOLEAN",
                    "description": "true ise mümkünse doğrudan oynatır"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_youtube_channel_report",
        "description": (
            "YouTube kanalinin public istatistiklerini ve son videolarin performansini raporlar. "
            "Kullanici kanal istatistiklerini, abone sayisini, son videolarini, buyume hizini "
            "veya YouTube analizini sordugunda kullan. Bu arac Studio yerine public YouTube Data API verisini kullanir."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": (
                        "Dogal dilde analiz istegi. Ornek: "
                        "'YouTube istatistiklerim nasil', 'son videolarimi analiz et', "
                        "'kanal buyumemi ozetle'"
                    )
                },
                "handle": {
                    "type": "STRING",
                    "description": (
                        "Opsiyonel kanal handle'i, kanal linki veya kanal ID'si. "
                        "Bos birakilirsa ayarlardaki youtube_channel_handle kullanilir."
                    )
                },
                "video_limit": {
                    "type": "NUMBER",
                    "description": "Analize dahil edilecek son video sayisi. Varsayilan 6."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "analyze_screen",
        "description": (
            "Aktif pencerenin ekran goruntusunu alip Gemini vision ile analiz eder. "
            "Kullanici ekranda ne oldugunu, bir hatayi, gorunen metni, butonlari veya pencere icerigini sordugunda kullan. "
            "Bu surum yalnizca aktif pencereyi destekler."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Kullanicinin ekranla ilgili sorusu. Ornek: 'Bu hatayi oku', 'Ekranda ne var?'"
                },
                "target": {
                    "type": "STRING",
                    "description": "Su an sadece active_window desteklenir."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "save_memory",
        "description": "Kullanıcı hakkında önemli bilgiyi kalıcı belleğe kaydeder. İsim, tercihler, projeler vb. duyunca sessizce çağır.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": "identity | preferences | projects | notes"
                },
                "key":   {"type": "STRING", "description": "Kısa anahtar (örn. 'name')"},
                "value": {"type": "STRING", "description": "Değer (İngilizce)"}
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "manage_smart_notes",
        "description": (
            "Akıllı not sistemi. Kullanıcı uzun soluklu bir not almak, not aramak veya silmek istediğinde kullan."
            "Kullanıcının cümlesinden kategoriyi, önceliği, deadline'ı ve etiketleri otomatik çıkararak Markdown formatında kaydeder. "
            "Örn: 'Yarınki toplantı için slayt hazırla deadline cuma' -> category: work, tags: ['toplantı', 'slayt'], deadline: cuma, priority: high"
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "create, search, list, delete"
                },
                "content": {
                    "type": "STRING",
                    "description": "Notun içeriği (create ve search için)."
                },
                "category": {
                    "type": "STRING",
                    "description": "work, personal, idea, todo (create ve search için)."
                },
                "tags": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "Not ile ilgili anahtar kelimeler (create için)."
                },
                "deadline": {
                    "type": "STRING",
                    "description": "Varsa son tarih (create için)."
                },
                "priority": {
                    "type": "STRING",
                    "description": "low, normal, high (create için)."
                },
                "note_id": {
                    "type": "STRING",
                    "description": "Silmek istenen notun ID'si (delete için)."
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "network_diagnostics",
        "description": (
            "Ağ tanılama ve internet sorunlarını analiz aracı. "
            "Kullanıcı 'İnternetim yavaş', 'Ping'imi ölç', 'DNS hatası alıyorum' veya 'Bağlantımı test et' dediğinde kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "ping (gecikme), speedtest (hız testi), dns_flush (dns temizleme), traceroute (bağlantı yolu)"
                },
                "target": {
                    "type": "STRING",
                    "description": "ping veya traceroute için hedef adres (örn. google.com). Belirtilmezse google.com kullanılır."
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "delete_memory",
        "description": (
            "Kalici hafizadaki bir kaydi siler. "
            "Kullanici 'bunu hafizandan kaldir', 'unut', 'sil' gibi bir sey derse kullan. "
            "Mumkunse category ve key ile sil; emin degilsen match_text ile ilgili kaydi bulup kaldir."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": "Kaydin kategorisi. Ornek: notes | identity | preferences | projects"
                },
                "key": {
                    "type": "STRING",
                    "description": "Silinecek anahtar. Ornek: claude_limit_refresh"
                },
                "match_text": {
                    "type": "STRING",
                    "description": "Kaydi bulmak icin kullanilacak dogal dil parcasi. Ornek: 'claude ai limit yenilenmesi'"
                }
            }
        }
    },
    {
        "name": "toggle_english_tutor",
        "description": "Ingilizce Pratik ve Ogretmen modunu acar veya kapatir. Kullanici 'ingilizce pratigi yapalim' derse enabled=True gonder.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "enabled": {"type": "BOOLEAN", "description": "Tutor modunu acmak icin True, kapatmak icin False"}
            },
            "required": ["enabled"]
        }
    },
    {
        "name": "enroll_voiceprint",
        "description": "Kullanıcının sesini kaydederek onu sistemin tek sahibi (Master) olarak yetkilendirir. Kullanıcı 'sesimi kaydet', 'sahibin benim' vb. dediğinde kullan.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "get_market_data",
        "description": "Borsa, kripto, altın veya döviz verilerini sorgular. Kullanıcı 'piyasalar ne durumda', 'bitcoin kaç para', 'dolar ne kadar' veya 'Apple hissesi' dediğinde çağır.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "symbol": {
                    "type": "STRING",
                    "description": "Spesifik bir sembol sorulduysa (Örn: AAPL, TSLA, BTC-USD, TRY=X). Genel piyasa sorulduysa boş bırak."
                }
            }
        }
    },
    {
        "name": "update_tutor_stats",
        "description": "Tutor modunda ogrenilen yeni kelimeleri ve kullanicinin son hatasinin aciklamasini HUD arayuzune gonderir. Sessizce calisir.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "new_word": {"type": "STRING", "description": "Ogrenilen yeni kelime ve anlami (Orn: 'Ubiquitous - Yaygin')"},
                "last_correction": {"type": "STRING", "description": "Kullaniciya verilen son feedback (Orn: 'He go -> He goes olacakti')"},
                "fluency": {"type": "STRING", "description": "Akicilik skoru (Orn: '85%')"}
            }
        }
    },
    {
        "name": "read_clipboard",
        "description": "Kullanıcının panosundaki (clipboard) son kopyaladığı metni okur. Kullanıcı 'bunu bana açıkla', 'kopyaladığım yazıyı çevir' veya 'panomdaki kodu düzelt' derse kullan.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "optimize_system",
        "description": "Bilgisayarın RAM önbelleğini ve geçici (temp) dosyalarını temizler. Kullanıcı 'sistemi optimize et', 'RAMi temizle' veya 'önbelleği boşalt' derse kullan.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "send_whatsapp_message",
        "description": (
            "WhatsApp Desktop veya WhatsApp Web üzerinden mesaj taslağı açar veya mesajı gönderir. "
            "Kişi adı veya telefon numarasıyla çalışabilir. "
            "Telefon numarası verilmemişse kişi adını önce kayıtlı WhatsApp kişileri ve içe aktarılan telefon rehberinde ara. "
            "Kullanıcı 'gönder', 'yolla', 'ile', 'hemen gönder' gibi açık bir gönderme niyeti söylüyorsa "
            "ekstra onay istemeden send_now=true kullan. "
            "Yalnızca 'hazırla', 'taslak aç', 'yaz ama gönderme' diyorsa send_now=false kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "recipient_name": {
                    "type": "STRING",
                    "description": "Kişi adı. Örn: 'Anne', 'Ahmet', 'Ece'"
                },
                "phone_number": {
                    "type": "STRING",
                    "description": "Uluslararası telefon numarası. Örn: +905551112233"
                },
                "message": {
                    "type": "STRING",
                    "description": "Gönderilecek mesaj içeriği"
                },
                "app_target": {
                    "type": "STRING",
                    "description": "desktop | web | auto. Varsayılan auto, tercihen desktop."
                },
                "send_now": {
                    "type": "BOOLEAN",
                    "description": "true ise sohbet açıldıktan sonra mesajı otomatik gönderir"
                }
            },
            "required": ["message"]
        }
    },
    {
        "name": "save_whatsapp_contact",
        "description": (
            "Sık kullanılan bir WhatsApp kişisini adı ve telefon numarasıyla kalıcı belleğe kaydeder. "
            "Kullanıcı bir kişiyi 'annem', 'Ahmet', 'iş ortağım' gibi tekrar kullanılacak şekilde tanımladığında kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "display_name": {
                    "type": "STRING",
                    "description": "Kaydedilecek kişi adı. Örn: 'Annem', 'Ahmet'"
                },
                "phone_number": {
                    "type": "STRING",
                    "description": "Uluslararası telefon numarası. Örn: +905551112233"
                },
                "aliases": {
                    "type": "STRING",
                    "description": "Virgülle ayrılmış alternatif hitaplar. Örn: 'anne, annem, mom'"
                }
            },
            "required": ["display_name", "phone_number"]
        }
    },
    {
        "name": "volume_control",
        "description": "Windows sistem sesini kontrol eder. Sesi açma, kısma, tamamen kapatma/açma veya belirli bir yüzdeye (%50 gibi) ayarlama işlemlerini yapar.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "Yapılacak işlem. 'up' (sesi aç), 'down' (sesi kıs), 'mute' (sesi kapat), 'unmute' (sesi geri aç), 'set' (belirli bir seviyeye ayarla)"
                },
                "level": {
                    "type": "NUMBER",
                    "description": "0 ile 100 arasında hedef ses seviyesi (yalnızca action='set' ise zorunlu)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "brightness_control",
        "description": "Windows ekran parlaklığını kontrol eder. Parlaklığı artırma, azaltma veya belirli bir yüzdeye (%80 gibi) ayarlama işlemlerini yapar. (Laptops/Monitors)",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "Yapılacak işlem. 'up' (parlaklığı artır), 'down' (parlaklığı azalt), 'set' (belirli bir seviyeye ayarla)"
                },
                "level": {
                    "type": "NUMBER",
                    "description": "0 ile 100 arasında hedef ekran parlaklığı (yalnızca action='set' ise zorunlu)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "media_playback_control",
        "description": "Windows arka plan medya oynatıcısını kontrol eder. Spotify, YouTube veya diğer çalarlar için medyayı durdurma, oynatma, sonraki/önceki şarkıya geçme işlemlerini yapar.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "Yapılacak işlem. 'play' (müziği başlat/devam ettir), 'pause' (müziği duraklat), 'next' (sonraki şarkı), 'prev' (önceki şarkı), 'stop' (oynatmayı tamamen durdur)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "power_profile_control",
        "description": "Windows güç planını (enerji modunu) kontrol eder. Performans artırma, oyun modu, güç tasarrufu veya dengeli moda geçme işlemlerini yapar.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "profile": {
                    "type": "STRING",
                    "description": "Hedef güç planı profili. 'high' (yüksek performans / oyun modu), 'save' (güç tasarrufu / pil modu), 'balanced' (dengeli / normal mod)"
                }
            },
            "required": ["profile"]
        }
    },
    {
        "name": "wallpaper_control",
        "description": "Windows masaüstü arkaplanını (duvar kağıdını) kullanıcının istediği temaya göre değiştirir.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Duvar kağıdı teması (Örn: 'trabzonspor', 'cyberpunk', 'space', 'nature', 'cars', 'anime', 'minimalist')"
                }
            },
            "required": ["query"]
        }
    }
]
