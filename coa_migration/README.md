# DRAFT pemetaan COA YA - Odoo 19

Sumber: `COA_Bersih_Import.csv` (391 akun) dan laporan audit read-only `erp-yussyakmal` tanggal 19 November 2026 (118 akun Odoo).

**JANGAN IMPOR FILE DRAFT INI LANGSUNG.** File dibuat sebagai hasil pemetaan awal, bukan perubahan yang sudah disetujui dan diuji di Odoo.

- `DRAFT_COA_01_Update_Existing.csv`: 15 akun Odoo dengan kode yang sudah cocok; kandidat pembaruan nama dan tipe melalui External ID.
- `DRAFT_COA_02_Import_New.csv`: 366 akun YA dengan kode yang belum ada dan tidak tercakup dalam pemetaan teknis khusus.
- `COA_03_Review.csv`: 10 akun yang harus ditangani secara terpisah. Termasuk benturan kode outstanding payment, suspense, receivable/payable, stock interim, pinjaman jangka panjang, dan current-year earnings.

Langkah wajib sebelum impor: selesaikan 10 item review, verifikasi seluruh dependensi akun default perusahaan/jurnal/kategori, cocokkan juga akun bawaan dengan fungsi sama tetapi kode berbeda, pastikan label Type sesuai field Odoo 19, kemudian uji impor pada backup/clone. Akun bawaan tidak boleh dihapus hanya karena tidak terdapat di master YA.

Untuk regenerasi dari hasil audit terbaru: `python3 script/build_coa_import_plan.py AUDIT_REPORT MASTER_CSV OUTPUT_DIR`.
