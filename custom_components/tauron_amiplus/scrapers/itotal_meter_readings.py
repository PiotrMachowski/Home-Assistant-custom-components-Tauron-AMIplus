from total_meter_reading import TotalMeterReading


class ITotalMeterReadings:
    @property
    def generation(self) -> TotalMeterReading:
        pass

    @property
    def consumption(self) -> TotalMeterReading:
        pass
