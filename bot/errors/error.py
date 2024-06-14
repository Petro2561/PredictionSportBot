class PredictionValidationError(Exception):
    def __init__(self, message="Ошибка в написании стран. Названия стран не соотствует id матча."):
        self.message = message
        super().__init__(self.message)