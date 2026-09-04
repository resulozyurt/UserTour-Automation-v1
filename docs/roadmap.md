# Yol Haritası — UserTour Automation

Guidde PDF tutorial'larını, Usertour v2 REST API üzerinden yarı otomatik
olarak Usertour flow'larına çeviren boru hattı. İçerik üretimi ara dosyada
durup gözden geçirmeye açılır; yükleme deterministik REST script'i ile yapılır.
Selector bağlama bilinçli olarak manuel kalır (tekrar eden elementler hariç).

## Neden bu yaklaşım

- Tarayıcı otomasyonu (panelde tıklama) kırılgan; kullanılmıyor.
- v2 REST API resmi ve deterministik: aynı girdi -> aynı çıktı.
- İçerik üretimi (AI/PDF) ile yükleme birbirinden ayrık; her aşama tek tek
  kontrol edilebilir, hata izole olur.

## Usertour v2 API — kullandığımız uçlar

- `GET  /v2/me` — token'ı doğrula; proje ve environment id'lerini keşfet
- `GET  /v2/projects/{projectId}/themes` — tema listesi (themeId gerekli)
- `GET  /v2/projects/{projectId}/content` — mevcut flow'lar
- `POST /v2/projects/{projectId}/content` — flow oluştur (type=flow, name, themeId);
  otomatik bir taslak sürüm (editedVersionId) döner
- `PATCH /v2/projects/{projectId}/content/{contentId}/versions/{id}` — adımları yaz
  (steps[]; alan bazlı merge)
- `GET  /v2/projects/{projectId}/content/{contentId}/versions/{id}/validate` —
  yayınlanabilirlik kontrolü (errors/warnings)
- `POST /v2/projects/{projectId}/content/{id}/publish` — yayınla
  (body: environmentId, versionId)

Auth: `Authorization: Bearer utp_...`. Token, bir veya birden çok projeye ve
scope'lara bağlı.

## Step şeması (özet)

Bir step: `key, name, type(tooltip|modal|hidden|bubble), target, placement,
content[], triggers, onClick`. Tooltip başlığı ve metni ayrı alan değil;
`content` içinde markdown block olarak tutulur:
`{ "type": "text", "markdown": "## Title\n\nBody" }`.

Target (selector) şeması: `{ "selector": "...", "text"?: "...", "nth"?: 0 }`.
Bir target objesi varsa `selector` zorunlu.

## Faz 0 sonucu (DOĞRULANDI)

Gerçek API çağrısıyla test edildi (faz0_probe.py):

- Target'sız tooltip step'i TASLAK olarak kaydediliyor (HTTP 200).
- validate, target'sız step için hata veriyor: "Tooltip step has no target
  element; the SDK skips it." Yani yayın (publish) için selector zorunlu,
  taslak için değil.
- Target eklenince validate ok=True.

Sonuç (mevcut tasarım doğru): builder, selector'ı çözülemeyen step'lerde target'ı
hiç göndermez; bu step'ler taslakta durur, validate onları tek tek listeler, sen
panelde OpenPicker ile bağlarsın, sonra yayınlanır. Tekrar eden elementler
selectors.yaml'dan otomatik çözülür.

## Fazlar

- Faz 0 — API doğrulaması: TAMAMLANDI (faz0_probe.py). Bulgular yukarıda.
- Faz 1 — Ara format + tek flow uçtan uca: `schema/flow.example.yaml` -> panelde
  doğru görünen bir flow. (Bu commit ile iskelet hazır.)
- Faz 2 — Selector sözlüğü: tekrar eden elementleri `schema/selectors.yaml`'a taşı;
  yeni flow'ların ortak adımları otomatik bağlansın.
- Faz 3 — PDF -> ara YAML üretimi: guidde PDF'ini okuyup taslak flow üret
  (gözden geçirmeye açık; otomatik yayınlamaz).
- Faz 4 — Akış: PDF ver -> taslak üret -> gözden geçir -> yükle -> panelde yalnız
  yeni selector'ları doldur -> yayınla.

## İçerik kuralları (özet)

Native American English; temel bilgi düzeyi; kaynağa sadık (adım ekleme/çıkarma
yok); aynı satırdaki alanlar tek adım; welcome/intro modalı yok; 3+ tekrar eden
grup bir örnek + tek özet adım. Target ve teknik notlar Türkçe; tooltip içerikleri
İngilizce.
