"""Tests for parse_rights_xml (M-K3.17.2 RLS) — права + RLS-условия из Rights.xml."""

from __future__ import annotations

from app.knowledge.typical.xml_parser import parse_rights_xml

RIGHTS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Rights xmlns="http://v8.1c.ru/8.2/roles" version="2.20">
  <object>
    <name>Document.ОПП</name>
    <right>
      <name>Read</name>
      <value>true</value>
      <restrictionByCondition>
        <condition>ВладелецДокумента = &amp;ТекущийПользователь</condition>
      </restrictionByCondition>
    </right>
    <right>
      <name>Update</name>
      <value>false</value>
    </right>
  </object>
  <object>
    <name>Catalog.Контрагенты</name>
    <right>
      <name>View</name>
      <value>true</value>
    </right>
  </object>
</Rights>
"""


def test_parse_rights_xml_basic(tmp_path):
    f = tmp_path / "Rights.xml"
    f.write_text(RIGHTS_XML, encoding="utf-8")
    rights = parse_rights_xml(f)
    assert len(rights) == 3
    by_key = {(r.object_name, r.right_name): r for r in rights}

    read = by_key[("Document.ОПП", "Read")]
    assert read.value is True
    assert read.condition == "ВладелецДокумента = &ТекущийПользователь"

    upd = by_key[("Document.ОПП", "Update")]
    assert upd.value is False
    assert upd.condition is None

    view = by_key[("Catalog.Контрагенты", "View")]
    assert view.value is True
    assert view.condition is None


def test_parse_rights_xml_cp1251_fallback(tmp_path):
    """1С иногда пишет Rights.xml в cp1251 при declaration UTF-8 → ридер устойчив."""
    f = tmp_path / "Rights.xml"
    f.write_bytes(RIGHTS_XML.encode("cp1251"))
    rights = parse_rights_xml(f)
    assert len(rights) == 3
    read = next(r for r in rights if r.right_name == "Read")
    assert read.object_name == "Document.ОПП"
    assert read.condition == "ВладелецДокумента = &ТекущийПользователь"


def test_parse_rights_xml_empty(tmp_path):
    f = tmp_path / "Rights.xml"
    f.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Rights xmlns="http://v8.1c.ru/8.2/roles" version="2.20"/>',
        encoding="utf-8",
    )
    assert parse_rights_xml(f) == []
