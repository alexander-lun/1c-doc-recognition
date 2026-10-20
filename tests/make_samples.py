"""Генерирует тестовые документы поставщиков в tests/samples/ и ожидаемые значения в expected.json.

    python tests/make_samples.py

Документы вымышленные; ИНН сгенерированы с корректными контрольными цифрами (кроме намеренно ошибочного).
Скан получается растеризацией PDF через pdftoppm (poppler-utils).
"""

import json
import subprocess
import tempfile
from pathlib import Path

from fpdf import FPDF

HERE = Path(__file__).parent
OUT = HERE / "samples"
FONT = "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf"


def inn10(first9):
    k = [2, 4, 10, 3, 5, 9, 4, 6, 8]
    return first9 + str(sum(int(d) * c for d, c in zip(first9, k, strict=True)) % 11 % 10)


def inn12(first10):
    k1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
    d11 = str(sum(int(d) * c for d, c in zip(first10, k1, strict=True)) % 11 % 10)
    k2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
    d12 = str(sum(int(d) * c for d, c in zip(first10 + d11, k2, strict=True)) % 11 % 10)
    return first10 + d11 + d12


def money(x):
    whole, frac = f"{x:.2f}".split(".")
    groups = []
    while whole:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    return " ".join(groups) + "," + frac


BUYER = ('ООО "Склад-Сервис"', inn10("540312345"), "540301001")

DOCS = [
    dict(
        file="upd_01.pdf",
        kind="upd",
        number="1542",
        date="2026-10-14",
        date_ru="14 октября 2026 г.",
        seller=('ООО "ЭлектроСнаб"', inn10("770123456"), "770101001"),
        items=[
            ("Кабель ВВГнг 3х2,5 (бухта 100 м)", 100, "м", 85.00),
            ("Автоматический выключатель 16А", 12, "шт", 410.00),
        ],
    ),
    dict(
        file="invoice_02.pdf",
        kind="invoice",
        number="СЧ-0087",
        date="2026-10-03",
        date_ru="03.10.2026",
        seller=('ООО "ТД Монтаж"', inn10("500198765"), "500101001"),
        items=[
            ("Розетка накладная белая", 20, "шт", 120.00),
            ("Кабель-канал 25х16", 50, "м", 64.50),
            ("Изолента ПВХ синяя 19 мм", 30, "шт", 45.00),
        ],
    ),
    dict(
        file="upd_03_bad_inn.pdf",
        kind="upd",
        number="77",
        date="2026-09-30",
        date_ru="30 сентября 2026 г.",
        seller=('ООО "Вектор"', None, "780101001"),
        items=[("Лампа светодиодная 10Вт E27", 40, "шт", 95.00)],
    ),
    dict(
        file="waybill_04_ip.pdf",
        kind="torg12",
        number="215",
        date="2026-10-10",
        date_ru="10.10.2026",
        seller=("ИП Петров Сергей Николаевич", inn12("6623012345"), ""),
        items=[("Автоматический выключатель 16А", 6, "шт", 395.00), ("Лампа светодиодная 10Вт E27", 10, "шт", 92.00)],
    ),
    dict(
        file="upd_05_scan.pdf",
        kind="upd",
        number="3310",
        date="2026-10-16",
        date_ru="16 октября 2026 г.",
        seller=('ООО "ЭлектроСнаб"', inn10("770123456"), "770101001"),
        items=[("Розетка накладная белая", 10, "шт", 118.00), ("Кабель ВВГнг 3х2,5 (бухта 100 м)", 200, "м", 84.00)],
        scan=True,
    ),
]

# Намеренно ошибочный ИНН: последняя цифра на 1 больше правильной
_good = inn10("781055555")
DOCS[2]["seller"] = (DOCS[2]["seller"][0], _good[:-1] + str((int(_good[-1]) + 1) % 10), DOCS[2]["seller"][2])

TITLES = {
    "upd": "УНИВЕРСАЛЬНЫЙ ПЕРЕДАТОЧНЫЙ ДОКУМЕНТ\nСчет-фактура № {number} от {date_ru}   Статус: 1",
    "invoice": "Счет на оплату № {number} от {date_ru}",
    "torg12": "ТОВАРНАЯ НАКЛАДНАЯ (форма ТОРГ-12)\nНомер документа {number}   Дата составления {date_ru}",
}


def line(pdf, text, height=6):
    pdf.multi_cell(0, height, text, new_x="LMARGIN", new_y="NEXT")


def render(doc, path):
    pdf = FPDF(orientation="L")
    pdf.add_font("DejaVu", "", FONT)
    pdf.add_font("DejaVu", "B", FONT_BOLD)
    pdf.add_page()

    pdf.set_font("DejaVu", "B", 12)
    line(pdf, TITLES[doc["kind"]].format(**doc), 7)
    pdf.ln(3)

    name, inn, kpp = doc["seller"]
    pdf.set_font("DejaVu", "", 10)
    if doc["kind"] == "invoice":
        line(pdf, f"Поставщик: {name}, ИНН {inn}" + (f", КПП {kpp}" if kpp else ""))
        line(pdf, f"Покупатель: {BUYER[0]}, ИНН {BUYER[1]}, КПП {BUYER[2]}")
    else:
        line(pdf, f"Продавец: {name}")
        line(pdf, f"ИНН/КПП продавца: {inn}" + (f"/{kpp}" if kpp else ""))
        line(pdf, f"Покупатель: {BUYER[0]}")
        line(pdf, f"ИНН/КПП покупателя: {BUYER[1]}/{BUYER[2]}")
    pdf.ln(4)

    widths = [10, 120, 25, 20, 40, 45]
    head = ["№", "Наименование товара", "Кол-во", "Ед.", "Цена с НДС", "Сумма с НДС"]
    pdf.set_font("DejaVu", "B", 9)
    for w, h in zip(widths, head, strict=True):
        pdf.cell(w, 8, h, border=1, align="C")
    pdf.ln()
    pdf.set_font("DejaVu", "", 9)
    total = 0
    for i, (iname, qty, unit, price) in enumerate(doc["items"], 1):
        amount = round(qty * price, 2)
        total += amount
        row = [str(i), iname, str(qty), unit, money(price), money(amount)]
        for w, v, a in zip(widths, row, "CLRCRR", strict=True):
            pdf.cell(w, 8, v, border=1, align=a)
        pdf.ln()

    pdf.set_font("DejaVu", "B", 10)
    vat = round(total * 20 / 120, 2)
    pdf.cell(sum(widths[:-1]), 8, "Всего к оплате:", align="R")
    pdf.cell(widths[-1], 8, money(total), border=1, align="R")
    pdf.ln()
    pdf.set_font("DejaVu", "", 9)
    pdf.cell(sum(widths[:-1]), 7, "в том числе НДС 20%:", align="R")
    pdf.cell(widths[-1], 7, money(vat), align="R")
    pdf.ln(12)
    pdf.cell(0, 6, "Руководитель ____________________      Главный бухгалтер ____________________")
    pdf.output(str(path))
    return round(total, 2)


def rasterize(path):
    """Превращает PDF в скан: страница → PNG 200 dpi → PDF без текстового слоя."""
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["pdftoppm", "-r", "200", "-png", "-singlefile", str(path), f"{tmp}/page"], check=True)
        pdf = FPDF(orientation="L")
        pdf.add_page()
        pdf.image(f"{tmp}/page.png", x=0, y=0, w=297)
        pdf.output(str(path))


def main():
    OUT.mkdir(exist_ok=True)
    expected = {}
    for doc in DOCS:
        path = OUT / doc["file"]
        total = render(doc, path)
        if doc.get("scan"):
            rasterize(path)
        expected[doc["file"]] = {
            "number": doc["number"],
            "date": doc["date"],
            "seller_inn": doc["seller"][1],
            "total": total,
            "items": [{"name": n, "quantity": q, "price": p, "amount": round(q * p, 2)} for n, q, _, p in doc["items"]],
            "extraction": "ocr" if doc.get("scan") else "pdf-text",
        }
    (OUT / "expected.json").write_text(json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(DOCS)} документов в {OUT}")


if __name__ == "__main__":
    main()
