# ics-tools

[![CI](https://github.com/YusufBeratZengin/ics-tools/actions/workflows/ci.yml/badge.svg)](https://github.com/YusufBeratZengin/ics-tools/actions/workflows/ci.yml) [![PyPI - Version](https://img.shields.io/pypi/v/ics-tools.svg)](https://pypi.org/project/ics-tools/) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE) [![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](pyproject.toml) [![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](pyproject.toml)

iCalendar (.ics) dosyalarını okuyun, birleştirin, filtreleyin, doğrulayın ve CSV'ye aktarın; tekrar eden etkinlikleri tarih aralığında listeleyin.
Yalnızca Python standart kütüphanesini kullanır ve çevrimdışı çalışır.

Depo kökünde kurulum: `python -m pip install .`
İlk deneme: `ics validate examples/demo.ics`

[English](README.md) | [Türkçe](README.tr.md)

Paket henüz PyPI'da yayımlanmadı; sürüm rozeti ilk yayından sonra görünecek. Şimdilik kaynak koddan kurabilirsiniz.

## Demo

![ics-tools CLI Demo](docs/demo.svg)

## Why ics-tools?

- **Ek paket gerektirmez**: `zoneinfo`, `re`, `datetime`, `csv` ve `argparse` gibi Python standart kütüphanesi modülleriyle çalışır. Kullanım için üçüncü taraf bağımlılık kurmanız gerekmez.
- **Veriler bilgisayarınızda kalır**: Takvim okuma, filtreleme ve tekrarları listeleme işlemleri çevrimdışı yapılır. Takvim kayıtları, konumlar ve notlar dışarı gönderilmez.
- **Tekrar eden etkinlikleri işler**: Günlük, haftalık, aylık ve yıllık kuralları; tarih filtreleri, tekrar sınırları, istisnalar ve `RECURRENCE-ID` ile değiştirilmiş kayıtlarla birlikte işler. Desteklenen RFC 5545 özellikleri aşağıdaki tabloda yer alır.

## Quick start

Python 3.10 veya üstü gerekir. Komutları kaynak kodun bulunduğu depo kökünde çalıştırın:

```sh
# Depo kök dizininde kurulum
python -m pip install .

# Bir iCalendar dosyasını doğrulama
ics validate examples/demo.ics

# 7 günlük pencerede yinelenen etkinlikleri listeleme
ics list examples/demo.ics --from 2026-01-01 --window 7d
```

> Kurulan komutun adı `ics` olur. Aynı doğrulama işlemini `python -m ics_tools validate examples/demo.ics` ile de çalıştırabilirsiniz.

## Usage examples

### Command-line interface (CLI)

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

- Tüm komutlar `-` verildiğinde standart girdiden (`stdin`) okur. Filter, list ve to-csv komutlarında dosya belirtilmezse de stdin kullanılır. Merge ve validate komutlarında dosya yollarıyla birlikte bir kez `-` kullanılabilir.
- Geçersiz argümanlar ve çözümlenemeyen açık `--tz` değerleri, kullanım hatasıyla ve çıkış kodu 2 ile sonuçlanır. Takvim doğrulama hatalarında çıkış kodu 1 olur.
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

# Takvimleri birleştirme; aynı UID + RECURRENCE-ID çiftine sahip kayıtları tekilleştirme
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

Takvim birleştirme, filtreleme, CSV dışa aktarımı ve programatik takvim oluşturma gibi daha fazla çalıştırılabilir örnek için [examples/](examples/) dizinini inceleyebilirsiniz.

## Configuration & options

### CLI parameters

| Seçenek | Komut | Açıklama |
| --- | --- | --- |
| `--from`, `--to` | `filter`, `list`, `to-csv` | ISO 8601 tarih (`YYYY-MM-DD`) veya tarih-saat (`YYYY-MM-DDTHH:MM:SSZ`). Yalnız tarih verildiğinde gece yarısı (UTC) kabul edilir. |
| `--window` | `list`, `to-csv` | Süre kısaltması: `30d` (gün), `2w` (hafta), `24h` (saat) veya `1m` (30 gün). Açıkça verilen `--to` bu değere önceliklidir. |
| `--tz` | `list`, `to-csv` | Hedef IANA zaman dilimi adı (örn. `Europe/Istanbul`, `America/New_York`) veya desteklenen Windows zaman dilimi adı. Çözümlenemeyen değerlerde çıkış kodu 2 olur. |
| `--match` | `filter` | `SUMMARY`, `DESCRIPTION`, `LOCATION` ve `CATEGORIES` alanlarında aranan düzenli ifade (regex). |
| `-i`, `--case-sensitive` | `filter` | Büyük/küçük harfe duyarlı regex eşleşmesi uygular (varsayılan: duyarsız). |
| `--raw` | `to-csv` | Tekrar eden etkinlikleri açmadan ham kayıtları CSV'ye aktarır. |
| `-o`, `--output` | `merge`, `filter`, `to-csv` | Hedef dosya yolu. Eksik üst klasörler otomatik olarak oluşturulur. |

### Recurrence rules & spec support

| Özellik | Destek Durumu |
| --- | --- |
| **Frekanslar** | `DAILY`, `WEEKLY`, `MONTHLY`, `YEARLY` |
| **Kural parçaları** | `INTERVAL`, `COUNT`, `UNTIL`, `BYDAY` (sayısal sıra belirteçleriyle, örn. `2MO`, `-1FR`), `BYMONTHDAY`, `BYMONTH`, `BYSETPOS`, `WKST` |
| **İstisnalar** | `EXDATE`, `RDATE` (`VALUE=DATE` ve `VALUE=DATE-TIME`) ve `RECURRENCE-ID` ile değiştirilmiş veya iptal edilmiş tekrarlar |

## FAQ & Limitations

### How does deduplication work?
`merge_calendars`, aynı `(UID, RECURRENCE-ID)` çiftine sahip kayıtları tekilleştirir. Hangi kaydın korunacağı şu sırayla belirlenir:
1. Yüksek `SEQUENCE` numarası.
2. Daha yeni `LAST-MODIFIED` zaman damgası.
3. Daha yeni `DTSTAMP` zaman damgası.
4. Girdi sırası (eşitlik sürerse son gelen kayıt korunur).

### How is line folding and serialization handled?
`serialize_calendar`, özellikleri her seferinde aynı sırayla yazar. RFC 5545 Bölüm 3.1'e uygun olarak, çok baytlı UTF-8 karakterleri bölmeden satırları 75 baytta katlar ve CRLF (`\r\n`) satır sonu kullanır. `DTSTAMP` değeri eksikse ilk yazımda atanır ve sonraki yazımlarda korunur.

### How are timezones resolved?
Önce Python `zoneinfo` modülüyle sistemin IANA veritabanına bakılır. TZID bulunamazsa veya veritabanı yoksa (bazı Windows kurulumlarında olduğu gibi), yaygın zaman dilimleri için yerleşik tanımlar, Windows adları ve takvime gömülü `VTIMEZONE` bileşenleri kullanılır. Takvim dosyasında çözümlenemeyen TZID için uyarı yazılır ve UTC kullanılır. CLI'da açıkça verilen `--tz` değeri çözümlenemiyorsa komut, çıkış kodu 2 ile hata verir.

### What are the design limits?
- **RFC 5545 alt kümesi**: Takvim işlemlerine odaklanmıştır. `DAILY` altındaki frekanslar (`HOURLY`, `MINUTELY`), `RDATE` süre aralıkları (`PERIOD`) ve `RANGE=THISANDFUTURE` kapsam dışındadır.
- **Çevrimdışı gizlilik**: İşlemler %100 çevrimdışı yürütülür; hiçbir ağ isteği yapılmaz.
- **Sonsuz tekrarlar**: Bitiş tarihi olmayan tekrarları işlerken bir tarih aralığı, `COUNT` veya `UNTIL` sınırı kullanın.

## Contributing

Katkılar, hata bildirimleri ve öneriler memnuniyetle karşılanır!

### Development setup

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

# Branch coverage raporuyla testleri çalıştırın
python -m pytest --cov=ics_tools --cov-report=term-missing

# Paket derleme ve meta veri doğrulamasını çalıştırın
python -m build
python -m twine check dist/*

# Gerçek CLI çıktısıyla demo görselini yeniden üretin
python scripts/make-demo.py
```

İlgili rehberler:

- Kod kuralları ve pull request süreci için [CONTRIBUTING.md](CONTRIBUTING.md).
- Topluluk katılım standartları için [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- Güvenlik açığı bildirim süreci için [SECURITY.md](SECURITY.md).

## License

Bu proje [MIT Lisansı](LICENSE) altında lisanslanmıştır.  
Telif Hakkı (c) 2026 Yusuf Berat Zengin.
