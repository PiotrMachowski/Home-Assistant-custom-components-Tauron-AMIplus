import re
import datetime

from html.parser import HTMLParser

from total_meter_reading import TotalMeterReading


class TotalMeterReadingHTMLScraper(HTMLParser):
    """Parses HTML to extract total meter value, unit, timestamp, and meter ID"""

    # the expected input for consumption only:           <div class="clear"></div>Pobór:<br /><span class="name"> <b></b> 02.10.2022 (23:59:59)</span> <span original-title="Nr licznika: 12345678" class="value tipsyOnTop"> 000035</span><span class="unit">kWh </span><br />
    # the expected input for consumption and generation: <div class="clear"></div>Pobór:<br /><span class="name"> <b></b> 02.10.2022 (23:59:59)</span> <span original-title="Nr licznika: 12345678" class="value tipsyOnTop"> 000035</span><span class="unit">kWh </span><br /><div class="clear"></div><br />Oddanie:<br /><span class="name"> <b></b> 02.10.2022 (23:59:59)</span> <span original-title="Nr licznika: 12345678" class="value tipsyOnTop"> 021483</span><span class="unit">kWh </span><br />

    @property
    def generation(self) -> TotalMeterReading:
        return self.__generation

    @property
    def consumption(self) -> TotalMeterReading:
        return self.__consumption

    @property
    def is_valid(self) -> bool:
        return self.__consumption is not None or self.__generation is not None

    def __init__(self):
        self.__current: TotalMeterReading = None
        self.__generation: TotalMeterReading = None
        self.__consumption: TotalMeterReading = None

        self.__is_value_span: bool = False
        self.__is_unit_span: bool = False
        self.__is_timestamp_span: bool = False

        super(TotalMeterReadingHTMLScraper, self).__init__()

    def handle_starttag(self, tag, attrs):
        if tag == "span":
            self.__handle_span_start_tag(attrs)

    def handle_endtag(self, tag):
        if tag == "span":
            self.__handle_span_end_tag()

    def handle_data(self, data):
        if data.strip() == "Pobór:":
            self.__start_consumption_context()
            return
        if data.strip() == "Oddanie:":
            self.__start_generation_context()
            return

        if self.__current is None:
            return

        if self.__is_value_span:
            self.__read_value(data)
        if self.__is_unit_span:
            self.__read_unit(data)
        if self.__is_timestamp_span:
            self.__read_timestamp(data)

    def __start_generation_context(self):
        self.__current = self.__generation = TotalMeterReading()

    def __start_consumption_context(self):
        self.__current = self.__consumption = TotalMeterReading()

    def __handle_span_start_tag(self, attrs):
        for x in attrs:
            if x[0] == "class":
                classes = x[1].split()
                if "value" in classes:
                    self.__is_value_span = True
                elif "name" in classes:
                    self.__is_timestamp_span = True
                elif "unit" in classes:
                    self.__is_unit_span = True

            if x[0] == "original-title":
                match = re.search(r"\d+", x[1])
                if match and self.__current is not None:
                    self.__current.meter_id = int(match[0])

    def __handle_span_end_tag(self):
        self.__is_value_span = self.__is_timestamp_span = self.__is_unit_span = False

    def __read_timestamp(self, data):
        match = re.search(
            r"(?P<day>\d{2})\.(?P<month>\d{2})\.(?P<year>\d{4}) \((?P<hour>\d{2})\:(?P<minute>\d{2})\:(?P<second>\d{2})\)",
            data
        )
        if match:
            self.__current.timestamp = datetime.datetime(
                year=int(match.group("year")),
                month=int(match.group("month")),
                day=int(match.group("day")),
                hour=int(match.group("hour")),
                minute=int(match.group("minute")),
                second=int(match.group("second"))
            )

    def __read_unit(self, data):
        self.__current.unit = data.strip()

    def __read_value(self, data):
        match = re.search(r"\d+", data)
        if match:
            self.__current.value = int(match[0])
