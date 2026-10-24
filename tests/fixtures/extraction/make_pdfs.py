from pathlib import Path


CALL = [
    [
        (72, 760, 18, "Open Atlas Fellowship 2027"),
        (72, 730, 11, "Call for proposals issued by the Lindqvist Foundation for Open Science."),
        (72, 700, 11, "The fellowship funds early-career researchers who build open reference atlases"),
        (72, 685, 11, "of human tissues. Applicants must hold a doctorate awarded no more than seven"),
        (72, 670, 11, "years before the first deadline. Projects run for up to 36 months."),
        (72, 640, 11, "Proposals are submitted in two stages. The funding rounds, their deadlines and"),
        (72, 625, 11, "their budgets are listed in the table on page 2."),
    ],
    [
        (72, 760, 14, "Funding rounds"),
        (72, 730, 11, "Round"),
        (200, 730, 11, "Deadline"),
        (360, 730, 11, "Budget"),
        (72, 712, 11, "Pre-proposal"),
        (200, 712, 11, "15 January 2027"),
        (360, 712, 11, "no funding"),
        (72, 694, 11, "Full proposal"),
        (200, 694, 11, "30 April 2027"),
        (360, 694, 11, "1 500 000 EUR"),
        (72, 676, 11, "Renewal"),
        (200, 676, 11, "1 March 2029"),
        (360, 676, 11, "750 000 EUR"),
        (72, 646, 11, "All amounts are maximum budgets per project."),
    ],
]


def content(lines: list[tuple[int, int, int, str]]) -> bytes:
    commands = [f"BT /F1 {size} Tf {x} {y} Td ({text}) Tj ET" for x, y, size, text in lines]
    return "\n".join(commands).encode("latin-1")


REPORT = [
    [
        (72, 770, 9, "ANNUAL REPORT 2026 | Spatial Atlas Group"),
        (72, 730, 16, "Annual report of the Spatial Atlas Group"),
        (72, 700, 11, "Dr. Ines Navarro leads the Spatial Atlas Group at the Lindqvist Institute."),
        (72, 685, 11, "The group maps human lung tissue with spatial transcriptomics."),
        (300, 40, 9, "Page 1 of 3"),
    ],
    [
        (72, 770, 9, "ANNUAL REPORT 2026 | Spatial Atlas Group"),
        (72, 730, 11, "In 2026 the group released an atlas of 120 lung samples."),
        (300, 40, 9, "Page 2 of 3"),
    ],
    [
        (72, 770, 9, "ANNUAL REPORT 2026 | Spatial Atlas Group"),
        (72, 730, 11, "The group thanks the Lindqvist Foundation for Open Science for its support."),
        (300, 40, 9, "Page 3 of 3"),
    ],
]


def build(pages: list[list[tuple[int, int, int, str]]]) -> bytes:
    page_ids = [3 + 2 * index for index in range(len(pages))]
    font_id = 3 + 2 * len(pages)
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: f"<< /Type /Pages /Kids [{' '.join(f'{i} 0 R' for i in page_ids)}] /Count {len(pages)} >>".encode(),
        font_id: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    }
    for page_id, lines in zip(page_ids, pages):
        stream = content(lines)
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {page_id + 1} 0 R "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>"
        ).encode()
        objects[page_id + 1] = b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"
    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += b"%d 0 obj\n" % number + objects[number] + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offsets[number] for number in sorted(objects))
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


if __name__ == "__main__":
    (Path(__file__).parent / "call.pdf").write_bytes(build(CALL))
    (Path(__file__).parent / "report.pdf").write_bytes(build(REPORT))
