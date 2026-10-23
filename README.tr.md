# ics-tools

[![CI](https://github.com/YusufBeratZengin/ics-tools/actions/workflows/ci.yml/badge.svg)](https://github.com/YusufBeratZengin/ics-tools/actions/workflows/ci.yml)
[![PyPI - Version](https://img.shields.io/pypi/v/ics-tools.svg)](https://pypi.org/project/ics-tools/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](pyproject.toml)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](pyproject.toml)

iCalendar (.ics) dosyalarını okuyun, birleştirin, filtreleyin, doğrulayın ve CSV'ye aktarın; tekrar eden etkinlikleri tarih aralığında listeleyin.

[English](README.md) | [Türkçe](README.tr.md)

![ics-tools CLI Demo](docs/demo.svg)

## Neden ics-tools?

- **Sıfır çalışma zamanı bağımlılığı**: Yalnızca saf Python standart kütüphanesi modülleri (`zoneinfo`, `re`, `datetime`, `csv`, `argparse`) ile geliştirilmiştir. Anında kurulum, sıfır tedarik zinciri riski ve minimum kaynak tüketimi.
- **Yerel ve gizlilik odaklı**: Tüm ayrıştırma, filtreleme ve açma işlemleri tamamen yerel makinenizde çevrimdışı yürütülür. Takvim kayıtları, konum bilgileri ve notlar asla bilgisayarınızın dışına çıkmaz.
- **Gelişmiş tekrar motoru**: INTERVAL, COUNT, UNTIL, BYDAY (sayısal sıra belirteçleriyle, örn. `2MO`, `-1FR`), BYMONTH, BYSETPOS, EXDATE, RDATE ve RECURRENCE-ID istisna geçersiz kılmalarını eksiksiz işleyen RFC 5545 uyumlu RRULE motoru (DAILY, WEEKLY, MONTHLY, YEARLY).

## Hızlı başlangıç

Python 3.10 veya üstü gerekir. Doğrudan kaynak koddan veya paketten kurun:

```sh
# Depo kök dizininde kurulum
python -m pip install .

# Bir iCalendar dosyasını doğrulama
ics validate examples/demo.ics

# 7 günlük pencerede yinelenen etkinlikleri listeleme
ics list examples/demo.ics --from 2026-01-01 --window 7d
```

> Kurulan komut satırı aracı `ics` adındadır. Alternatif olarak `python -m ics_tools` ile de çalıştırılabilir.

## Kullanım örnekleri

### Komut Satırı Arayüzü (CLI)

```sh
# 1. RFC 5545 standartlarına uygunluğu denetle (geçerlide 0, hatada 1 döner)
ics validate examples/demo.ics

# 2. Birden fazla takvim dosyasını otomatik tekilleştirmeyle birleştir
ics merge examples/demo.ics examples/demo.ics -o is/merged.ics

# 3. Etkinlikleri tarih aralığı ve metin aramasıyla filtrele
ics filter examples/demo.ics --from 2026-01-01 --to 2026-01-07 --match Demo -o is/filtered.ics

# 4. Tekrarları açarak hedef zaman diliminde etkinlikleri listele
ics list examples/demo.ics --from 2026-01-01 --window 30d --tz Europe/Istanbul

# 5. Tekrar eden etkinlikleri açarak CSV biçiminde dışa aktar
ics to-csv examples/demo.ics --from 2026-01-01 --window 30d --tz Europe/Istanbul -o is/events.csv

# 6. Takvim kayıtlarını tekrarları açmadan ham haliyle CSV'ye aktar
ics to-csv examples/demo.ics --raw -o is/events-raw.csv
```

**CLI Notları:**
- Filter, list ve to-csv komutları dosya yolu yerine `-` verilirse veya dosya argümanı boş bırakılırsa standart girdiden (`stdin`) okur.
- `-o` / `--output` parametresi verilmezse çıktılar doğrudan standart çıktıya (`stdout`) yazılır.
- CSV çıktı sütunları: `UID`, `Summary`, `Description`, `Location`, `Start`, `End`, `Duration`, `AllDay`, `Status` ve `RecurrenceId`.

### Python API

```python
from datetime import date
from pathlib import Path
from ics_tools import (
    expand_event,
    export_to_csv,
    filter_calendar,
    merge_calendars,
    parse_calendar,
    serialize_calendar,
    validate_calendar,
)

# Dosya yolu, ham metin, UTF-8 bayt dizisi veya metin akışından ayrıştırma
calendar = parse_calendar(Path("examples/demo.ics"))

# Belirli bir zaman penceresinde tekrar eden etkinlikleri açma
occurrences = expand_event(calendar.events[0], date(2026, 1, 1), date(2026, 1, 7))
assert len(occurrences) == 3

# Takvimleri çakışma çözümüyle birleştirme (UID + RECURRENCE-ID tekilleştirmesi)
merged = merge_calendars([calendar, calendar])

# Etkinlikleri metin deseni ve tarih sınırlarıyla filtreleme
filtered = filter_calendar(merged, pattern="Demo")

# RFC 5545 standartlarına uygunluğu denetleme
result = validate_calendar(serialize_calendar(filtered))
assert result.is_valid

# CSV formatına aktarma (metin döndürür veya doğrudan bir akışa yazar)
csv_text = export_to_csv(filtered, window_start=date(2026, 1, 1), window_end=date(2026, 1, 7))
assert "Demo sync" in csv_text
```

## Yapılandırma & seçenekler

### CLI parametreleri

| Seçenek | Komut | Açıklama |
| --- | --- | --- |
| `--from`, `--to` | `filter`, `list`, `to-csv` | ISO 8601 tarih (`YYYY-MM-DD`) veya tarih-saat (`YYYY-MM-DDTHH:MM:SSZ`). Yalnız tarih verildiğinde gece yarısı (UTC) kabul edilir. |
| `--window` | `list`, `to-csv` | Süre kısaltması: `30d` (gün), `2w` (hafta), `24h` (saat) veya `1m` (30 gün). Açıkça verilen `--to` bu değere önceliklidir. |
| `--tz` | `list`, `to-csv` | Hedef IANA zaman dilimi adı (örn. `Europe/Istanbul`, `America/New_York`) veya desteklenen Windows zaman dilimi adı. |
| `--match` | `filter` | `SUMMARY`, `DESCRIPTION`, `LOCATION` ve `CATEGORIES` alanlarında aranan düzenli ifade (regex). |
| `-i`, `--case-sensitive` | `filter` | Büyük/küçük harfe duyarlı regex eşleşmesi uygular (varsayılan: duyarsız). |
| `--raw` | `to-csv` | Tekrar eden etkinlikleri açmadan ham kayıtları CSV'ye aktarır. |
| `-o`, `--output` | `merge`, `filter`, `to-csv` | Hedef dosya yolu. Eksik üst klasörler otomatik olarak oluşturulur. |

### Tekrar kuralları & standart desteği

| Özellik | Destek Durumu |
| --- | --- |
| **Frekanslar** | `DAILY`, `WEEKLY`, `MONTHLY`, `YEARLY` |
| **Kural parçaları** | `INTERVAL`, `COUNT`, `UNTIL`, `BYDAY` (sayısal sıra belirteçleriyle, örn. `2MO`, `-1FR`), `BYMONTHDAY`, `BYMONTH`, `BYSETPOS`, `WKST` |
| **İstisnalar** | `EXDATE`, `RDATE` (`VALUE=DATE` ve `VALUE=DATE-TIME`) ve iptaller dahil `RECURRENCE-ID` geçersiz kılmaları |

## SSS ve Sınırlamalar

### Tekilleştirme nasıl çalışır?
`merge_calendars`, kayıtları `(UID, RECURRENCE-ID)` çiftine göre belirler. Çakışma durumunda kazanan kayıt şu öncelik sırasına göre belirlenir:
1. Yüksek `SEQUENCE` numarası.
2. Daha yeni `LAST-MODIFIED` zaman damgası.
3. Daha yeni `DTSTAMP` zaman damgası.
4. Girdi sırası (sonraki gelen girdi öncekini değiştirir).

### Satır katlama ve serileştirme nasıl yapılır?
`serialize_calendar` özellikleri deterministik sırada yazar, RFC 5545 Bölüm 3.1 gereği satırları çok baytlı karakterleri bölmeden 75 sekizlide (oktet) katlar ve satır sonlarında CRLF (`\r\n`) kullanır. `DTSTAMP` değeri eksik olan etkinliklere ilk serileştirmede bir zaman damgası atanır ve sonraki yazımlarda korunur.

### Zaman dilimleri nasıl çözümlenir?
Zaman dilimi çözümünde öncelik sistem IANA veritabanına bağlı standart Python `zoneinfo` modülündedir. TZID bulunamazsa veya sistem IANA veritabanı eksikse (özellikle saf Windows kurulumlarında), `ics-tools` yaygın Windows zaman dilimi adlarını ve takvim içindeki gömülü `VTIMEZONE` bileşenlerini yedek olarak kullanır. Çözümlenemeyen zaman dilimleri uyarı kaydederek UTC'ye döner.

### Tasarım sınırları nelerdir?
- **RFC 5545 alt kümesi**: Takvim işlemlerine odaklanmıştır. `DAILY` altındaki frekanslar (`HOURLY`, `MINUTELY`), `RDATE` süre aralıkları (`PERIOD`) ve `RANGE=THISANDFUTURE` kapsam dışındadır.
- **Çevrimdışı gizlilik**: İşlemler %100 çevrimdışı yürütülür; hiçbir ağ isteği yapılmaz.
- **Sınırsız üretim**: Sonsuz tekrar dizileri daima bir genişletme penceresi, `COUNT` veya `UNTIL` sınırı ile tüketilmelidir.

## Katkıda Bulunma

Katkılar, hata bildirimleri ve öneriler memnuniyetle karşılanır!

### Geliştirme ortamı

```sh
# Depoyu klonlayın
git clone https://github.com/YusufBeratZengin/ics-tools.git
cd ics-tools

# Geliştirme bağımlılıklarını düzenlenebilir modda kurun
python -m pip install -e ".[dev]"

# Kod stili ve linter kontrolünü çalıştırın
python -m ruff check .

# Statik tip denetimini çalıştırın
python -m mypy src tests

# Dal kapsama raporuyla test paketini çalıştırın
python -m pytest --cov=ics_tools --cov-report=term-missing

# Paket derleme ve meta veri doğrulamasını çalıştırın
python -m build
python -m twine check dist/*
```

İlgili rehberler:
- Kod kuralları ve pull request süreci için [CONTRIBUTING.md](CONTRIBUTING.md).
- Topluluk katılım standartları için [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- Güvenlik açığı bildirim süreci için [SECURITY.md](SECURITY.md).

## Lisans

Bu proje [MIT Lisansı](LICENSE) altında lisanslanmıştır.  
Telif Hakkı (c) 2026 Yusuf Berat Zengin.
