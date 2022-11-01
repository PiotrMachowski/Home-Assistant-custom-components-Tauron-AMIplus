import re
import datetime

from html.parser import HTMLParser

class TotalMeterValueHTMLScraper(HTMLParser):
    """Parses HTML to extract total meter value, unit, timestamp, and meter ID"""

    # the expected input: <div class="clear"></div>Pobór:<br /><span class="name"> <b></b> 02.10.2022 (23:59:59)</span> <span original-title="Nr licznika: 12345678" class="value tipsyOnTop"> 000035</span><span class="unit">kWh </span><br />

    @property
    def total(self):
        return self.__total

    @property
    def unit(self):
        return self.__unit

    @property
    def timestamp(self):
        return self.__timestamp

    @property
    def meter_id(self):
        return self.__meter_id

    def __init__(self):
        self.__total = None
        self.__unit = None
        self.__timestamp = None
        self.__meter_id = None
    
        self.__isValueSpan = False
        self.__isUnitSpan = False
        self.__isDateTimeSpan = False

        super(TotalMeterValueHTMLScraper, self).__init__()
    
    def handle_starttag(self, tag, attrs):
        if tag != "span":
            return

        for x in attrs:
            if x[0] == "class":
                classes = x[1].split()
                if "value" in classes:
                    self.__isValueSpan = True

                if "name" in classes:
                    self.__isDateTimeSpan = True

                if "unit" in classes:
                    self.__isUnitSpan = True

            if x[0] == "original-title":
                match = re.search(r"\d+", x[1])
                if match:
                    self.__meter_id = int(match[0])
    
    def handle_endtag(self, tag):
        if tag == "span":
            self.__isValueSpan = False
            self.__isDateTimeSpan = False
            self.__isUnitSpan = False
    
    def handle_data(self, data):
        if self.__isValueSpan:
            match = re.search(r"\d+", data)
            if match:
                self.__total = int(match[0])
                
        if self.__isUnitSpan:
            self.__unit = data.strip()
                
        if self.__isDateTimeSpan:
            match = re.search(r"(?P<day>\d{2})\.(?P<month>\d{2})\.(?P<year>\d{4}) \((?P<hour>\d{2})\:(?P<minute>\d{2})\:(?P<second>\d{2})\)", data)
            if match:
                self.__timestamp = datetime.datetime(
                    year = int(match.group("year")),
                    month = int(match.group("month")),
                    day = int(match.group("day")),
                    hour = int(match.group("hour")),
                    minute = int(match.group("minute")),
                    second = int(match.group("second"))
                )