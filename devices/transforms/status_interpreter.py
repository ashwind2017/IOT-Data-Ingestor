"""
Status interpreter.

Reads `data_int` (set by Base64Decoder) and assigns a semantic label.
Currently a single-byte status code:

    0x01 -> passing
    anything else -> failing

Intentionally trivial — the point is to demonstrate that the parser
layer is pluggable and can grow without touching the source/storage
layers.
"""

from .base import Transform


class StatusInterpreter(Transform):
    PASSING_VALUE = 1

    def apply(self, record: dict) -> dict:
        value = record.get('data_int')
        if value is None:
            # Run order error; fail loud rather than guess.
            raise ValueError('data_int missing; run Base64Decoder first')

        record['status'] = 'passing' if value == self.PASSING_VALUE else 'failing'
        return record
