# Merch-M015-Add Workflow to Form

Source: source.pdf (guidde "Add Workflow to Form")

## Revizyon notları
Buraya flow'a özel değişiklik isteklerini yaz; bir sonraki turda flow.yaml güncellenir.

## Uygulanan kurallar (panel geri bildirimine göre)
- Placement her adımda Auto (alignType: auto).
- Tooltip'lerde H2 başlık yok; sadece gövde metni.
- Bold (**...**) tema üzerinden marka rengiyle (#018478) render olur; içerikte renk alanı yok.
- Her adımda "Next ->" butonu + onClick ile sonraki adıma geçiş (goto_step).
- Son adımdan sonra kapanış modalı (Finish Screen), M014'ün son ekranına göre uyarlandı.

## Kararlar
- 00 Introduction ve 09 "Collapse Current Section" atlandı (intro / açıklama yok).
- Aksiyonla uyuşmayan başlıklar düzeltildi (02, 03, 06, 11, 12).
- M014'teki "Invite Your Users ->" (başka flow'a zincirleme) butonu alınmadı; onun yerine
  "Finish" (dismiss) + "Go back to home" konuldu. İstenirse zincirleme eklenir.
- Adımlarda sayfa değiştiren `navigate` URL'leri eklenmedi (PDF'te net değil); gerekirse
  her adıma `url:` eklenebilir.

## Selector durumu
- forms-menu, pencil-icon -> schema/selectors.yaml doldurulunca otomatik bağlanır.
- Diğer 12 adımın selector'ı panelde manuel bağlanacak (bkz. her adımın `note` alanı).
