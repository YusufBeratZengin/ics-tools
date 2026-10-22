# ics-tools

iCalendar (.ics) dosyalarını ayrıştırmak, birleştirmek, filtrelemek ve doğrulamak için geliştirilmiş, RFC 5545 tekrarlayan etkinlik (RRULE) genişletme desteğine sahip Python kütüphanesi ve komut satırı aracı (CLI).

Sıfır çalışma zamanı bağımlılığı. Tamamen Python standart kütüphanesi (`zoneinfo`) üzerine inşa edilmiştir.

Bu dokümantasyonun İngilizce aslı: [README.md](README.md).

## Özellikler

- **RFC 5545 Ayrıştırıcı ve Sözcüksel Çözümleyici**: Satır katlamalarını (folding/unfolding) çözer, özellik parametrelerini ve tırnaklı değerleri ayrıştırır, metin kaçışlarını (escaping) RFC 5545 Bölüm 3.3.11'e göre işler.
- **Bayt Seviyesinde Kararlı Serileştirici**: 75 sekizli (octet) UTF-8 sınırlarında güvenli katlama ve zorunlu CRLF satır sonlarıyla deterministik çıktı üretir.
- **Tekrarlama Motoru (RRULE)**: Belirlenen zaman pencerelerinde `FREQ` (`DAILY`, `WEEKLY`, `MONTHLY`, `YEARLY`), `INTERVAL`, `COUNT`, `UNTIL`, `BYDAY` (sayısal sıra eki içeren `2TU`, `-1SU` dahil), `BYMONTHDAY`, `BYMONTH`, `BYSETPOS`, `EXDATE`, `RDATE` ve `RECURRENCE-ID` ile ezilen etkinlikleri genişletir.
- **Zaman Dilimi Çözümleme**: `zoneinfo` aracılığıyla IANA `TZID` eşlemesini önceler. Gömülü `VTIMEZONE` bileşenleri ve yaygın Windows zaman dilimi adları için belgelenmiş yedek çözümleyici sunar.
- **CLI Komutları**:
  - `ics merge`: `(UID, RECURRENCE-ID)` temelinde tekilleştirme ve `SEQUENCE`/`LAST-MODIFIED` önceliğiyle birden fazla takvimi birleştirir.
  - `ics filter`: Tarih aralığı ve düzenli ifade (regex) ile etkinlikleri filtreler.
  - `ics list`: Belirtilen zaman penceresinde yinelenen etkinlikleri genişleterek hedef zaman diliminde listeler.
  - `ics validate`: RFC 5545 kurallarına uyumluluğu denetler; hata ve uyarıları bildirir.
  - `ics to-csv`: Etkinlikleri ve yinelenen oluşumları CSV formatına aktarır.

## Gereksinimler

- Python >= 3.10
- Sıfır harici çalışma zamanı bağımlılığı

## Kurulum

```bash
pip install ics-tools
```

Veya kaynaktan düzenlenebilir modda kurun:

```bash
git clone https://github.com/YusufBeratZengin/ics-tools.git
cd ics-tools
pip install -e .
```

## CLI Kullanımı

### 1. Takvimleri Tekilleştirerek Birleştirme (`merge`)

Birden fazla iCalendar dosyasını tek dosyada birleştirir. Aynı `UID` ve `RECURRENCE-ID`ye sahip etkinlikler çakıştığında yüksek `SEQUENCE` veya daha yeni `LAST-MODIFIED` damgasına sahip olan tercih edilir:

```bash
ics merge takvim1.ics takvim2.ics -o birlesmis.ics
```

### 2. Etkinlikleri Filtreleme (`filter`)

Belirli bir tarih aralığına denk gelen veya özet/açıklama/konum alanlarında regex kalıbıyla eşleşen etkinlikleri filtreleyin:

```bash
# Tarih aralığına göre filtreleme (ISO 8601)
ics filter --from 2026-11-01 --to 2026-11-30 girdi.ics -o filtrelenmis.ics

# Regex kalıbı ile arama
ics filter --match "Sprint Planlama" girdi.ics -o planlama.ics

# Standart girdiden okuma
cat girdi.ics | ics filter --match "Tasarım" > cikti.ics
```

### 3. Tekrarlayan Etkinlikleri Listeleme (`list`)

Belirli bir süre penceresinde (örneğin `30d`, `2w`, `24h`) yer alan etkinlikleri genişleterek ve hedef zaman dilimine dönüştürerek listeleyin:

```bash
ics list --window 30d --tz Europe/Istanbul girdi.ics
```

Örnek çıktı:

```text
START                END                  SUMMARY                        LOCATION            
---------------------------------------------------------------------------------------------
2026-11-01 12:00     2026-11-01 13:00     Q4 Sprint Planlama             Toplantı Odası B    
2026-11-02 17:00     2026-11-02 18:00     Geliştirici Ofis Saati         Online Zoom         
```

### 4. RFC 5545 Uyumluluk Doğrulama (`validate`)

Bir veya daha fazla `.ics` dosyasının RFC 5545 gereksinimlerine, zorunlu bileşen alanlarına, tarih biçimlerine ve RRULE kurallarına uygunluğunu denetleyin:

```bash
ics validate takvim.ics
```

Tüm dosyalar geçerli olduğunda çıkış kodu `0`, hata bulunduğunda `1` döner.

### 5. CSV Formatına Aktarma (`to-csv`)

Takvim etkinliklerini elektronik tablo veya veri boru hatlarında işlemek üzere CSV'ye aktarın:

```bash
ics to-csv girdi.ics -o etkinlikler.csv --window 30d --tz Europe/Istanbul
```

CSV alanları: `UID`, `Summary`, `Description`, `Location`, `Start`, `End`, `Duration`, `AllDay`, `Status`, `RecurrenceId`.

Tekrarları genişletmeden ham etkinlik kayıtlarını aktarmak için `--raw` parametresi kullanılabilir:

```bash
ics to-csv girdi.ics -o ham_etkinlikler.csv --raw
```

## Python Kütüphanesi Kullanımı

### iCalendar Akışını Ayrıştırma

```python
from ics_tools import parse_calendar

with open("takvim.ics", "r", encoding="utf-8") as f:
    calendar = parse_calendar(f)

for event in calendar.events:
    print(f"{event.summary} | Başlangıç: {event.dtstart} | Süre: {event.effective_duration}")
```

### Tekrarlayan Etkinlikleri Genişletme (RRULE)

```python
from datetime import datetime, timezone
from ics_tools import parse_calendar, expand_event

calendar = parse_calendar(open("takvim.ics", "r", encoding="utf-8"))

window_start = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)
window_end = datetime(2026, 11, 30, 23, 59, tzinfo=timezone.utc)

for event in calendar.events:
    if event.rrule:
        occurrences = expand_event(event, window_start, window_end)
        for occ in occurrences:
            print(f"Oluşum: {occ.start} -> {occ.end} ({occ.summary})")
```

### Takvim Oluşturma ve Kaydetme

```python
from datetime import datetime, timezone
from ics_tools import Calendar, Event, serialize_calendar

cal = Calendar(prodid="-//Uygulama//TR")

event = Event(
    uid="etkinlik-9876@example.com",
    summary="Mimari Değerlendirme",
    description="RFC 5545 serileştirme motorunun incelenmesi.",
    dtstart=datetime(2026, 11, 15, 14, 0, tzinfo=timezone.utc),
    dtend=datetime(2026, 11, 15, 15, 30, tzinfo=timezone.utc),
    location="Toplantı Salonu A",
)

cal.add_event(event)

ics_metni = serialize_calendar(cal)
with open("cikti.ics", "w", encoding="utf-8", newline="") as f:
    f.write(ics_metni)
```

## Testleri Çalıştırma

Test paketini pytest ile çalıştırın:

```bash
python -m pytest -v
```

Veya standart Python unittest çalıştırıcısı ile doğrudan yürütün (ek paket gerektirmez):

```bash
python -m unittest discover -s tests -v
```

## Lisans

MIT Lisansı. Telif Hakkı (c) 2026 Yusuf Berat Zengin. Ayrıntılar için [LICENSE](LICENSE) dosyasına bakınız.
