import os
import re
import logging
import pdfplumber
from tabulate import tabulate
from multiprocessing import Pool, cpu_count

class PDFProcessor:
    def __init__(self):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
        self.subscript_mapping = {str(i): chr(8320 + i) for i in range(10)}
        self.superscript_mapping = {
            '0': '\u2070', '1': '\u00B9', '2': '\u00B2', '3': '\u00B3',
            '4': '\u2074', '5': '\u2075', '6': '\u2076', '7': '\u2077',
            '8': '\u2078', '9': '\u2079', '+': '\u207A', '-': '\u207B', '−': '\u207B'
        }
        self.subscript_to_digit = {chr(8320 + i): str(i) for i in range(10)}
        self.exclude_keywords = [
            "FHSST Authors", "Copyright", "Contents", "Contributors", "CONTENTS",
            "FHSST Core Team", "www.fhsst.org", "Permission is granted"
        ]
        self.roman_numeral_re = re.compile(r'^[IVXLCDM]+$', re.IGNORECASE)
        self.toc_table_pattern = re.compile(r'(\b\d+\.\d+(\.\d+)*\b.*?\.\.\.\s*\d+)', flags=re.IGNORECASE)
        self.toc_text_pattern = re.compile(r'\d+\.\d+.*\.\.\.\s*\d+')

    @staticmethod
    def fix_broken_chemical_formulas(text):
        return re.sub(r'\b([A-Z][a-z]?)\s+(\d+)\b', r'\1\2', text)

    def apply_unit_superscript(self, text):
        units = [
            'cm³', 'dm³', 'm³',
            'mℓ', 'kℓ', 'ℓ',
            'cm', 'mm', 'km', 'dm', 'm',
            's', 'm · s', 'm·s', 'hr', 'km·h'
        ]
        units_sorted = sorted(units, key=len, reverse=True)
        pattern = r'(?<!\w)(' + '|'.join(re.escape(u) for u in units_sorted) + r')([+\-−]?\d+)'
        return re.sub(pattern, lambda m: m.group(1) + ''.join(self.superscript_mapping.get(ch, ch) for ch in m.group(2)), text)

    def apply_subscript(self, text):
        return re.sub(r'([A-Za-z])(\d+)', lambda m: m.group(1) + ''.join(self.subscript_mapping.get(d, d) for d in m.group(2)), text)

    def fix_ion_charge(self, text):
        text = re.sub(
            r'(?<![₀-₉])([₀-₉])([₀-₉])([+\-−])',
            lambda m: m.group(1) +
                      self.superscript_mapping.get(self.subscript_to_digit.get(m.group(2), m.group(2)), m.group(2)) +
                      self.superscript_mapping.get(m.group(3), m.group(3)),
            text
        )
        text = re.sub(
            r'(?<![₀-₉])([₀-₉])([+\-−])',
            lambda m: m.group(1) +
                      self.superscript_mapping.get(m.group(2), m.group(2)),
            text
        )
        text = re.sub(
            r'([A-Za-z])([+\-−])(?!\d)',
            lambda m: m.group(1) +
                      self.superscript_mapping.get(m.group(2), m.group(2)),
            text
        )
        return text

    def apply_superscript(self, text):
        def process_exponent(exp_sign, digits):
            if re.fullmatch(r'0+', digits):
                return exp_sign + digits
            stripped = digits.lstrip('0')
            return exp_sign + (stripped if stripped else '0')

        def repl_scientific(match):
            notation = match.group(1)
            exp_sign = match.group(2)
            digits = match.group(3)
            if exp_sign == '' and re.fullmatch(r'0+', digits):
                return f"{notation}10{digits}"
            processed = process_exponent(exp_sign, digits)
            return f"{notation}10{''.join(self.superscript_mapping.get(c, c) for c in processed)}"

        def repl_standalone(match):
            exp_sign = match.group(1)
            digits = match.group(2)
            if exp_sign == '' and re.fullmatch(r'0+', digits):
                return f"10{digits}"
            processed = process_exponent(exp_sign, digits)
            return f"10{''.join(self.superscript_mapping.get(c, c) for c in processed)}"

        text = re.sub(r'([×x])\s*10([+\-−]?)(\d+)', repl_scientific, text)
        text = re.sub(r'(?<!\d)10([+\-−])(\d+)(?!\d)', repl_standalone, text)
        return text

    @staticmethod
    def fix_temperature_units(text):
        pattern = re.compile(r'(\d+)\s*([CFK])\b')

        def replace_temp(match):
            start = match.start()
            context = text[max(0, start - 20):start]
            if re.search(r'×\s*10', context):
                return match.group(0).replace("°", "")
            else:
                num_str = match.group(1).lstrip('0')
                if not num_str:
                    num_str = '0'
                else:
                    if num_str.endswith('0'):
                        num_str = num_str[:-1]
                return f"{num_str}°{match.group(2)}"

        text = pattern.sub(replace_temp, text)
        text = re.sub(
            r'(\(\s*)0°([CFK]\s*\))',
            lambda m: f"{m.group(1)}°{m.group(2)}",
            text,
            flags=re.IGNORECASE
        )
        return text

    def fix_plain_exponents(self, text):
        allowed_exponents = {"1", "2", "3", "6", "9", "12", "15", "18", "21", "24"}

        def repl(m):
            exponent = m.group(1)
            if exponent in allowed_exponents:
                return "10" + ''.join(self.superscript_mapping.get(ch, ch) for ch in exponent)
            return m.group(0)

        pattern = re.compile(r'\b10(\d{1,2})\b')
        return pattern.sub(repl, text)

    def preprocess_text(self, text):
        text = self.fix_broken_chemical_formulas(text)
        text = self.apply_unit_superscript(text)
        text = self.apply_subscript(text)
        text = self.fix_ion_charge(text)
        text = self.fix_temperature_units(text)
        text = self.apply_superscript(text)
        text = self.fix_plain_exponents(text)
        return text

    def transform_table_cell(self, cell_text):
        if not cell_text:
            return cell_text
        s = cell_text.strip()
        m = re.fullmatch(r'10([+\-]?)(\d+)', s)
        if m:
            sign, digits = m.group(1), m.group(2)
            allowed_positive = {"24", "21", "18", "15", "12", "9", "6", "3", "2", "1"}
            allowed_negative = {"1", "2", "3", "6", "9", "12", "15", "18", "21", "24"}
            if sign == '' and digits in allowed_positive:
                return "10" + ''.join(self.superscript_mapping.get(c, c) for c in digits)
            elif sign in ['-', '−'] and digits in allowed_negative:
                return "10" + self.superscript_mapping.get(sign, sign) + ''.join(
                    self.superscript_mapping.get(c, c) for c in digits)
        return cell_text

    def should_exclude_page(self, tables, lines):
        exclude = False
        for table in tables:
            for row in table:
                for cell in row:
                    if cell and self.toc_table_pattern.search(cell):
                        exclude = True
                        break
                if exclude:
                    break
            if exclude:
                break

        if exclude:
            return True

        text_content = "\n".join(lines)
        preprocessed_text = self.preprocess_text(text_content)

        if any(keyword in preprocessed_text for keyword in self.exclude_keywords):
            return True

        stripped_text = preprocessed_text.strip()
        if self.roman_numeral_re.fullmatch(stripped_text):
            return True

        if self.toc_text_pattern.search(preprocessed_text):
            return True

        return False

    def extract_and_preprocess_pdf(self, pdf_path, page_numbers=None, save_to_file=True):
        """
        Extract and preprocess PDF content with option to save text file and return text directly

        Args:
            pdf_path: Path to the PDF file
            page_numbers: List of specific pages to process (None for all pages)
            save_to_file: Whether to save extracted text to txtBook folder

        Returns:
            str: Extracted and preprocessed text, or None if error
        """
        full_text = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    if page_numbers and page_num not in page_numbers:
                        continue

                    tables = page.extract_tables(table_settings={
                        "vertical_strategy": "lines",
                        "horizontal_strategy": "lines",
                        "intersection_tolerance": 5,
                        "text_x_tolerance": 2,
                        "text_y_tolerance": 6,
                    })

                    found_tables = page.find_tables(table_settings={
                        "vertical_strategy": "lines",
                        "horizontal_strategy": "lines",
                        "intersection_tolerance": 5,
                        "text_x_tolerance": 2,
                        "text_y_tolerance": 6,
                    })
                    table_bboxes = [tbl.bbox for tbl in found_tables]

                    words = page.extract_words(x_tolerance=2, y_tolerance=6)
                    non_table_words = []
                    for word in words:
                        cx = (word['x0'] + word['x1']) / 2
                        cy = (word['top'] + word['bottom']) / 2
                        if any(tb[0] <= cx <= tb[2] and tb[1] <= cy <= tb[3] for tb in table_bboxes):
                            continue
                        non_table_words.append(word)

                    lines = []
                    current_line = []
                    current_top = None
                    for word in non_table_words:
                        if current_top is None or abs(word['top'] - current_top) > 5:
                            if current_line:
                                lines.append(" ".join(w[1] for w in sorted(current_line, key=lambda x: x[0])))
                                current_line = []
                            current_top = word['top']
                        current_line.append((word['x0'], word['text']))
                    if current_line:
                        lines.append(" ".join(w[1] for w in sorted(current_line, key=lambda x: x[0])))

                    if self.should_exclude_page(tables, lines):
                        continue

                    table_content = []
                    for table in tables:
                        processed_table = [
                            [self.transform_table_cell(self.preprocess_text(cell)) if cell else "" for cell in row]
                            for row in table]
                        table_content.append(tabulate(processed_table, headers="firstrow", tablefmt="grid"))

                    page_text = []
                    if table_content:
                        page_text.append("\n--- Tables ---\n" + "\n\n".join(table_content))
                    if lines:
                        preprocessed_text = self.preprocess_text("\n".join(lines))
                        page_text.append(preprocessed_text)

                    full_text.append("\n".join(page_text))

            extracted_text = "\n".join(full_text)

            if save_to_file and extracted_text:
                try:
                    pdf_directory = os.path.dirname(pdf_path)
                    txt_folder = os.path.join(pdf_directory, "txtBook")
                    os.makedirs(txt_folder, exist_ok=True)

                    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
                    output_path = os.path.join(txt_folder, f"{base_name}.txt")

                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(extracted_text)

                    logging.info(f"Text saved to: {output_path}")

                except Exception as save_error:
                    logging.error(f"Failed to save text file: {save_error}")

            return extracted_text

        except Exception as e:
            logging.error(f"Error processing {pdf_path}: {e}", exc_info=True)
            return None

    def process_pdf(self, pdf_path):
        try:
            logging.info(f"Processing {pdf_path}...")
            text = self.extract_and_preprocess_pdf(pdf_path)
            if text:
                output_path = pdf_path.replace(".pdf", ".txt")
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(text)
                logging.info(f"Saved to {output_path}")
            else:
                logging.warning(f"No text extracted from {pdf_path}")
        except Exception as e:
            logging.error(f"Failed to process {pdf_path}: {e}", exc_info=True)

    def process_pdf_folder(self, pdf_folder):
        try:
            pdf_files = []
            for root, _, files in os.walk(pdf_folder):
                for file in files:
                    if file.lower().endswith(".pdf"):
                        pdf_files.append(os.path.join(root, file))

            if not pdf_files:
                logging.warning("No PDF files found")
                return

            num_processes = min(cpu_count(), len(pdf_files))
            logging.info(f"Processing {len(pdf_files)} PDFs using {num_processes} workers")

            with Pool(num_processes) as pool:
                pool.map(self.process_pdf, pdf_files)

        except Exception as e:
            logging.error(f"Folder processing failed: {e}", exc_info=True)

if __name__ == "__main__":
    pdf_folder_path = r"C:\Users\user\Downloads\test"
    processor = PDFProcessor()
    processor.process_pdf_folder(pdf_folder_path)
    logging.info("Processing completed")
