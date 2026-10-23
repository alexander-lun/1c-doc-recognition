"""Генерирует тестовые УПД в формате ФНС (XML, как они приходят по ЭДО) в tests/samples/.

    python tests/make_xml_samples.py

Структура упрощена до реквизитов, которые читает 1С, но имена элементов и атрибутов - как в формате ФНС:
5.03 (КНД 1115131, НомерДок/ДатаДок) и 5.01 (КНД 1115125, НомерСчФ/ДатаСчФ). Кодировка windows-1251.
"""

import json
from pathlib import Path
from xml.sax.saxutils import quoteattr

from make_samples import BUYER, inn10, inn12

HERE = Path(__file__).parent
OUT = HERE / "samples"
VAT = 20

DOCS = [
    dict(
        file="upd_06_edo.xml",
        version="5.03",
        number="1601",
        date="2026-10-18",
        seller=dict(org='ООО "ЭлектроСнаб"', inn=inn10("770123456"), kpp="770101001"),
        items=[
            # наименование, код товара (артикул), единица, количество, сумма с НДС
            ("Кабель ВВГнг 3х2,5 (бухта 100 м)", "RD-CABLE", "м", 50, 4250.00),
            ("Выключатель автоматический ВА47-29 1P 16А", "RD-QF16", "шт", 4, 1640.00),
            ("Розетка накладная белая", "", "шт", 10, 1180.00),
        ],
    ),
    dict(
        file="upd_07_edo_ip_501.xml",
        version="5.01",
        number="44",
        date="2026-10-19",
        seller=dict(ip=("Петров", "Сергей", "Николаевич"), inn=inn12("6623012345")),
        items=[
            # цена с НДС 333,333... - сумма не делится на количество нацело
            ("Кабель-канал 25х16", "", "м", 3, 1000.00),
            ("Лампа светодиодная 10Вт E27", "RD-LAMP", "шт", 7, 665.00),
        ],
    ),
]


def ru_date(iso):
    y, m, d = iso.split("-")
    return f"{d}.{m}.{y}"


def party(p):
    if "org" in p:
        ident = f'<СвЮЛУч НаимОрг={quoteattr(p["org"])} ИННЮЛ="{p["inn"]}" КПП="{p["kpp"]}"/>'
    else:
        last, first, middle = p["ip"]
        ident = f'<СвИП ИННФЛ="{p["inn"]}"><ФИО Фамилия="{last}" Имя="{first}" Отчество="{middle}"/></СвИП>'
    return f'<ИдСв>{ident}</ИдСв><Адрес><АдрИнф КодСтр="643" АдрТекст="г. Москва"/></Адрес>'


def money(x):
    return f"{x:.2f}"


def render(doc):
    v503 = doc["version"] == "5.03"
    num_attr, date_attr = ("НомерДок", "ДатаДок") if v503 else ("НомерСчФ", "ДатаСчФ")
    knd = "1115131" if v503 else "1115125"
    rows, total, total_net, total_vat = [], 0.0, 0.0, 0.0
    for i, (name, code, unit, qty, amount) in enumerate(doc["items"], 1):
        net = round(amount * 100 / (100 + VAT), 2)
        vat = round(amount - net, 2)
        total, total_net, total_vat = total + amount, total_net + net, total_vat + vat
        extra = f'<ДопСведТов КодТов="{code}"/>' if code else "<ДопСведТов/>"
        rows.append(
            f'<СведТов НомСтр="{i}" НаимТов={quoteattr(name)} ОКЕИ_Тов="796" НаимЕдИзм="{unit}" '
            f'КолТов="{qty}" ЦенаТов="{net / qty:.2f}" СтТовБезНДС="{money(net)}" НалСт="{VAT}%" '
            f'СтТовУчНал="{money(amount)}"><Акциз><БезАкциз>без акциза</БезАкциз></Акциз>'
            f"<СумНал><СумНал>{money(vat)}</СумНал></СумНал>{extra}</СведТов>"
        )
    seller_id = doc["seller"]["inn"]
    buyer = dict(org=BUYER[0], inn=BUYER[1], kpp=BUYER[2])
    xml = (
        '<?xml version="1.0" encoding="windows-1251"?>\n'
        f'<Файл ИдФайл="ON_NSCHFDOPPR_{BUYER[1]}_{seller_id}_{doc["number"]}" '
        f'ВерсФорм="{doc["version"]}" ВерсПрог="test">'
        f'<СвУчДокОбор ИдОтпр="2BM-{seller_id}" ИдПол="2BM-{BUYER[1]}"/>'
        f'<Документ КНД="{knd}" Функция="СЧФДОП" ДатаИнфПр="{ru_date(doc["date"])}" ВремИнфПр="10.00.00">'
        f'<СвСчФакт {num_attr}="{doc["number"]}" {date_attr}="{ru_date(doc["date"])}" КодОКВ="643">'
        f"<СвПрод>{party(doc['seller'])}</СвПрод><СвПокуп>{party(buyer)}</СвПокуп>"
        "</СвСчФакт>"
        f"<ТаблСчФакт>{''.join(rows)}"
        f'<ВсегоОпл СтТовБезНДСВсего="{money(total_net)}" СтТовУчНалВсего="{money(total)}">'
        f"<СумНалВсего><СумНал>{money(total_vat)}</СумНал></СумНалВсего></ВсегоОпл></ТаблСчФакт>"
        "</Документ></Файл>\n"
    )
    (OUT / doc["file"]).write_bytes(xml.encode("cp1251"))
    return round(total, 2)


def main():
    OUT.mkdir(exist_ok=True)
    expected = {}
    for doc in DOCS:
        total = render(doc)
        expected[doc["file"]] = {
            "number": doc["number"],
            "date": doc["date"],
            "seller_inn": doc["seller"]["inn"],
            "total": total,
            "items": [
                {"name": n, "code": c, "quantity": q, "price": round(a / q, 2), "amount": a}
                for n, c, _, q, a in doc["items"]
            ],
        }
    (OUT / "expected_xml.json").write_text(json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(DOCS)} документов в {OUT}")


if __name__ == "__main__":
    main()
