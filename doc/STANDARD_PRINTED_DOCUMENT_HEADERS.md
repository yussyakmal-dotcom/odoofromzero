# Standar Header Dokumen Cetak Odoo YA

Keputusan owner — 2026-Nov-27. Berlaku lintas modul, untuk seluruh cetakan yang memuat Source Document (termasuk label Order).

## Aturan wajib

- Source Document / Order wajib menempati satu baris/blok tersendiri selebar area cetak (100%).
- Jangan menempatkannya sejajar dalam grid atau kolom dengan Warehouse, Status, Operator, Scheduled Date maupun metadata lain.
- Bila referensi panjang, teks harus wrap secara alami ke baris berikutnya di dalam blok penuh tersebut. Jangan memotong teks atau mengurangi lebar kolom metadata lain.
- Blok metadata lain berada pada baris berikutnya. Pertahankan keterbacaan dan pemisahan visual.
- Aturan berlaku pada QWeb/PDF dan tampilan print yang relevan. Tidak mengubah arti, nilai atau relasi Source Document.

## Contoh Picking List

```
Internal Transfer
CDC/INT/00093
Order: YA-MR-60-CDC-GRG / 2026-Nov-30 / S1 / MR1

Warehouse:     Status:      Operator:        Scheduled Date:
My Company     Ready        Administrator    2026-Nov-27
```

Tanggal pada Source Document MR mengacu pada pengiriman produk jadi; Scheduled Date mengacu pada jadwal transfer bahan.

## Acceptance

Uji referensi pendek dan panjang pada PDF aktual: seluruh referensi terbaca, tidak bertabrakan dengan blok metadata lain, dan tidak terpotong pada batas halaman. Gunakan standar ini untuk cetakan baru atau revisi cetakan yang sudah ada; catat ketidaksesuaian pada cetakan existing. Tidak ada perubahan template atau transaksi dalam commit dokumentasi ini. Implementasi Picking List MR masih pending bersama revisi MR1/MR2.
