"""Read-only source snapshot. Consumers receive detached working copies.

A future consent event writer must validate and audit a new snapshot explicitly;
recommendation generation is deliberately not such a writer.
"""
from collections.abc import Mapping
from copy import deepcopy


class CustomerSnapshot(Mapping):
    def __init__(self, records):
        self.__records = deepcopy(records)

    def __getitem__(self, customer_id):
        return deepcopy(self.__records[customer_id])

    def __iter__(self):
        return iter(self.__records)

    def __len__(self):
        return len(self.__records)
