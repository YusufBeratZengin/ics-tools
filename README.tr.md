# ics-tools
[![CI](https://github.com/YusufBeratZengin/ics-tools/actions/workflows/ci.yml/badge.svg)](https://github.com/YusufBeratZengin/ics-tools/actions/workflows/ci.yml) [![PyPI](https://img.shields.io/pypi/v/ics-tools)](https://pypi.org/project/ics-tools/) [![MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE) [![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml) [![Dependencies](https://img.shields.io/badge/runtime_dependencies-0-green)](pyproject.toml)

iCalendar (.ics) dosyalarını oku, birleştir, filtrele, doğrula ve CSV'ye aktar; tekrar eden etkinlikleri tarih aralığında listele.
Tip bilgisi sunan Python kütüphanesi ve CLI; çalışma zamanı bağımlılığı yok, takvimler yerelde işlenir.
[English](README.md) | [Türkçe](README.tr.md)

Depo klasöründe kur: `python -m pip install .`
Dene: `python -m ics_tools validate examples/demo.ics`

## Demo

Projeyle gelen yapay takvim örneğini çalıştır:

```sh
python examples/demo.py
```

Gerçek çıktı (DAILY, COUNT, EXDATE ve RDATE birlikte):

```text
Parsed 1 event
2026-01-01T09:00:00+00:00 | Demo sync
2026-01-03T09:00:00+00:00 | Demo sync
2026-01-05T09:00:00+00:00 | Demo sync
```

## Kurulum

Python 3.10 veya üstü gerekir. Yukarıdaki kurulum komutunu depo kökünde çalıştır.
Paket Hatchling ile oluşturulur; kurulum için erişilebilir bir paket kaynağı veya önceden kurulmuş build aracı gerekir.
PyPI rozeti paket kaynağındaki durumu gösterir; yayın workflow'unu eklemek tek başına sürüm yayımlamaz.
Kurulumdan sonra `ics` komutu, `python -m ics_tools` ile aynı işi yapar.

## Kullanım

### CLI

Merge, `(UID, RECURRENCE-ID)` eşleşmesiyle tekilleştirir. Önce yüksek SEQUENCE, ardından
yeni LAST-MODIFIED ve DTSTAMP, eşitlikte ise sonraki girdi tercih edilir. Filter; özet,
açıklama, konum ve kategorilerde arama yapar; varsayılan olarak büyük/küçük harf ayrımı yapmaz.
List, tekrar eden etkinliklerin oluşumlarını listeler. Validate, geçerli girdide 0, hatada 1 döndürür;
yalnız uyarı varsa başarısız sayılmaz. Örneklerde yapay veri kullanılır; çıktılar `is/` altına yazılır.

```sh
python -m ics_tools merge examples/demo.ics examples/demo.ics -o is/merged.ics
python -m ics_tools filter examples/demo.ics --from 2026-01-01 --to 2026-01-07 --match Demo -o is/filtered.ics
python -m ics_tools list examples/demo.ics --from 2026-01-01 --window 30d --tz Europe/Istanbul
python -m ics_tools validate examples/demo.ics
python -m ics_tools to-csv examples/demo.ics --from 2026-01-01 --window 30d --tz Europe/Istanbul -o is/events.csv
python -m ics_tools to-csv examples/demo.ics --raw -o is/events-raw.csv
```

Filter, list ve to-csv için dosya yerine `-` kullanabilir veya girdiyi boş bırakarak stdin'den okuyabilirsin.
`-o` verilmezse çıktı stdout'a yazılır. CSV sütunları: UID, Summary, Description, Location,
Start, End, Duration, AllDay, Status ve RecurrenceId. CSV aktarımında tarih sınırı veya pencere
verilirse tekrarlar açılır; sınır verilmezse ham kayıtlar aktarılır. `--raw` her zaman ham kayıt verir.

### Python API

```python
from datetime import date
from pathlib import Path
from ics_tools import (
    expand_event, export_to_csv, filter_calendar, merge_calendars,
    parse_calendar, serialize_calendar, validate_calendar,
)

calendar = parse_calendar(Path("examples/demo.ics"))
occurrences = expand_event(calendar.events[0], date(2026, 1, 1), date(2026, 1, 7))
assert len(occurrences) == 3
merged = merge_calendars([calendar, calendar])
filtered = filter_calendar(merged, pattern="Demo")
assert validate_calendar(serialize_calendar(filtered)).is_valid
csv_text = export_to_csv(filtered, window_start=date(2026, 1, 1), window_end=date(2026, 1, 7))
assert "Demo sync" in csv_text
```

`parse_calendar`; metin, UTF-8 baytları, `Path` veya metin akışı kabul eder.
`Calendar` ve `Event` nesneleri doğrudan da oluşturulabilir. `serialize_calendar`, CRLF satır
sonlarıyla metin döndürür; bunları korumak için `serialize_calendar_bytes` kullan veya çıktı
dosyasını `newline=""` ile aç. `export_to_csv` metin döndürür; `output` verilirse akışa yazar ve boş metin döndürür.

## Örnekler

[examples/demo.py](examples/demo.py) ve [examples/demo.ics](examples/demo.ics), çalıştırılabilir
yapay örneklerdir. Test fixture'ları Google, Apple, Outlook ve Thunderbird çıktılarının biçimini
taklit eder; gerçek kullanıcı takvimlerinden alınmamıştır.

## Yapılandırma / seçenekler

| Seçenek veya kural | Davranış |
| --- | --- |
| `--from`, `--to` | ISO tarih veya tarih-saat sınırları; yalnız tarih verilirse gece yarısı kabul edilir |
| `--window` | `30d`, `2w`, `24h` veya `1m` (30 gün); açıkça verilen `--to` önceliklidir |
| `--tz` | List / CSV çıktısı için IANA veya desteklenen Windows zaman dilimi adı |
| `--match`, `--case-sensitive` | Regex filtresi; isteğe bağlı büyük/küçük harf ayrımı |
| `-o`, `--output` | Çıktı dosyası; gerekirse üst klasörleri oluşturulur |
| `--raw` | Tekrarları açmadan CSV'ye aktarım |
| RRULE | DAILY, WEEKLY, MONTHLY, YEARLY; INTERVAL, COUNT, UNTIL, BYDAY, BYMONTHDAY, BYMONTH, BYSETPOS, WKST |
| İstisnalar | EXDATE, RDATE (DATE / DATE-TIME) ve iptaller dahil RECURRENCE-ID değişiklikleri |

## Nasıl çalışır?

Parser, katlanmış satırları birleştirir; kaçışlı metinleri ve tırnaklı parametreleri işler,
bilinmeyen özellikleri korur. Writer, özellikleri tutarlı sırada yazar; UTF-8 satırlarını
75 baytta katlar ve CRLF üretir. Event nesnesinde DTSTAMP yoksa ilk yazımda atanır ve sonraki
yazımlarda korunur. Tekrar filtreleri, her frekans dönemi içinde BYSETPOS'tan önce uygulanır.
COUNT, UNTIL ve pencere sonu birlikte üretimi sınırlar. Zaman diliminde önce IANA verisi kullanılır.

## Sınırlamalar / gizlilik

Takvimler çevrimdışı işlenir; dışarıya veri gönderilmez. Özel takvimleri issue veya fixture olarak ekleme.
Araç, RFC 5545'in pratik bir alt kümesini uygular; kapsamlı bir RFC uygunluk denetleyicisi değildir.
Tekrar genişletme DAILY–YEARLY aralığını destekler; RDATE PERIOD değerleri,
BYHOUR/BYMINUTE/BYSECOND/BYYEARDAY/BYWEEKNO ve RANGE=THISANDFUTURE desteklenmez.
Doğrulama; yapıyı, temel zorunlu alanları, tarih biçimini ve desteklenen tekrar değerlerinin sınırlarını
kontrol eder; RFC'nin her koşulunu denetlemez.

Gömülü VTIMEZONE yedeği offset değerlerini çıkarır ve kuzey yarımküre için yaklaşık bir yaz saati aralığı kullanır;
geçmiş geçişleri ve bileşendeki geçiş RRULE'larını yorumlamaz. Sistemde IANA verisi yoksa
(Windows'ta sık görülür) yaygın zaman dilimleri için kullanılan yedeklerde de bu sınırlar geçerlidir.
Bilinmeyen TZID için uyarı kaydedilir ve UTC kullanılır. Zaman dilimsiz datetime değerleri
karşılaştırmada UTC sayılır; tutarlı dönüşüm için zaman dilimli değerler kullan.
Tarih penceresi sınırları ve aralıkla örtüşen etkinlikler dahildir; bir günün tamamını kapsamak için
bitişi tarih-saat olarak ver. Sınırsız generator'ı yalnız gerektiği kadar tüket veya COUNT,
UNTIL ya da pencere sonu belirt. Üretim DTSTART'tan başladığı için eski seriler ve geniş pencereler yavaş olabilir.

## Geliştirme

Depo klasöründe geliştirme araçlarını kurup kontrolleri çalıştır:

```sh
python -m pip install -e ".[dev]"
python -m ruff check .
python -m mypy src
python -m pytest -q
python -m build
python -m twine check dist/*
```

CI, Linux ve Windows üzerinde Python 3.10–3.13 sürümlerini kapsar. Testler ağa bağlanmaz.
Kısıtlı çalışma ortamlarına uyum için pytest'in isteğe bağlı cache eklentisi kapalıdır.

## Katkıda bulunma

Kontroller, commit biçimi ve bakım sorumlusunun sürüm çıkarma adımları için
[CONTRIBUTING.md](CONTRIBUTING.md) dosyasına bak. Topluluk kuralları
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), özel güvenlik bildirim yolu ise [SECURITY.md](SECURITY.md) içindedir.

## Lisans

[MIT](LICENSE). Telif hakkı (c) 2026 Yusuf Berat Zengin.
