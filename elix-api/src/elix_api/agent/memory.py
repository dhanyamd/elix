from datetime import datetime

import pixeltable as pxt
from loguru import logger
from pydantic import BaseModel


class MemoryRecord(BaseModel):
    message_id: str
    role: str
    content: str
    timestamp: datetime
 
class Memory: 
    def __init__(self, name: str): 
        # Sanitize name for pixeltable path (replace hyphens and other invalid chars with underscores)
        self.directory = name.replace("-", "_").replace(".", "_")
        
        pxt.create_dir(self.directory, if_exists="replace_force") 

        self._setup_table() 
        self._memory_table = pxt.get_table(f"{self.directory}.memory")
    def _setup_table(self): 
        self._memory_table = pxt.create_table(
            f"{self.directory}.memory",
            schema={
                "message_id": pxt.String,
                "role": pxt.String,
                "content": pxt.String, 
                "timestamp": pxt.Timestamp,
            },
            if_exists="ignore", 
        )
    def reset_memory(self):
        logger.info(f"Resetting memory: {self.directory}") 
        pxt.drop_dir(self.directory, if_not_exists="ignore", force=True)

    def insert(self, memory_record: MemoryRecord):
        self._memory_table.insert([memory_record.dict()])

    def get_all(self) -> list[MemoryRecord]:
        return [MemoryRecord(**record) for record in self._memory_table.collect()]

    def get_latest(self, n: int) -> list[MemoryRecord]:
        return self.get_all()[-n:]

    def get_by_message_id(self, message_id: str) -> MemoryRecord:
        return self._memory_table.where(self._memory_table.message_id == message_id).collect()[0]