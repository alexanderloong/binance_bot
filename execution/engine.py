from abc import ABC, abstractmethod

class ExecutionEngine(ABC):
    @abstractmethod
    def execute_long(self, price: float, **kwargs):
        pass

    @abstractmethod
    def execute_short(self, price: float, **kwargs):
        pass
        
    @abstractmethod
    def close_position(self, price: float, **kwargs):
        pass
