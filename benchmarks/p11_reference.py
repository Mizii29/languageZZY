"""Independent nonnegative stats reference for the P11 workload, not a runtime implementation."""
from benchmarks.reference import CheckedArray, sum_bits


class CheckedStats(CheckedArray):
    def stats(self):
        total=0;minimum=maximum=None
        owner=self.meter.reserve(runtime_payload_bytes=0)
        try:
            for value in self.values:
                self.meter.cancellation.check()
                if type(value) is not int:raise TypeError('stats requires Int')
                if value<0:raise ValueError('this reference workload is nonnegative')
                with self.meter.reserve(runtime_payload_bytes=(max(total.bit_length(),value.bit_length())+7)//8):
                    bits=sum_bits(total,value,self.meter)
                self.meter.check('integer_bits',bits)
                next_owner=self.meter.reserve(runtime_payload_bytes=(bits+7)//8)
                total+=value;owner.release();owner=next_owner
                if minimum is None or value<minimum:minimum=value
                if maximum is None or value>maximum:maximum=value
            self.owners.append(owner)
            self.owners.append(self.meter.reserve(runtime_payload_bytes=(len(self.values).bit_length()+7)//8,runtime_objects=1,runtime_slots=5))
            return [len(self.values),total,minimum,maximum]
        except BaseException:
            owner.release();raise
