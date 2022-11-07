import datetime


class TotalMeterReading:
    def __init__(self):
        self.__value: str = None
        self.__unit: str = None
        self.__timestamp: datetime.datetime = None
        self.__meter_id: str = None

    @property
    def value(self) -> str:
        return self.__value

    @value.setter
    def value(self, value: str):
        self.__value = value

    @property
    def unit(self) -> str:
        return self.__unit

    @unit.setter
    def unit(self, value: str):
        self.__unit = value

    @property
    def timestamp(self) -> datetime.datetime:
        return self.__timestamp

    @timestamp.setter
    def timestamp(self, value: datetime.datetime):
        self.__timestamp = value

    @property
    def meter_id(self) -> str:
        return self.__meter_id

    @meter_id.setter
    def meter_id(self, value: str):
        self.__meter_id = value
