from collections import Counter
from app.models.downloaded_file import DownloadedFile
from app.schemas.statistics import FileStatistic
import string


DIGITS = string.digits


class CalculateFileStatistic:
    def __init__(self, files):
        self._files = files
        self._per_file = {f.filename: self._digit_frequency(f) for f in files}

    def _digit_frequency(self, file: DownloadedFile) -> dict[str, int]:
        with open(file.file_path, 'r', encoding='utf-8') as open_file:
            content = open_file.read()
            counter = Counter(char for char in content if char.isdigit())
            return {digit: counter.get(digit, 0) for digit in DIGITS}

    def _aggregate_digit_frequency(self, per_file: dict[str, dict[str, int]]) -> dict[str, int]:
        totals = {digit: 0 for digit in DIGITS}
        for frequencies in per_file.values():
            for digit in DIGITS:
                totals[digit] += frequencies[digit]
        return totals

    def get_total_statistics(self):
        return self._aggregate_digit_frequency(self._per_file)

    def get_file_statistic(self):
        return [FileStatistic(filename=name, digits=counts) for name, counts in self._per_file.items()]