from app.channel.inbox import copy_to_inbox, guess_supplier, list_seed_files
from app.channel.outbox import write_eml


def test_guess_supplier_from_filename():
    assert guess_supplier("S1_Fjordline_quotation.xlsx") == "Fjordline Seafood AS"
    assert guess_supplier("S4_Oceanis_ratecard_photo.jpg") == "Oceanis Trading SARL"
    assert guess_supplier("unrelated_file.txt") is None


def test_list_seed_files_finds_all_replies_and_certs():
    files = list_seed_files()
    names = [f.name for f in files]
    assert "S1_Fjordline_quotation.xlsx" in names
    assert "S4_Oceanis_food_safety_certificate.pdf" in names
    assert len(files) == 9  # 5 replies + 4 certificates


def test_copy_to_inbox(tmp_path, monkeypatch):
    import app.channel.inbox as inbox_module
    import app.config as config_module

    monkeypatch.setattr(config_module.settings, "data_dir", tmp_path)
    monkeypatch.setattr(inbox_module, "SEED_REPLIES", tmp_path / "seed_src")
    (tmp_path / "seed_src").mkdir()
    src = tmp_path / "seed_src" / "S1_test.xlsx"
    src.write_bytes(b"fake xlsx content")

    dest = copy_to_inbox(src)
    assert dest.exists()
    assert dest.read_bytes() == b"fake xlsx content"


def test_write_eml_creates_file(tmp_path, monkeypatch):
    import app.channel.outbox as outbox_module

    monkeypatch.setattr(outbox_module.settings, "data_dir", tmp_path)
    path = write_eml("sales@fjordline.example", "RFQ: Test", "Hello supplier")
    assert path.exists()
    content = path.read_text()
    assert "Hello supplier" in content
    assert "sales@fjordline.example" in content
